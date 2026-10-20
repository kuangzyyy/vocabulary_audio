"""Application settings.

The data directory can be overridden with VOCABULARY_AUDIO_DATA_DIR, which keeps
tests and local experiments away from the real user data folder.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_MAX_UPLOAD_BYTES = 100 * 1024 * 1024
DEFAULT_AUDIO_USER_AGENT = "VocabularyAudio/0.1 (local educational project)"
DEFAULT_AUDIO_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_AUDIO_TIMEOUT_SECONDS = 20.0
DEFAULT_AUDIO_USE_PROXY = False
DEFAULT_SENTENCE_MAX_CHARS = 500
DEFAULT_TTS_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_PHOTO_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_EPUB_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    audio_user_agent: str = DEFAULT_AUDIO_USER_AGENT
    audio_max_bytes: int = DEFAULT_AUDIO_MAX_BYTES
    audio_timeout_seconds: float = DEFAULT_AUDIO_TIMEOUT_SECONDS
    audio_use_proxy: bool = DEFAULT_AUDIO_USE_PROXY
    sentence_max_chars: int = DEFAULT_SENTENCE_MAX_CHARS
    tts_timeout_seconds: float = DEFAULT_TTS_TIMEOUT_SECONDS
    max_photo_bytes: int = DEFAULT_MAX_PHOTO_BYTES
    max_epub_bytes: int = DEFAULT_MAX_EPUB_BYTES


@lru_cache
def get_settings() -> Settings:
    data_dir = Path(
        os.environ.get("VOCABULARY_AUDIO_DATA_DIR", str(DEFAULT_DATA_DIR))
    ).expanduser()
    max_upload_bytes = int(
        os.environ.get("VOCABULARY_AUDIO_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
    )
    audio_user_agent = os.environ.get(
        "VOCABULARY_AUDIO_USER_AGENT", DEFAULT_AUDIO_USER_AGENT
    )
    audio_max_bytes = int(
        os.environ.get("VOCABULARY_AUDIO_AUDIO_MAX_BYTES", str(DEFAULT_AUDIO_MAX_BYTES))
    )
    audio_timeout_seconds = float(
        os.environ.get(
            "VOCABULARY_AUDIO_AUDIO_TIMEOUT_SECONDS",
            str(DEFAULT_AUDIO_TIMEOUT_SECONDS),
        )
    )
    audio_use_proxy = os.environ.get(
        "VOCABULARY_AUDIO_USE_PROXY", str(int(DEFAULT_AUDIO_USE_PROXY))
    ).lower() in {"1", "true", "yes", "on"}
    sentence_max_chars = int(
        os.environ.get(
            "VOCABULARY_AUDIO_SENTENCE_MAX_CHARS", str(DEFAULT_SENTENCE_MAX_CHARS)
        )
    )
    tts_timeout_seconds = float(
        os.environ.get(
            "VOCABULARY_AUDIO_TTS_TIMEOUT_SECONDS", str(DEFAULT_TTS_TIMEOUT_SECONDS)
        )
    )
    max_photo_bytes = int(
        os.environ.get(
            "VOCABULARY_AUDIO_MAX_PHOTO_BYTES", str(DEFAULT_MAX_PHOTO_BYTES)
        )
    )
    max_epub_bytes = int(
        os.environ.get(
            "VOCABULARY_AUDIO_MAX_EPUB_BYTES", str(DEFAULT_MAX_EPUB_BYTES)
        )
    )
    return Settings(
        data_dir=data_dir.resolve(),
        max_upload_bytes=max_upload_bytes,
        audio_user_agent=audio_user_agent,
        audio_max_bytes=audio_max_bytes,
        audio_timeout_seconds=audio_timeout_seconds,
        audio_use_proxy=audio_use_proxy,
        sentence_max_chars=sentence_max_chars,
        tts_timeout_seconds=tts_timeout_seconds,
        max_photo_bytes=max_photo_bytes,
        max_epub_bytes=max_epub_bytes,
    )
