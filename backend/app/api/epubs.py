"""EPUB upload and original-file endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse

from backend.app.config import get_settings
from backend.app.models.schemas import EpubInfo
from backend.app.services.epubs import EpubService

router = APIRouter(prefix="/api/epubs", tags=["epubs"])


def get_epub_service() -> EpubService:
    """Build an EPUB service for the configured local data directory."""
    settings = get_settings()
    return EpubService(settings.data_dir, settings.max_epub_bytes)


@router.post("", response_model=EpubInfo, status_code=201)
async def upload_epub(
    file: UploadFile = File(...),
    service: EpubService = Depends(get_epub_service),
) -> EpubInfo:
    return await service.create_epub(file)


@router.get("/{epub_id}/file")
def get_epub_file(
    epub_id: str,
    service: EpubService = Depends(get_epub_service),
) -> FileResponse:
    _, epub_path = service.get_epub_path(epub_id)
    return FileResponse(epub_path, media_type="application/epub+zip")
