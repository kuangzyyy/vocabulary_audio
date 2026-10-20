"""Photo upload, OCR data and image file endpoints."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.responses import FileResponse

from backend.app.config import get_settings
from backend.app.models.schemas import PhotoData
from backend.app.services.photo_ocr import PhotoOcrService

router = APIRouter(prefix="/api/photos", tags=["photos"])


@lru_cache
def get_photo_service() -> PhotoOcrService:
    """Return the process-wide OCR service; it reuses the loaded models."""
    settings = get_settings()
    return PhotoOcrService(
        settings.data_dir,
        max_upload_bytes=settings.max_photo_bytes,
    )


@router.post("", response_model=PhotoData, status_code=201)
async def upload_photo(
    file: UploadFile = File(...),
    service: PhotoOcrService = Depends(get_photo_service),
) -> PhotoData:
    return await service.create_photo(file)


@router.get("/{photo_id}/file")
def get_photo_file(
    photo_id: str,
    service: PhotoOcrService = Depends(get_photo_service),
) -> FileResponse:
    path = service.get_photo_path(photo_id)
    return FileResponse(path, media_type="image/jpeg")


@router.delete("/{photo_id}", status_code=204)
def delete_photo(
    photo_id: str,
    service: PhotoOcrService = Depends(get_photo_service),
) -> Response:
    service.delete_photo(photo_id)
    return Response(status_code=204)
