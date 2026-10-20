"""Word pronunciation endpoints backed by Wikimedia Commons and local cache."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from backend.app.config import get_settings
from backend.app.models.schemas import SentenceAudioInfo, WordAudioInfo
from backend.app.services.audio_service import AudioService
from backend.app.services.sentence_audio import SYNTHETIC_NOTE, SentenceAudioService

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


@lru_cache
def get_sentence_service() -> SentenceAudioService:
    """Return the process-wide sentence TTS service."""
    settings = get_settings()
    return SentenceAudioService(
        settings.data_dir / "audio_cache",
        max_chars=settings.sentence_max_chars,
        tts_timeout=settings.tts_timeout_seconds,
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


@router.get("/sentence", response_model=SentenceAudioInfo)
def get_sentence_audio(
    text: str = Query(..., min_length=1),
    service: SentenceAudioService = Depends(get_sentence_service),
) -> SentenceAudioInfo:
    resolved = service.resolve(text)
    return SentenceAudioInfo(
        text=resolved.text,
        synthetic=resolved.synthetic,
        engine=resolved.engine,
        voice=resolved.voice,
        locale=resolved.locale,
        audio_url=f"/api/audio/cache/{resolved.cache_id}",
        cached=resolved.cached,
        note=SYNTHETIC_NOTE,
    )
