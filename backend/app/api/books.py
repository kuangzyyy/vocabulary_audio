"""Book upload, file serving and page data endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse

from backend.app.config import get_settings
from backend.app.models.schemas import BookInfo, PageData
from backend.app.services.books import BookService

router = APIRouter(prefix="/api/books", tags=["books"])


def get_book_service() -> BookService:
    """Build a book service for the configured local data directory."""
    settings = get_settings()
    return BookService(settings.data_dir, settings.max_upload_bytes)


@router.post("", response_model=BookInfo, status_code=201)
async def upload_book(
    file: UploadFile = File(...),
    service: BookService = Depends(get_book_service),
) -> BookInfo:
    return await service.create_book(file)


@router.get("/{book_id}/file")
def get_book_file(
    book_id: str,
    service: BookService = Depends(get_book_service),
) -> FileResponse:
    _, pdf_path = service.get_pdf_path(book_id)
    return FileResponse(pdf_path, media_type="application/pdf")


@router.get("/{book_id}/pages/{page_number}", response_model=PageData)
def get_page(
    book_id: str,
    page_number: int,
    service: BookService = Depends(get_book_service),
) -> PageData:
    return service.get_page(book_id, page_number)
