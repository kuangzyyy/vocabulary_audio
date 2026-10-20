"""System endpoints."""

from fastapi import APIRouter

from backend.app import APP_VERSION

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    """Return a small, dependency-free health response for environment checks."""
    return {
        "status": "ok",
        "service": "vocabulary-audio",
        "version": APP_VERSION,
    }
