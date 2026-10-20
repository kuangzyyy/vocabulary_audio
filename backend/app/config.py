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


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES


@lru_cache
def get_settings() -> Settings:
    data_dir = Path(
        os.environ.get("VOCABULARY_AUDIO_DATA_DIR", str(DEFAULT_DATA_DIR))
    ).expanduser()
    max_upload_bytes = int(
        os.environ.get("VOCABULARY_AUDIO_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
    )
    return Settings(
        data_dir=data_dir.resolve(),
        max_upload_bytes=max_upload_bytes,
    )
