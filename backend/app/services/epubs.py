"""Local EPUB storage and container validation."""

from __future__ import annotations

import json
import logging
import re
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

from fastapi import UploadFile
from pydantic import ValidationError

from backend.app.models.schemas import EpubInfo
from backend.app.services.errors import (
    EpubNotFoundError,
    EpubTooLargeError,
    InvalidEpubError,
)

logger = logging.getLogger(__name__)

EPUB_ID_RE = re.compile(r"^[0-9a-f]{32}$")
CHUNK_SIZE = 1024 * 1024
MIMETYPE_BYTES = b"application/epub+zip"
CONTAINER_PATH = "META-INF/container.xml"
MAX_METADATA_BYTES = 4 * 1024 * 1024


class EpubService:
    """Store EPUBs under data/epubs after checking the basic container."""

    def __init__(self, data_dir: Path, max_upload_bytes: int = 100 * 1024 * 1024):
        self.epubs_dir = Path(data_dir) / "epubs"
        self.epubs_dir.mkdir(parents=True, exist_ok=True)
        self.max_upload_bytes = max_upload_bytes

    async def create_epub(self, upload: UploadFile) -> EpubInfo:
        epub_id = uuid.uuid4().hex
        original_name = _safe_filename(upload.filename)
        temp_path = self.epubs_dir / f".{epub_id}.part"
        final_path = self.epubs_dir / f"{epub_id}.epub"
        metadata_path = self.epubs_dir / f"{epub_id}.json"
        temp_metadata_path = self.epubs_dir / f".{epub_id}.json.part"

        size = 0
        try:
            with temp_path.open("wb") as output:
                while True:
                    chunk = await upload.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self.max_upload_bytes:
                        max_mb = self.max_upload_bytes // (1024 * 1024)
                        raise EpubTooLargeError(
                            f"EPUB 超过大小限制（最大 {max_mb} MB）。"
                        )
                    output.write(chunk)

            if size == 0:
                raise InvalidEpubError("上传的 EPUB 为空。")
            if not zipfile.is_zipfile(temp_path):
                raise InvalidEpubError("文件不是有效的 EPUB（不是 ZIP 容器）。")

            title, author, language, chapter_count = _read_epub_metadata(
                temp_path, fallback_title=Path(original_name).stem
            )
            temp_path.replace(final_path)

            info = EpubInfo(
                epub_id=epub_id,
                filename=original_name,
                title=title,
                author=author,
                language=language,
                chapter_count=chapter_count,
                size_bytes=size,
            )
            temp_metadata_path.write_text(
                json.dumps(info.model_dump(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp_metadata_path.replace(metadata_path)
            return info

        except Exception:
            temp_path.unlink(missing_ok=True)
            final_path.unlink(missing_ok=True)
            temp_metadata_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

    def get_epub_info(self, epub_id: str) -> EpubInfo:
        epub_id = _validate_epub_id(epub_id)
        metadata_path = self.epubs_dir / f"{epub_id}.json"
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise EpubNotFoundError("找不到这个 EPUB，请重新上传。") from exc
        except (OSError, ValueError) as exc:
            raise EpubNotFoundError("EPUB 记录损坏，请重新上传。") from exc

        try:
            info = EpubInfo(**data)
        except (TypeError, ValidationError) as exc:
            raise EpubNotFoundError("EPUB 记录损坏，请重新上传。") from exc

        if info.epub_id != epub_id:
            raise EpubNotFoundError("EPUB 记录不匹配，请重新上传。")
        return info

    def get_epub_path(self, epub_id: str) -> tuple[EpubInfo, Path]:
        info = self.get_epub_info(epub_id)
        epub_path = self.epubs_dir / f"{info.epub_id}.epub"
        if not epub_path.is_file():
            raise EpubNotFoundError("找不到 EPUB 文件，请重新上传。")
        return info, epub_path


def _read_epub_metadata(
    path: Path, *, fallback_title: str | None = None
) -> tuple[str, str | None, str | None, int]:
    """Validate the EPUB container and return display metadata.

    Only the mimetype, container.xml and package document are read, each with
    an uncompressed-size cap. No book text is written to logs.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            mimetype = _read_member(
                archive, "mimetype", 1024, "文件不是有效的 EPUB（缺少 mimetype）。"
            )
            if mimetype.strip() != MIMETYPE_BYTES:
                raise InvalidEpubError("文件不是有效的 EPUB（mimetype 不正确）。")

            container_data = _read_member(
                archive,
                CONTAINER_PATH,
                MAX_METADATA_BYTES,
                "文件不是有效的 EPUB（缺少 META-INF/container.xml）。",
            )
            container_root = _parse_xml(container_data)
            rootfile = _find_first(container_root, "rootfile")
            if rootfile is None:
                raise InvalidEpubError("文件不是有效的 EPUB（找不到内容清单）。")

            rootfile_path = _safe_member_path(rootfile.get("full-path"))
            if rootfile_path is None:
                raise InvalidEpubError("EPUB 的内容路径无效。")

            package_data = _read_member(
                archive,
                rootfile_path,
                MAX_METADATA_BYTES,
                "文件不是有效的 EPUB（找不到内容清单）。",
            )
            package_root = _parse_xml(package_data)
    except zipfile.BadZipFile as exc:
        raise InvalidEpubError("文件不是有效的 EPUB（ZIP 容器损坏）。") from exc
    except RuntimeError as exc:
        # Encrypted ZIP entries raise a RuntimeError from zipfile.
        raise InvalidEpubError("EPUB 包含不支持的内容加密。") from exc

    metadata = _find_first(package_root, "metadata")
    title = _first_text(metadata, "title") or fallback_title or path.stem or "未命名 EPUB"
    author = _first_text(metadata, "creator")
    language = _first_text(metadata, "language")

    spine = _find_first(package_root, "spine")
    chapter_count = 0
    if spine is not None:
        chapter_count = sum(
            1 for item in spine if _local_name(item.tag) == "itemref"
        )
    if chapter_count == 0:
        raise InvalidEpubError("EPUB 没有可阅读章节。")

    return title[:200], _optional_text(author, 200), _optional_text(language, 40), chapter_count


def _read_member(
    archive: zipfile.ZipFile,
    name: str,
    max_bytes: int,
    missing_message: str,
) -> bytes:
    filename = name.replace("\\", "/")
    try:
        info = archive.getinfo(filename)
    except KeyError as exc:
        raise InvalidEpubError(missing_message) from exc
    if info.file_size > max_bytes:
        raise InvalidEpubError("EPUB 的内容清单过大，无法安全读取。")
    try:
        return archive.read(info)
    except (KeyError, RuntimeError, OSError) as exc:
        raise InvalidEpubError("EPUB 的内容清单损坏，无法读取。") from exc


def _parse_xml(data: bytes) -> ElementTree.Element:
    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise InvalidEpubError("EPUB 的内容清单损坏，无法读取。") from exc


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_first(root: ElementTree.Element, name: str) -> ElementTree.Element | None:
    for element in root.iter():
        if _local_name(element.tag) == name:
            return element
    return None


def _first_text(root: ElementTree.Element | None, name: str) -> str | None:
    if root is None:
        return None
    for element in root.iter():
        if _local_name(element.tag) == name:
            value = (element.text or "").strip()
            if value:
                return value
    return None


def _optional_text(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    return value[:limit]


def _safe_member_path(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.replace("\\", "/").lstrip("/")
    if not normalized or "://" in normalized:
        return None
    parts = PurePosixPath(normalized).parts
    if not parts or ".." in parts:
        return None
    return normalized


def _validate_epub_id(epub_id: str) -> str:
    if not EPUB_ID_RE.fullmatch(epub_id):
        raise EpubNotFoundError("EPUB ID 无效，请重新上传。")
    return epub_id


def _safe_filename(filename: str | None) -> str:
    name = (filename or "book.epub").replace("\\", "/").split("/")[-1]
    name = name.replace("\x00", "").strip()
    return (name or "book.epub")[:255]
