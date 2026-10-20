"""Local book storage and page extraction orchestration."""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path

from fastapi import UploadFile
from pydantic import ValidationError

from backend.app.models.schemas import BookInfo, PageData
from backend.app.services.errors import (
    BookNotFoundError,
    InvalidPdfError,
    PageExtractionError,
    PageNotFoundError,
    PdfError,
    UploadTooLargeError,
)
from backend.app.services.pdf_extractor import extract_page_data, open_pdf

logger = logging.getLogger(__name__)

BOOK_ID_RE = re.compile(r"^[0-9a-f]{32}$")
CHUNK_SIZE = 1024 * 1024
HEADER_PROBE_SIZE = 1024


class BookService:
    """Store PDFs under data/books and expose validated page data."""

    def __init__(self, data_dir: Path, max_upload_bytes: int = 100 * 1024 * 1024):
        self.books_dir = Path(data_dir) / "books"
        self.books_dir.mkdir(parents=True, exist_ok=True)
        self.max_upload_bytes = max_upload_bytes

    async def create_book(self, upload: UploadFile) -> BookInfo:
        book_id = uuid.uuid4().hex
        original_name = _safe_filename(upload.filename)
        temp_path = self.books_dir / f".{book_id}.part"
        final_path = self.books_dir / f"{book_id}.pdf"
        metadata_path = self.books_dir / f"{book_id}.json"
        temp_metadata_path = self.books_dir / f".{book_id}.json.part"

        size = 0
        header_probe = b""

        try:
            with temp_path.open("wb") as output:
                while True:
                    chunk = await upload.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self.max_upload_bytes:
                        max_mb = self.max_upload_bytes // (1024 * 1024)
                        raise UploadTooLargeError(
                            f"PDF 超过大小限制（最大 {max_mb} MB）。"
                        )
                    if len(header_probe) < HEADER_PROBE_SIZE:
                        remaining = HEADER_PROBE_SIZE - len(header_probe)
                        header_probe += chunk[:remaining]
                    output.write(chunk)

            if size == 0:
                raise InvalidPdfError("上传的文件为空。")
            if b"%PDF-" not in header_probe:
                raise InvalidPdfError("文件不是有效的 PDF（缺少 PDF 文件头）。")

            doc = open_pdf(temp_path)
            try:
                page_count = doc.page_count
                title = _clean_title(doc.metadata)
            finally:
                doc.close()

            temp_path.replace(final_path)

            metadata = BookInfo(
                book_id=book_id,
                filename=original_name,
                page_count=page_count,
                title=title,
                size_bytes=size,
            )
            temp_metadata_path.write_text(
                json.dumps(metadata.model_dump(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp_metadata_path.replace(metadata_path)
            return metadata

        except Exception:
            temp_path.unlink(missing_ok=True)
            final_path.unlink(missing_ok=True)
            temp_metadata_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

    def get_book_info(self, book_id: str) -> BookInfo:
        book_id = _validate_book_id(book_id)
        metadata_path = self.books_dir / f"{book_id}.json"
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise BookNotFoundError("找不到这本书，请重新上传 PDF。") from exc
        except (OSError, ValueError) as exc:
            raise BookNotFoundError("书籍记录损坏，请重新上传 PDF。") from exc

        try:
            info = BookInfo(**data)
        except (TypeError, ValidationError) as exc:
            raise BookNotFoundError("书籍记录损坏，请重新上传 PDF。") from exc

        if info.book_id != book_id:
            raise BookNotFoundError("书籍记录不匹配，请重新上传 PDF。")
        return info

    def get_pdf_path(self, book_id: str) -> tuple[BookInfo, Path]:
        info = self.get_book_info(book_id)
        pdf_path = self.books_dir / f"{info.book_id}.pdf"
        if not pdf_path.is_file():
            raise BookNotFoundError("找不到 PDF 文件，请重新上传。")
        return info, pdf_path

    def get_page(self, book_id: str, page_number: int) -> PageData:
        info, pdf_path = self.get_pdf_path(book_id)
        if page_number < 1 or page_number > info.page_count:
            raise PageNotFoundError(f"页码必须在 1 到 {info.page_count} 之间。")

        try:
            doc = open_pdf(pdf_path)
        except PdfError:
            raise

        try:
            return extract_page_data(doc, page_number, book_id)
        except PdfError:
            raise
        except Exception as exc:
            logger.exception(
                "Unexpected page extraction failure book_id=%s page=%s",
                book_id,
                page_number,
            )
            raise PageExtractionError(
                "这一页的文字提取失败，请换一页重试或检查 PDF 文件。"
            ) from exc
        finally:
            doc.close()


def _validate_book_id(book_id: str) -> str:
    if not BOOK_ID_RE.fullmatch(book_id):
        raise BookNotFoundError("书籍 ID 无效，请重新上传 PDF。")
    return book_id


def _safe_filename(filename: str | None) -> str:
    name = (filename or "book.pdf").replace("\\", "/").split("/")[-1]
    name = name.replace("\x00", "").strip()
    return (name or "book.pdf")[:255]


def _clean_title(metadata: dict[str, str] | None) -> str | None:
    if not metadata:
        return None
    title = metadata.get("title")
    if not isinstance(title, str):
        return None
    title = title.strip()
    return title[:200] if title else None
