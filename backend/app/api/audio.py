"""Word pronunciation endpoints backed by Wikimedia Commons and local cache."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from backend.app.config import get_settings
from backend.app.models.schemas import WordAudioInfo
from backend.app.services.audio_service import AudioService

router = APIRouter(prefix="/api/audio", tags=["audio"])


@lru_cache
def get_audio_service() -> AudioService:
    """Return the process-wide audio service so cache locks are shared."""
    settings = get_settings()
    return AudioService(
        settings.data_dir / "audio_cache",
        user_agent=settings.audio_user_agent,
        max_bytes=settings.audio_max_bytes,
        timeout=settings.audio_timeout_seconds,
        use_proxy=settings.audio_use_proxy,
    )


@router.get("/word", response_model=WordAudioInfo)
def get_word_audio(
    text: str = Query(..., min_length=1, max_length=64),
    accent: str = Query("auto", pattern="^(auto|us|uk)$"),
    service: AudioService = Depends(get_audio_service),
) -> WordAudioInfo:
    resolved = service.resolve(text, accent)
    return WordAudioInfo(
        word=resolved.word,
        accent=resolved.accent,
        available_accents=resolved.available_accents,
        audio_url=f"/api/audio/cache/{resolved.cache_id}",
        source_page=resolved.source_page,
        provider=resolved.provider,
        license=resolved.license_name,
        license_url=resolved.license_url,
        attribution=resolved.attribution,
        cached=resolved.cached,
    )


@router.get("/cache/{cache_id}")
def get_audio_file(
    cache_id: str,
    service: AudioService = Depends(get_audio_service),
) -> FileResponse:
    audio_path, mime = service.get_cached_audio(cache_id)
    return FileResponse(
        audio_path,
        media_type=mime,
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Disposition": "inline",
        },
    )
