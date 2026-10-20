"""FastAPI application entry point.

Current API surface: health, PDF books, EPUB books, word/sentence audio, and
local photo OCR. The app stays local-first and binds to 127.0.0.1 by default.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app import APP_VERSION
from backend.app.api.audio import router as audio_router
from backend.app.api.books import router as books_router
from backend.app.api.epubs import router as epubs_router
from backend.app.api.health import router as health_router
from backend.app.api.photos import router as photos_router
from backend.app.logging_utils import install_access_log_filter
from backend.app.services.errors import AudioError, EpubError, PdfError, PhotoError

install_access_log_filter()

app = FastAPI(
    title="Vocabulary Audio",
    description="Local-first English reading and pronunciation helper.",
    version=APP_VERSION,
)

# The Vite dev server proxies /api to this backend, so CORS is only relevant
# when the frontend calls the API directly during local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(PdfError)
async def pdf_error_handler(request: Request, exc: PdfError) -> JSONResponse:
    """Return predictable JSON errors for upload and extraction failures."""
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(AudioError)
async def audio_error_handler(request: Request, exc: AudioError) -> JSONResponse:
    """Return predictable JSON errors for audio lookup and download failures."""
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(PhotoError)
async def photo_error_handler(request: Request, exc: PhotoError) -> JSONResponse:
    """Return predictable JSON errors for photo validation and OCR failures."""
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(EpubError)
async def epub_error_handler(request: Request, exc: EpubError) -> JSONResponse:
    """Return predictable JSON errors for EPUB validation failures."""
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


app.include_router(health_router)
app.include_router(books_router)
app.include_router(epubs_router)
app.include_router(audio_router)
app.include_router(photos_router)
