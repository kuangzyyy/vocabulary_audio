"""Resolve word audio, download it once, and serve it from a local cache."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from backend.app.services.audio_provider import (
    ACCENT_ORDER,
    PROVIDER_NAME,
    AudioCandidate,
    ProviderLookup,
    WikimediaCommonsProvider,
)
from backend.app.services.errors import (
    AudioCacheError,
    AudioRateLimitedError,
    AudioUnavailableError,
    AudioUpstreamError,
    InvalidWordError,
)
from backend.app.services.wikimedia_http import download as http_download

WORD_RE = re.compile(r"^[A-Za-z]+(?:['\-][A-Za-z]+)*$")
CACHE_ID_RE = re.compile(r"^[0-9a-f]{64}$")
ACCENT_LABELS = {
    "us": "美式发音",
    "uk": "英式发音",
    "unknown": "未标注口音的录音",
}


class AudioProvider(Protocol):
    def lookup(self, word: str) -> ProviderLookup:
        """Return licensed audio candidates for a normalized word."""


Downloader = Callable[[str, Path, int], None]


@dataclass(frozen=True)
class ResolvedAudio:
    cache_id: str
    word: str
    accent: str
    available_accents: list[str]
    source_page: str
    provider: str
    license_name: str
    license_url: str | None
    attribution: str | None
    mime: str
    cached: bool


class AudioService:
    """Provider + disk cache + polite throttling for pronunciation audio."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        provider: AudioProvider | None = None,
        downloader: Downloader | None = None,
        user_agent: str = "VocabularyAudio/0.1 (local educational project)",
        max_bytes: int = 10 * 1024 * 1024,
        timeout: float = 20.0,
        provider_throttle_seconds: float = 0.5,
        use_proxy: bool = False,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.timeout = timeout
        self.user_agent = user_agent
        self.use_proxy = use_proxy
        self.provider = provider or WikimediaCommonsProvider(
            user_agent,
            timeout=timeout,
            throttle_seconds=provider_throttle_seconds,
            use_proxy=use_proxy,
        )
        self.downloader: Downloader = downloader or self._download
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def resolve(self, word: str, accent: str = "auto") -> ResolvedAudio:
        """Return cached audio or download a licensed candidate exactly once."""
        normalized = normalize_word(word)
        lock = self._lock_for(normalized)
        with lock:
            cached = self._find_cached(normalized, accent)
            if cached is not None:
                return cached

            lookup = self.provider.lookup(normalized)
            candidate = select_candidate(lookup, accent)
            if candidate is None:
                raise AudioUnavailableError(
                    _missing_message(normalized, accent, lookup.available_accents)
                )

            return self._store_candidate(normalized, candidate, lookup.available_accents)

    def get_cached_audio(self, cache_id: str) -> tuple[Path, str]:
        """Resolve a validated cache id to a local file and MIME type."""
        if not CACHE_ID_RE.fullmatch(cache_id):
            raise AudioUnavailableError("音频缓存 ID 无效。")
        metadata = self._read_metadata(cache_id)
        if metadata is None:
            raise AudioUnavailableError("音频缓存不存在，请重新点击单词。")

        cache_file = str(metadata.get("cache_file") or "")
        if not cache_file or "/" in cache_file or "\\" in cache_file:
            raise AudioUnavailableError("音频缓存记录无效。")
        if not cache_file.startswith(f"{cache_id}."):
            raise AudioUnavailableError("音频缓存记录无效。")

        audio_path = self.cache_dir / cache_file
        if not audio_path.is_file():
            raise AudioUnavailableError("音频缓存文件丢失，请重新点击单词。")

        mime = str(metadata.get("mime") or "audio/mpeg")
        return audio_path, mime

    def _lock_for(self, word: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(word)
            if lock is None:
                lock = threading.Lock()
                self._locks[word] = lock
            return lock

    def _find_cached(self, word: str, accent: str) -> ResolvedAudio | None:
        accents = ACCENT_ORDER if accent == "auto" else (accent,)
        for candidate_accent in accents:
            cache_id = _cache_key(word, candidate_accent)
            metadata = self._read_metadata(cache_id)
            if metadata is None:
                continue
            if metadata.get("word") != word:
                continue
            if metadata.get("accent") != candidate_accent:
                continue
            cache_file = str(metadata.get("cache_file") or "")
            if not cache_file or not cache_file.startswith(f"{cache_id}."):
                continue
            if "/" in cache_file or "\\" in cache_file:
                continue
            if not (self.cache_dir / cache_file).is_file():
                continue
            return _resolved_from_metadata(cache_id, metadata, cached=True)
        return None

    def _store_candidate(
        self,
        word: str,
        candidate: AudioCandidate,
        available: list[str],
    ) -> ResolvedAudio:
        cache_id = _cache_key(word, candidate.accent)
        suffix = _suffix_for(candidate.mime, candidate.audio_url)
        audio_path = self.cache_dir / f"{cache_id}{suffix}"
        metadata_path = self.cache_dir / f"{cache_id}.json"
        temp_audio = self.cache_dir / f".{cache_id}.audio.part"
        temp_metadata = self.cache_dir / f".{cache_id}.json.part"

        try:
            self.downloader(candidate.audio_url, temp_audio, self.max_bytes)
            if not temp_audio.is_file():
                raise AudioCacheError("音频下载失败：没有生成缓存文件。")
            size = temp_audio.stat().st_size
            if size <= 0:
                raise AudioCacheError("音频下载失败：文件为空。")
            if size > self.max_bytes:
                raise AudioCacheError("音频文件过大，已拒绝缓存。")

            metadata = {
                "cache_version": 1,
                "word": word,
                "accent": candidate.accent,
                "available_accents": available,
                "cache_file": audio_path.name,
                "mime": candidate.mime,
                "provider": PROVIDER_NAME,
                "title": candidate.title,
                "source_page": candidate.source_page,
                "audio_url": candidate.audio_url,
                "original_url": candidate.original_url,
                "license": candidate.license_name,
                "license_url": candidate.license_url,
                "attribution": candidate.attribution,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            temp_metadata.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            temp_audio.replace(audio_path)
            temp_metadata.replace(metadata_path)
            return _resolved_from_metadata(cache_id, metadata, cached=False)
        except Exception:
            temp_audio.unlink(missing_ok=True)
            temp_metadata.unlink(missing_ok=True)
            audio_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
            raise

    def _read_metadata(self, cache_id: str) -> dict[str, object] | None:
        path = self.cache_dir / f"{cache_id}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def _download(self, url: str, destination: Path, max_bytes: int) -> None:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "upload.wikimedia.org":
            raise AudioUpstreamError("音频地址不在允许的来源范围内。")

        try:
            http_download(
                url,
                destination,
                user_agent=self.user_agent,
                timeout=self.timeout,
                max_bytes=max_bytes,
                use_proxy=self.use_proxy,
            )
        except AudioRateLimitedError as exc:
            destination.unlink(missing_ok=True)
            delay = min(max(exc.retry_after or 5.0, 1.0), 12.0)
            time.sleep(delay)
            http_download(
                url,
                destination,
                user_agent=self.user_agent,
                timeout=self.timeout,
                max_bytes=max_bytes,
                use_proxy=self.use_proxy,
            )

        self._validate_audio_file(destination, max_bytes)

    @staticmethod
    def _validate_audio_file(destination: Path, max_bytes: int) -> None:
        if not destination.is_file():
            raise AudioUpstreamError("音频源没有返回文件。")
        size = destination.stat().st_size
        if size <= 0:
            raise AudioUpstreamError("音频源返回了空文件。")
        if size > max_bytes:
            destination.unlink(missing_ok=True)
            raise AudioUpstreamError("音频文件过大，已拒绝缓存。")

        with destination.open("rb") as handle:
            header = handle.read(12)
        looks_audio = (
            header.startswith(b"ID3")
            or header[:1] == b"\xff"
            or header.startswith(b"OggS")
            or header.startswith(b"RIFF")
            or header.startswith(b"fLaC")
        )
        if not looks_audio:
            destination.unlink(missing_ok=True)
            raise AudioUpstreamError("音频源返回的内容不是有效音频。")


def normalize_word(word: str) -> str:
    """Normalize a display word into a safe lowercase lookup key."""
    value = (word or "").strip().replace("’", "'")
    if len(value) > 64 or not WORD_RE.fullmatch(value):
        raise InvalidWordError("请输入一个英文单词（只包含字母、连字符或撇号）。")
    return value.lower()


def select_candidate(
    lookup: ProviderLookup,
    accent: str,
) -> AudioCandidate | None:
    """Choose a candidate without inventing accents that do not exist."""
    if accent == "auto":
        for wanted in ACCENT_ORDER:
            for candidate in lookup.candidates:
                if candidate.accent == wanted:
                    return candidate
        return None
    for candidate in lookup.candidates:
        if candidate.accent == accent:
            return candidate
    return None


def _missing_message(word: str, accent: str, available: list[str]) -> str:
    if accent == "auto" or not available:
        return f"没有找到“{word}”的可合法使用真人录音。"
    agreed = "、".join(ACCENT_LABELS.get(item, item) for item in available)
    return f"没有找到{ACCENT_LABELS.get(accent, accent)}；可用：{agreed}。"


def _cache_key(word: str, accent: str) -> str:
    raw = f"wikimedia-commons|v1|{word}|{accent}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _suffix_for(mime: str, url: str) -> str:
    lowered_mime = (mime or "").lower()
    path = urllib.parse.urlparse(url).path.lower()
    if "mpeg" in lowered_mime or path.endswith(".mp3"):
        return ".mp3"
    if "ogg" in lowered_mime or path.endswith((".ogg", ".oga")):
        return ".ogg"
    if "wav" in lowered_mime or path.endswith(".wav"):
        return ".wav"
    if "flac" in lowered_mime or path.endswith(".flac"):
        return ".flac"
    return ".audio"


def _resolved_from_metadata(
    cache_id: str,
    metadata: dict[str, object],
    *,
    cached: bool,
) -> ResolvedAudio:
    raw_available = metadata.get("available_accents")
    available = (
        [str(item) for item in raw_available]
        if isinstance(raw_available, list)
        else [str(metadata.get("accent") or "unknown")]
    )
    return ResolvedAudio(
        cache_id=cache_id,
        word=str(metadata.get("word") or ""),
        accent=str(metadata.get("accent") or "unknown"),
        available_accents=available,
        source_page=str(metadata.get("source_page") or ""),
        provider=str(metadata.get("provider") or PROVIDER_NAME),
        license_name=str(metadata.get("license") or ""),
        license_url=(
            str(metadata["license_url"]) if metadata.get("license_url") else None
        ),
        attribution=(
            str(metadata["attribution"]) if metadata.get("attribution") else None
        ),
        mime=str(metadata.get("mime") or "audio/mpeg"),
        cached=cached,
    )
