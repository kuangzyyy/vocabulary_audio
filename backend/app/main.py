"""FastAPI application entry point.

Phase 0 intentionally exposes only the health check. PDF, OCR and audio
routes are added in later phases.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app import APP_VERSION
from backend.app.api.health import router as health_router

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

app.include_router(health_router)
