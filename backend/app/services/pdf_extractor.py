"""Extract positioned English words from PDF pages with PyMuPDF.

Coordinate contract
-------------------
PyMuPDF returns text coordinates in the *unrotated* page coordinate system,
relative to the page's top-left corner. PDF.js renders the page in its
displayed rotation. To make the two line up, every rectangle is transformed
with ``page.rotation_matrix`` and then normalized against the displayed
``page.rect``. The API therefore exposes only normalized visual coordinates:

    [x0, y0, x1, y1] with 0 <= values <= 1

The origin is the top-left of the rendered page and y grows downwards.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pymupdf

from backend.app.models.schemas import (
    LineItem,
    PageData,
    SentenceItem,
    SentenceSegment,
    WordItem,
)
from backend.app.services.errors import (
    EmptyPdfError,
    EncryptedPdfError,
    InvalidPdfError,
    PageExtractionError,
    PageNotFoundError,
)

ENGLISH_WORD_RE = re.compile(r"\b[A-Za-z]+(?:['’\-][A-Za-z]+)*\b")
SENTENCE_END_RE = re.compile(r"[.!?][\"'”’)\]]*$")
WHITESPACE_RE = re.compile(r"\s+")
SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")
SPACE_AFTER_OPEN_RE = re.compile(r"([(\[])\s+")


@dataclass(frozen=True)
class Token:
    """A whitespace-delimited token returned by PyMuPDF."""

    raw_text: str
    rect: pymupdf.Rect
    block_no: int
    line_no: int
    word_no: int


def open_pdf(path: Path) -> pymupdf.Document:
    """Open and validate a PDF, returning an open PyMuPDF document."""
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise InvalidPdfError("PDF 无法打开，文件可能已损坏或不是有效的 PDF。") from exc

    try:
        if not doc.is_pdf:
            raise InvalidPdfError("文件不是有效的 PDF。")
        if doc.needs_pass:
            raise EncryptedPdfError("PDF 已加密，当前版本暂不支持需要密码的文件。")
        if doc.page_count < 1:
            raise EmptyPdfError("PDF 没有可显示的页面。")
    except Exception:
        doc.close()
        raise

    return doc


def normalize_rect(page: pymupdf.Page, rect: pymupdf.Rect) -> list[float]:
    """Convert an unrotated PDF rectangle to normalized visual coordinates."""
    page_rect = page.rect
    if page_rect.width <= 0 or page_rect.height <= 0:
        raise PageExtractionError("页面尺寸无效。")

    visual_rect = rect * page.rotation_matrix if page.rotation else rect

    x0 = (visual_rect.x0 - page_rect.x0) / page_rect.width
    y0 = (visual_rect.y0 - page_rect.y0) / page_rect.height
    x1 = (visual_rect.x1 - page_rect.x0) / page_rect.width
    y1 = (visual_rect.y1 - page_rect.y0) / page_rect.height
    return [
        round(_clamp01(x0), 6),
        round(_clamp01(y0), 6),
        round(_clamp01(x1), 6),
        round(_clamp01(y1), 6),
    ]


def extract_page_data(
    doc: pymupdf.Document,
    page_number: int,
    book_id: str,
) -> PageData:
    """Extract words, lines and sentences for a 1-based page number."""
    if page_number < 1 or page_number > doc.page_count:
        raise PageNotFoundError(f"页码必须在 1 到 {doc.page_count} 之间。")

    try:
        page = doc.load_page(page_number - 1)
        tokens = _extract_tokens(page)
        return _build_page_data(
            page=page,
            tokens=tokens,
            book_id=book_id,
            page_number=page_number,
            page_count=doc.page_count,
        )
    except PageNotFoundError:
        raise
    except PageExtractionError:
        raise
    except Exception as exc:
        raise PageExtractionError("无法提取这一页的文字，请换一页重试或检查 PDF 文件。") from exc


def _extract_tokens(page: pymupdf.Page) -> list[Token]:
    try:
        raw_words = page.get_text("words", sort=False)
    except Exception as exc:
        raise PageExtractionError("无法读取这一页的文字层。") from exc

    tokens: list[Token] = []
    for item in raw_words:
        if len(item) < 8:
            continue
        raw_text = str(item[4]).strip()
        if not raw_text:
            continue
        rect = pymupdf.Rect(item[0], item[1], item[2], item[3])
        if rect.width <= 0 or rect.height <= 0:
            continue
        tokens.append(
            Token(
                raw_text=raw_text,
                rect=rect,
                block_no=int(item[5]),
                line_no=int(item[6]),
                word_no=int(item[7]),
            )
        )
    return tokens


def _build_page_data(
    page: pymupdf.Page,
    tokens: list[Token],
    book_id: str,
    page_number: int,
    page_count: int,
) -> PageData:
    tokens = sorted(
        tokens,
        key=lambda token: (token.block_no, token.line_no, token.word_no, token.rect.x0),
    )

    line_groups: dict[tuple[int, int], list[Token]] = {}
    for token in tokens:
        line_groups.setdefault((token.block_no, token.line_no), []).append(token)

    line_items: list[LineItem] = []
    for (block_no, line_no) in sorted(line_groups):
        line_tokens = sorted(
            line_groups[(block_no, line_no)],
            key=lambda token: (token.word_no, token.rect.x0),
        )
        line_items.append(
            LineItem(
                id=_line_id(block_no, line_no),
                text=_tidy_text(" ".join(token.raw_text for token in line_tokens)),
                bbox=normalize_rect(page, _union_rects(token.rect for token in line_tokens)),
            )
        )

    word_records: list[dict[str, object]] = []
    records_by_position: dict[tuple[int, int, int], dict[str, object]] = {}
    for token in tokens:
        text = _english_word(token.raw_text)
        if text is None:
            continue
        record: dict[str, object] = {
            "token": token,
            "item": WordItem(
                id=f"w-{token.block_no}-{token.line_no}-{token.word_no}",
                text=text,
                bbox=normalize_rect(page, token.rect),
                line_id=_line_id(token.block_no, token.line_no),
                sentence_id=None,
            ),
        }
        word_records.append(record)
        records_by_position[(token.block_no, token.line_no, token.word_no)] = record

    sentence_items = _build_sentences(page, tokens, records_by_position)

    has_text = bool(tokens)
    if not has_text:
        has_text = bool(page.get_text("text").strip())

    is_scanned = False
    if not has_text:
        try:
            is_scanned = bool(page.get_images(full=True))
        except Exception:
            is_scanned = False

    if is_scanned:
        message = "此页没有可提取的文字，可能是扫描版 PDF，当前版本暂不支持 OCR。"
    elif not has_text:
        message = "此页没有可提取的文字（空白页）。"
    elif not word_records:
        message = "此页有文字，但没有检测到可点击的英文单词。"
    else:
        message = None

    return PageData(
        book_id=book_id,
        page=page_number,
        page_count=page_count,
        width=round(page.rect.width, 3),
        height=round(page.rect.height, 3),
        rotation=page.rotation,
        has_text=has_text,
        is_scanned=is_scanned,
        message=message,
        words=[record["item"] for record in word_records],
        lines=line_items,
        sentences=sentence_items,
    )


def _build_sentences(
    page: pymupdf.Page,
    tokens: list[Token],
    records_by_position: dict[tuple[int, int, int], dict[str, object]],
) -> list[SentenceItem]:
    sentences: list[SentenceItem] = []
    blocks = sorted({token.block_no for token in tokens})

    for block_no in blocks:
        block_tokens = [token for token in tokens if token.block_no == block_no]
        lines = sorted({token.line_no for token in block_tokens})
        current: list[Token] = []
        sentence_index = 0

        for line_no in lines:
            line_tokens = sorted(
                [token for token in block_tokens if token.line_no == line_no],
                key=lambda token: (token.word_no, token.rect.x0),
            )
            for token in line_tokens:
                current.append(token)
                if SENTENCE_END_RE.search(token.raw_text):
                    sentence = _finish_sentence(
                        page=page,
                        tokens=current,
                        block_no=block_no,
                        sentence_index=sentence_index,
                        records_by_position=records_by_position,
                    )
                    if sentence is not None:
                        sentences.append(sentence)
                    sentence_index += 1
                    current = []

        if current:
            sentence = _finish_sentence(
                page=page,
                tokens=current,
                block_no=block_no,
                sentence_index=sentence_index,
                records_by_position=records_by_position,
            )
            if sentence is not None:
                sentences.append(sentence)

    return sentences


def _finish_sentence(
    page: pymupdf.Page,
    tokens: list[Token],
    block_no: int,
    sentence_index: int,
    records_by_position: dict[tuple[int, int, int], dict[str, object]],
) -> SentenceItem | None:
    english_tokens = [token for token in tokens if _english_word(token.raw_text)]
    if not english_tokens:
        return None

    sentence_id = f"s-{block_no}-{sentence_index}"
    for token in english_tokens:
        record = records_by_position.get(
            (token.block_no, token.line_no, token.word_no)
        )
        if record is not None:
            record["item"].sentence_id = sentence_id

    return SentenceItem(
        id=sentence_id,
        text=_tidy_text(" ".join(token.raw_text for token in tokens)),
        bbox=normalize_rect(page, _union_rects(token.rect for token in tokens)),
        segments=_sentence_segments(page, tokens),
    )


def _sentence_segments(
    page: pymupdf.Page,
    tokens: list[Token],
) -> list[SentenceSegment]:
    """Return one clickable box per line, avoiding a large multi-line union box."""
    groups: dict[tuple[int, int], list[Token]] = {}
    for token in tokens:
        groups.setdefault((token.block_no, token.line_no), []).append(token)

    segments: list[SentenceSegment] = []
    for (block_no, line_no) in sorted(groups):
        line_tokens = groups[(block_no, line_no)]
        segments.append(
            SentenceSegment(
                line_id=_line_id(block_no, line_no),
                bbox=normalize_rect(
                    page,
                    _union_rects(token.rect for token in line_tokens),
                ),
            )
        )
    return segments


def _english_word(raw_text: str) -> str | None:
    match = ENGLISH_WORD_RE.search(raw_text)
    if match is None:
        return None
    word = match.group(0)
    return word if word else None


def _tidy_text(text: str) -> str:
    text = WHITESPACE_RE.sub(" ", text).strip()
    text = SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    text = SPACE_AFTER_OPEN_RE.sub(r"\1", text)
    return text


def _union_rects(rects: Iterable[pymupdf.Rect]) -> pymupdf.Rect:
    iterator = iter(rects)
    try:
        union = pymupdf.Rect(next(iterator))
    except StopIteration as exc:
        raise PageExtractionError("无法计算文字区域。") from exc
    for rect in iterator:
        union.include_rect(rect)
    return union


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _line_id(block_no: int, line_no: int) -> str:
    return f"l-{block_no}-{line_no}"
