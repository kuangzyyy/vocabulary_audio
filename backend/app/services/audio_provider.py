"""Resolve human word pronunciations from Wikimedia Commons.

Wikimedia Commons is used through its official MediaWiki API. Only files with a
clear free license and a known human-recording naming pattern are accepted.
No HTML scraping, no TTS, and no API keys are involved.
"""

from __future__ import annotations

import html
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

from backend.app.services.errors import AudioUpstreamError
from backend.app.services.wikimedia_http import get_json

COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"
COMMONS_FILE_BASE = "https://commons.wikimedia.org/wiki/"
UPLOAD_HOST = "upload.wikimedia.org"
PROVIDER_NAME = "Wikimedia Commons"

ACCENT_ORDER = {"us": 0, "uk": 1, "unknown": 2}
TTS_MARKERS = (
    "text-to-speech",
    "text to speech",
    "synthetic speech",
    "speech synthesis",
    "espeak",
    "festival tts",
    "google translate",
    "microsoft speech",
    "tts-",
    "tts_",
)
AUDIO_EXTENSIONS = ("ogg", "oga", "wav", "mp3", "flac")


@dataclass(frozen=True)
class AudioCandidate:
    """One downloadable pronunciation file with its legal metadata."""

    title: str
    accent: str
    audio_url: str
    source_page: str
    mime: str
    license_name: str
    license_url: str | None
    attribution: str | None
    original_url: str | None = None


@dataclass(frozen=True)
class ProviderLookup:
    candidates: list[AudioCandidate]
    available_accents: list[str]


def candidate_from_page(page: dict[str, Any]) -> AudioCandidate | None:
    """Convert one MediaWiki page object into a usable audio candidate."""
    info_list = page.get("videoinfo") or page.get("imageinfo") or []
    if not isinstance(info_list, list) or not info_list:
        return None
    info = info_list[0]
    if not isinstance(info, dict):
        return None

    title = str(page.get("title") or "").strip()
    accent = _accent_from_title(title)
    if accent is None:
        return None

    metadata = info.get("extmetadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    description = _meta_value(metadata, "ImageDescription")
    categories = _meta_value(metadata, "Categories")
    if _looks_synthetic(title, description, categories):
        return None

    license_name = _meta_value(metadata, "LicenseShortName") or _meta_value(
        metadata, "License"
    )
    if not is_acceptable_license(license_name):
        return None

    audio = _select_audio(info)
    if audio is None:
        return None
    audio_url, mime = audio

    original_url = str(info.get("url") or "").strip() or None
    source_page = _source_page(info, title)
    if source_page is None:
        return None

    license_url = _meta_value(metadata, "LicenseUrl") or None
    if license_url is not None and not _is_http_url(license_url):
        license_url = None

    attribution = _clean_html(
        _meta_value(metadata, "Artist") or _meta_value(metadata, "Credit")
    )
    attribution = attribution or None

    return AudioCandidate(
        title=title,
        accent=accent,
        audio_url=audio_url,
        source_page=source_page,
        mime=mime,
        license_name=_clean_html(license_name),
        license_url=license_url,
        attribution=attribution,
        original_url=original_url,
    )


def is_acceptable_license(name: str) -> bool:
    """Return True only for clear free licenses compatible with local reuse."""
    value = (name or "").strip().lower()
    if not value:
        return False
    if re.search(r"\b(nc|nd)\b|non-?commercial|no[- ]deriv", value):
        return False
    if "public domain" in value or value in {"pd", "cc0", "cc-0"}:
        return True
    if "cc0" in value:
        return True
    if "cc by" in value or "cc-by" in value:
        return True
    return False


def available_accents(candidates: list[AudioCandidate]) -> list[str]:
    unique = {candidate.accent for candidate in candidates}
    return sorted(unique, key=lambda accent: ACCENT_ORDER.get(accent, 99))


class WikimediaCommonsProvider:
    """Small, throttled client for the Wikimedia Commons audio API."""

    def __init__(
        self,
        user_agent: str,
        *,
        timeout: float = 20.0,
        throttle_seconds: float = 0.5,
        cache_ttl_seconds: float = 3600.0,
        negative_ttl_seconds: float = 300.0,
        use_proxy: bool = False,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.throttle_seconds = max(0.0, throttle_seconds)
        self.cache_ttl_seconds = cache_ttl_seconds
        self.negative_ttl_seconds = negative_ttl_seconds
        self.use_proxy = use_proxy

        self._lookup_cache: dict[str, tuple[float, ProviderLookup]] = {}
        self._cache_lock = threading.Lock()
        self._request_lock = threading.Lock()
        self._last_request_at = 0.0

    def lookup(self, word: str) -> ProviderLookup:
        """Find licensed candidates for a normalized English word."""
        now = time.monotonic()
        with self._cache_lock:
            cached = self._lookup_cache.get(word)
            if cached is not None and cached[0] > now:
                return cached[1]

        candidates = self._lookup_exact(word)
        if not candidates:
            candidates = self._lookup_search(word)

        candidates = _deduplicate(candidates)
        candidates.sort(key=lambda item: (ACCENT_ORDER.get(item.accent, 99), item.title.lower()))
        result = ProviderLookup(
            candidates=candidates,
            available_accents=available_accents(candidates),
        )

        ttl = self.cache_ttl_seconds if candidates else self.negative_ttl_seconds
        with self._cache_lock:
            self._lookup_cache[word] = (time.monotonic() + ttl, result)
        return result

    def _lookup_exact(self, word: str) -> list[AudioCandidate]:
        titles: list[str] = []
        for prefixes in (("us",), ("uk", "gb")):
            for prefix in prefixes:
                for extension in AUDIO_EXTENSIONS:
                    titles.append(f"File:En-{prefix}-{word}.{extension}")

        payload = self._api_get(
            {
                "titles": "|".join(titles),
                "prop": "videoinfo",
                "viprop": "url|mime|derivatives|extmetadata",
            }
        )
        return _candidates_from_payload(payload)

    def _lookup_search(self, word: str) -> list[AudioCandidate]:
        payload = self._api_get(
            {
                "generator": "search",
                "gsrsearch": f"intitle:{word} filetype:audio",
                "gsrnamespace": "6",
                "gsrlimit": "10",
                "prop": "videoinfo",
                "viprop": "url|mime|derivatives|extmetadata",
            }
        )
        low_word = word.lower()
        return [
            candidate
            for candidate in _candidates_from_payload(payload)
            if low_word in candidate.title.lower()
        ]

    def _api_get(self, params: dict[str, str]) -> dict[str, Any]:
        query = {"action": "query", "format": "json", "formatversion": "2", **params}
        url = f"{COMMONS_API_URL}?{urllib.parse.urlencode(query)}"

        with self._request_lock:
            wait_seconds = self.throttle_seconds - (
                time.monotonic() - self._last_request_at
            )
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            self._last_request_at = time.monotonic()
            payload = get_json(
                url,
                user_agent=self.user_agent,
                timeout=self.timeout,
                use_proxy=self.use_proxy,
            )

        if payload.get("error"):
            raise AudioUpstreamError("Wikimedia Commons 音频查询失败。")
        return payload


def _candidates_from_payload(payload: dict[str, Any]) -> list[AudioCandidate]:
    query = payload.get("query") or {}
    pages = query.get("pages") or []
    if not isinstance(pages, list):
        return []
    candidates: list[AudioCandidate] = []
    for page in pages:
        if not isinstance(page, dict) or page.get("missing"):
            continue
        candidate = candidate_from_page(page)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _select_audio(info: dict[str, Any]) -> tuple[str, str] | None:
    derivatives = info.get("derivatives") or []
    if isinstance(derivatives, list):
        for derivative in derivatives:
            if not isinstance(derivative, dict):
                continue
            mime = str(derivative.get("type") or "").lower()
            src = str(derivative.get("src") or "").strip()
            if src and "mpeg" in mime and _is_upload_url(src):
                return src, "audio/mpeg"

        for derivative in derivatives:
            if not isinstance(derivative, dict):
                continue
            mime = str(derivative.get("type") or "").lower()
            src = str(derivative.get("src") or "").strip()
            if src and mime.startswith("audio/") and _is_upload_url(src):
                return src, mime.split(";")[0]

    original = str(info.get("url") or "").strip()
    if original and _is_upload_url(original):
        return original, _normalize_mime(str(info.get("mime") or ""))

    return None


def _accent_from_title(title: str) -> str | None:
    lowered = title.lower()
    if lowered.startswith("file:en-us-"):
        return "us"
    if lowered.startswith("file:en-uk-") or lowered.startswith("file:en-gb-"):
        return "uk"
    if lowered.startswith("file:ll-q1860 (eng)-"):
        return "unknown"
    return None


def _looks_synthetic(title: str, description: str, categories: str) -> bool:
    haystack = f"{title} {description} {categories}".lower()
    return any(marker in haystack for marker in TTS_MARKERS)


def _meta_value(metadata: dict[str, Any], key: str) -> str:
    item = metadata.get(key)
    if isinstance(item, dict):
        item = item.get("value")
    if item is None:
        return ""
    return str(item).strip()


def _clean_html(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:300]


def _source_page(info: dict[str, Any], title: str) -> str | None:
    source = str(info.get("descriptionurl") or "").strip()
    if source and _is_http_url(source):
        return source
    if not title:
        return None
    return COMMONS_FILE_BASE + urllib.parse.quote(title.replace(" ", "_"))


def _is_upload_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == UPLOAD_HOST


def _is_http_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _normalize_mime(mime: str) -> str:
    lowered = mime.lower().strip()
    if lowered in {"application/ogg", "application/x-ogg"}:
        return "audio/ogg"
    if lowered in {"audio/x-wav", "audio/wave"}:
        return "audio/wav"
    return lowered or "application/octet-stream"


def _deduplicate(candidates: list[AudioCandidate]) -> list[AudioCandidate]:
    seen: set[str] = set()
    unique: list[AudioCandidate] = []
    for candidate in candidates:
        key = candidate.title.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique
