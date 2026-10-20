"""Photo upload, EXIF correction, local RapidOCR, and normalized word boxes."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from backend.app.models.schemas import (
    LineItem,
    PhotoData,
    SentenceItem,
    SentenceSegment,
    WordItem,
)
from backend.app.services.errors import (
    InvalidPhotoError,
    PhotoNotFoundError,
    PhotoOcrError,
    PhotoTooLargeError,
)

logger = logging.getLogger(__name__)

PHOTO_ID_RE = re.compile(r"^[0-9a-f]{32}$")
ENGLISH_WORD_RE = re.compile(r"\b[A-Za-z]+(?:['’\-][A-Za-z]+)*\b")
SENTENCE_END_RE = re.compile(r"[.!?][\"'”’)\]]*$")
WHITESPACE_RE = re.compile(r"\s+")
SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")
SPACE_AFTER_OPEN_RE = re.compile(r"([(\[])\s+")

OCR_ENGINE_NAME = "RapidOCR 3.10.0 / PP-OCRv6 small"
WORD_BOX_METHOD = (
    "RapidOCR return_word_box=True 直接返回英文单词框；"
    "没有从整行坐标推算或伪造单词框。"
)
MAX_IMAGE_PIXELS = 80_000_000
DISPLAY_MAX_EDGE = 3000
OCR_MAX_EDGE = 2000
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class OcrToken:
    raw_text: str
    bbox: list[float]
    confidence: float | None
    line_id: str
    line_index: int
    token_index: int
    from_word_box: bool


class PhotoOcrService:
    """Store photos locally and expose OCR words/lines/sentences."""

    def __init__(
        self,
        data_dir: Path,
        *,
        engine: Any | None = None,
        max_upload_bytes: int = 25 * 1024 * 1024,
        display_max_edge: int = DISPLAY_MAX_EDGE,
        ocr_max_edge: int = OCR_MAX_EDGE,
    ) -> None:
        self.photos_dir = Path(data_dir) / "photos"
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.engine = engine
        self.max_upload_bytes = max_upload_bytes
        self.display_max_edge = display_max_edge
        self.ocr_max_edge = ocr_max_edge
        self._engine_lock = threading.Lock()
        self._ocr_lock = threading.Lock()

    async def create_photo(self, upload: UploadFile) -> PhotoData:
        photo_id = uuid.uuid4().hex
        filename = _safe_filename(upload.filename)
        chunks: list[bytes] = []
        size = 0
        try:
            while True:
                chunk = await upload.read(CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > self.max_upload_bytes:
                    raise PhotoTooLargeError(
                        f"照片超过大小限制（最大 {self.max_upload_bytes // (1024 * 1024)} MB）。"
                    )
                chunks.append(chunk)
        finally:
            await upload.close()

        if size == 0:
            raise InvalidPhotoError("上传的照片为空。")

        data = b"".join(chunks)
        return await asyncio.to_thread(self._create_photo_sync, data, filename, photo_id)

    def _create_photo_sync(
        self,
        data: bytes,
        filename: str,
        photo_id: str,
    ) -> PhotoData:
        display_image, ocr_image = self._prepare_image(data)
        photo_path = self.photos_dir / f"{photo_id}.jpg"
        metadata_path = self.photos_dir / f"{photo_id}.json"
        temp_photo = self.photos_dir / f".{photo_id}.jpg.part"
        temp_metadata = self.photos_dir / f".{photo_id}.json.part"

        try:
            display_image.save(
                temp_photo,
                format="JPEG",
                quality=92,
                optimize=True,
                progressive=True,
            )
            temp_photo.replace(photo_path)

            ocr_error: str | None = None
            result = None
            try:
                result = self._run_ocr(ocr_image)
            except PhotoOcrError as exc:
                ocr_error = str(exc)
            except Exception:
                logger.exception("Photo OCR failed photo_id=%s", photo_id)
                ocr_error = "照片 OCR 失败，请确认 RapidOCR 依赖已安装，或换一张更清晰的照片。"

            if ocr_error is not None:
                photo_data = _empty_photo_data(
                    photo_id=photo_id,
                    filename=filename,
                    width=display_image.width,
                    height=display_image.height,
                    message=ocr_error,
                )
            else:
                try:
                    photo_data = _parse_ocr_result(
                        result,
                        photo_id=photo_id,
                        filename=filename,
                        display_width=display_image.width,
                        display_height=display_image.height,
                        ocr_width=ocr_image.width,
                        ocr_height=ocr_image.height,
                    )
                except Exception:
                    logger.exception("Photo OCR result parsing failed photo_id=%s", photo_id)
                    photo_data = _empty_photo_data(
                        photo_id=photo_id,
                        filename=filename,
                        width=display_image.width,
                        height=display_image.height,
                        message="照片 OCR 结果解析失败，请换一张照片重试。",
                    )

            metadata = {
                "cache_version": 1,
                "photo_id": photo_id,
                "filename": filename,
                "width": display_image.width,
                "height": display_image.height,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "ocr_engine": OCR_ENGINE_NAME,
            }
            temp_metadata.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp_metadata.replace(metadata_path)
            return photo_data
        except Exception:
            temp_photo.unlink(missing_ok=True)
            temp_metadata.unlink(missing_ok=True)
            photo_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
            raise

    def _prepare_image(self, data: bytes) -> tuple[Any, Any]:
        try:
            from PIL import Image, ImageOps, UnidentifiedImageError
        except ImportError as exc:
            raise PhotoOcrError(
                "照片处理依赖未安装，请运行 pip install -r requirements-ocr.txt。"
            ) from exc

        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
        try:
            with Image.open(io.BytesIO(data)) as source:
                source.load()
                image = ImageOps.exif_transpose(source).convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise InvalidPhotoError("无法读取这张图片，请选择 JPG、PNG 或 WebP 照片。") from exc
        except Image.DecompressionBombError as exc:
            raise InvalidPhotoError("照片分辨率过大，请先缩小后再试。") from exc

        if image.width < 200 or image.height < 200:
            raise InvalidPhotoError("照片太小，请选择更清晰、分辨率更高的照片。")
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise InvalidPhotoError("照片分辨率过大，请先缩小到 8000 万像素以内。")

        display = image.copy()
        display.thumbnail((self.display_max_edge, self.display_max_edge), Image.Resampling.LANCZOS)
        ocr_image = display.copy()
        ocr_image.thumbnail((self.ocr_max_edge, self.ocr_max_edge), Image.Resampling.LANCZOS)
        return display, ocr_image

    def _run_ocr(self, ocr_image: Any) -> Any:
        try:
            import numpy as np
            from rapidocr import RapidOCR
        except ImportError as exc:
            raise PhotoOcrError(
                "照片 OCR 依赖未安装，请运行 pip install -r requirements-ocr.txt。"
            ) from exc

        with self._engine_lock:
            if self.engine is None:
                self.engine = RapidOCR()

        array = np.asarray(ocr_image)
        with self._ocr_lock:
            return self.engine(array, return_word_box=True)

    def get_photo_path(self, photo_id: str) -> Path:
        photo_id = _validate_photo_id(photo_id)
        metadata_path = self.photos_dir / f"{photo_id}.json"
        photo_path = self.photos_dir / f"{photo_id}.jpg"
        if not metadata_path.is_file() or not photo_path.is_file():
            raise PhotoNotFoundError("找不到这张照片，请重新上传。")
        return photo_path

    def delete_photo(self, photo_id: str) -> None:
        photo_id = _validate_photo_id(photo_id)
        metadata_path = self.photos_dir / f"{photo_id}.json"
        photo_path = self.photos_dir / f"{photo_id}.jpg"
        if not metadata_path.is_file() and not photo_path.is_file():
            raise PhotoNotFoundError("找不到这张照片。")
        photo_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)


def _parse_ocr_result(
    result: Any,
    *,
    photo_id: str,
    filename: str,
    display_width: int,
    display_height: int,
    ocr_width: int,
    ocr_height: int,
) -> PhotoData:
    boxes = _as_list(getattr(result, "boxes", None))
    txts = _as_list(getattr(result, "txts", None))
    scores = _as_list(getattr(result, "scores", None))
    word_results = _as_list(getattr(result, "word_results", None))

    line_items: list[LineItem] = []
    tokens_by_line: list[list[OcrToken]] = []
    line_has_word_boxes: list[bool] = []

    for index, raw_text in enumerate(txts):
        text = _tidy_text(str(raw_text))
        line_quad = boxes[index] if index < len(boxes) else None
        line_bbox = _quad_bbox(line_quad, ocr_width, ocr_height)
        line_id = f"l-{index}"

        line_tokens: list[OcrToken] = []
        raw_words = word_results[index] if index < len(word_results) else None
        if raw_words:
            for token_index, item in enumerate(raw_words):
                if not isinstance(item, (list, tuple)) or len(item) < 3:
                    continue
                word_text = str(item[0]).strip()
                if not word_text:
                    continue
                word_bbox = _quad_bbox(item[2], ocr_width, ocr_height)
                if word_bbox is None:
                    continue
                confidence = _confidence(item[1])
                line_tokens.append(
                    OcrToken(
                        raw_text=word_text,
                        bbox=word_bbox,
                        confidence=confidence,
                        line_id=line_id,
                        line_index=index,
                        token_index=token_index,
                        from_word_box=True,
                    )
                )

        if line_bbox is None and line_tokens:
            line_bbox = _union_bbox(token.bbox for token in line_tokens)
        if line_bbox is None:
            continue
        if not text:
            text = _tidy_text(" ".join(token.raw_text for token in line_tokens))
        if not text:
            continue

        # Some OCR modes return one box per character for CJK text. Never
        # present those as independent English word boxes; fall back to the
        # line as a sentence-level hit area instead.
        word_texts = [
            token.raw_text.strip()
            for token in line_tokens
            if token.from_word_box
        ]
        char_like = (
            " " in text
            and len(word_texts) > 1
            and all(len(value) <= 1 for value in word_texts)
        )
        if char_like:
            line_tokens = []

        if not line_tokens:
            line_tokens = [
                OcrToken(
                    raw_text=text,
                    bbox=line_bbox,
                    confidence=_confidence(scores[index]) if index < len(scores) else None,
                    line_id=line_id,
                    line_index=index,
                    token_index=0,
                    from_word_box=False,
                )
            ]
        line_items.append(LineItem(id=line_id, text=text, bbox=line_bbox))
        tokens_by_line.append(line_tokens)
        line_has_word_boxes.append(any(token.from_word_box for token in line_tokens))

    all_tokens = [token for tokens in tokens_by_line for token in tokens]
    word_items: list[WordItem] = []
    token_to_word: dict[int, WordItem] = {}
    for token in all_tokens:
        if not token.from_word_box:
            continue
        word_text = _english_word(token.raw_text)
        if word_text is None:
            continue
        word = WordItem(
            id=f"w-{token.line_index}-{token.token_index}",
            text=word_text,
            bbox=token.bbox,
            line_id=token.line_id,
            sentence_id=None,
        )
        word_items.append(word)
        token_to_word[id(token)] = word

    sentences = _build_sentences(all_tokens, token_to_word)
    has_text = bool(line_items)
    has_english = any(
        ENGLISH_WORD_RE.search(line.text) is not None for line in line_items
    )
    has_word_boxes = bool(word_items)

    message: str | None = None
    if not has_text:
        message = (
            "没有识别到文字。请尽量正对书页、保证光线均匀，并拍得更清晰一些。"
        )
    elif not has_english:
        message = "识别到文字，但没有检测到英文单词；当前只支持英文点读。"
    elif not has_word_boxes:
        message = (
            "识别到英文文字，但 OCR 没有返回单词级坐标，"
            "无法建立单词点击区域；可以点击整句或换一张更清晰的照片。"
        )

    warnings: list[str] = []
    confidences = [
        token.confidence
        for token in all_tokens
        if token.from_word_box and token.confidence is not None
    ]
    if confidences and sum(confidences) / len(confidences) < 0.6:
        warnings.append("OCR 置信度较低，照片可能模糊或倾斜，识别结果可能不准确。")
    if has_english and not has_word_boxes:
        warnings.append("没有使用行框推算单词框，因此单词点击不可用。")
    elif any(not flag for flag in line_has_word_boxes):
        warnings.append("部分文字行没有单词级坐标，那些行只能按整句点击。")
    if 0 < len(word_items) < 3:
        warnings.append("识别到的英文单词较少，请尽量拍正、拍清晰。")

    return PhotoData(
        photo_id=photo_id,
        filename=filename,
        width=display_width,
        height=display_height,
        photo_url=f"/api/photos/{photo_id}/file",
        has_text=has_text,
        has_english=has_english,
        message=message,
        quality_warning=" ".join(warnings) if warnings else None,
        word_box_method=WORD_BOX_METHOD,
        ocr_engine=OCR_ENGINE_NAME,
        words=word_items,
        lines=line_items,
        sentences=sentences,
    )


def _empty_photo_data(
    *,
    photo_id: str,
    filename: str,
    width: int,
    height: int,
    message: str,
) -> PhotoData:
    return PhotoData(
        photo_id=photo_id,
        filename=filename,
        width=width,
        height=height,
        photo_url=f"/api/photos/{photo_id}/file",
        has_text=False,
        has_english=False,
        message=message,
        quality_warning=None,
        word_box_method=WORD_BOX_METHOD,
        ocr_engine=OCR_ENGINE_NAME,
        words=[],
        lines=[],
        sentences=[],
    )


def _build_sentences(
    tokens: list[OcrToken],
    token_to_word: dict[int, WordItem],
) -> list[SentenceItem]:
    sentences: list[SentenceItem] = []
    current: list[OcrToken] = []
    sentence_index = 0

    def finish() -> None:
        nonlocal sentence_index
        if not current:
            return
        sentence_id = f"s-{sentence_index}"
        sentence_index += 1
        english_tokens = [token for token in current if _english_word(token.raw_text)]
        if not english_tokens:
            current.clear()
            return

        for token in english_tokens:
            word = token_to_word.get(id(token))
            if word is not None:
                word.sentence_id = sentence_id

        groups: dict[int, list[OcrToken]] = {}
        for token in current:
            groups.setdefault(token.line_index, []).append(token)
        segments = [
            SentenceSegment(
                line_id=line_tokens[0].line_id,
                bbox=_union_bbox(token.bbox for token in line_tokens),
            )
            for _, line_tokens in sorted(groups.items())
        ]
        sentences.append(
            SentenceItem(
                id=sentence_id,
                text=_tidy_text(" ".join(token.raw_text for token in current)),
                bbox=_union_bbox(token.bbox for token in current),
                segments=segments,
            )
        )
        current.clear()

    for token in tokens:
        current.append(token)
        if SENTENCE_END_RE.search(token.raw_text):
            finish()
    finish()
    return sentences


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _quad_bbox(quad: Any, width: int, height: int) -> list[float] | None:
    if quad is None:
        return None
    try:
        points = list(quad)
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
    except (TypeError, ValueError, IndexError):
        return None
    if not xs or not ys:
        return None
    return _normalize_bbox(min(xs), min(ys), max(xs), max(ys), width, height)


def _normalize_bbox(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    width: int,
    height: int,
) -> list[float] | None:
    if width <= 0 or height <= 0:
        return None
    values = [
        _clamp01(x0 / width),
        _clamp01(y0 / height),
        _clamp01(x1 / width),
        _clamp01(y1 / height),
    ]
    if values[2] <= values[0] or values[3] <= values[1]:
        return None
    return [round(value, 6) for value in values]


def _union_bbox(boxes: Any) -> list[float]:
    values = list(boxes)
    x0 = min(box[0] for box in values)
    y0 = min(box[1] for box in values)
    x1 = max(box[2] for box in values)
    y1 = max(box[3] for box in values)
    return [round(x0, 6), round(y0, 6), round(x1, 6), round(y1, 6)]


def _confidence(value: Any) -> float | None:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _english_word(raw_text: str) -> str | None:
    match = ENGLISH_WORD_RE.search(raw_text)
    return match.group(0) if match else None


def _tidy_text(text: str) -> str:
    text = WHITESPACE_RE.sub(" ", text).strip()
    text = SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    text = SPACE_AFTER_OPEN_RE.sub(r"\1", text)
    return text


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _safe_filename(filename: str | None) -> str:
    name = (filename or "photo.jpg").replace("\\", "/").split("/")[-1]
    name = name.replace("\x00", "").strip()
    return (name or "photo.jpg")[:255]


def _validate_photo_id(photo_id: str) -> str:
    if not PHOTO_ID_RE.fullmatch(photo_id):
        raise PhotoNotFoundError("照片 ID 无效，请重新上传。")
    return photo_id
