"""Tests for audio candidate selection and the local disk cache."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.services.audio_provider import (
    AudioCandidate,
    ProviderLookup,
)
from backend.app.services.audio_service import AudioService
from backend.app.services.errors import (
    AudioUnavailableError,
    AudioUpstreamError,
    InvalidWordError,
)


class FakeProvider:
    def __init__(self, lookup: ProviderLookup | Exception) -> None:
        self.lookup_result = lookup
        self.calls = 0

    def lookup(self, word: str) -> ProviderLookup:
        self.calls += 1
        if isinstance(self.lookup_result, Exception):
            raise self.lookup_result
        return self.lookup_result


def make_candidate(accent: str = "us", title: str | None = None) -> AudioCandidate:
    return AudioCandidate(
        title=title or f"File:En-{accent}-hello.ogg",
        accent=accent,
        audio_url=(
            "https://upload.wikimedia.org/wikipedia/commons/transcoded/"
            "5/52/Example.ogg/Example.ogg.mp3"
        ),
        source_page="https://commons.wikimedia.org/wiki/File:Example.ogg",
        mime="audio/mpeg",
        license_name="CC BY-SA 3.0",
        license_url="https://creativecommons.org/licenses/by-sa/3.0/",
        attribution="Tester",
        original_url="https://upload.wikimedia.org/wikipedia/commons/5/52/Example.ogg",
    )


def make_service(
    tmp_path: Path,
    lookup: ProviderLookup,
) -> tuple[AudioService, FakeProvider, list[str]]:
    downloads: list[str] = []

    def fake_download(url: str, destination: Path, max_bytes: int) -> None:
        downloads.append(url)
        destination.write_bytes(b"ID3fake-audio")

    provider = FakeProvider(lookup)
    service = AudioService(
        tmp_path / "audio_cache",
        provider=provider,
        downloader=fake_download,
        max_bytes=1024,
    )
    return service, provider, downloads


def test_auto_uses_us_and_caches_without_duplicate_download(tmp_path: Path) -> None:
    lookup = ProviderLookup(
        candidates=[make_candidate("us"), make_candidate("uk")],
        available_accents=["us", "uk"],
    )
    service, provider, downloads = make_service(tmp_path, lookup)

    first = service.resolve("Hello", "auto")
    assert first.accent == "us"
    assert first.available_accents == ["us", "uk"]
    assert first.cached is False
    assert first.license_name == "CC BY-SA 3.0"
    assert first.attribution == "Tester"
    assert len(downloads) == 1

    second = service.resolve("hello", "auto")
    assert second.cached is True
    assert second.cache_id == first.cache_id
    assert provider.calls == 1
    assert len(downloads) == 1

    audio_path, mime = service.get_cached_audio(first.cache_id)
    assert audio_path.read_bytes() == b"ID3fake-audio"
    assert mime == "audio/mpeg"
    assert (tmp_path / "audio_cache" / f"{first.cache_id}.json").is_file()


def test_explicit_uk_downloads_separately(tmp_path: Path) -> None:
    lookup = ProviderLookup(
        candidates=[make_candidate("us"), make_candidate("uk")],
        available_accents=["us", "uk"],
    )
    service, _, downloads = make_service(tmp_path, lookup)

    result = service.resolve("hello", "uk")
    assert result.accent == "uk"
    assert result.available_accents == ["us", "uk"]
    assert len(downloads) == 1
    assert result.cached is False


def test_missing_requested_accent_lists_available_ones(tmp_path: Path) -> None:
    lookup = ProviderLookup(
        candidates=[make_candidate("uk")],
        available_accents=["uk"],
    )
    service, _, _ = make_service(tmp_path, lookup)

    with pytest.raises(AudioUnavailableError) as exc_info:
        service.resolve("hello", "us")

    message = str(exc_info.value)
    assert "美式" in message
    assert "英式" in message


def test_no_candidates_returns_clear_error(tmp_path: Path) -> None:
    service, _, _ = make_service(
        tmp_path,
        ProviderLookup(candidates=[], available_accents=[]),
    )

    with pytest.raises(AudioUnavailableError) as exc_info:
        service.resolve("rotated", "auto")

    assert "没有找到" in str(exc_info.value)
    assert "rotated" in str(exc_info.value)


def test_invalid_word_is_rejected(tmp_path: Path) -> None:
    service, _, _ = make_service(
        tmp_path,
        ProviderLookup(candidates=[], available_accents=[]),
    )

    for word in ("hello!", "123", "", "hello world"):
        with pytest.raises(InvalidWordError):
            service.resolve(word, "auto")


def test_provider_failure_is_propagated(tmp_path: Path) -> None:
    service, _, _ = make_service(
        tmp_path,
        ProviderLookup(candidates=[], available_accents=[]),
    )
    service.provider = FakeProvider(AudioUpstreamError("upstream down"))

    with pytest.raises(AudioUpstreamError):
        service.resolve("hello", "auto")


def test_missing_cache_file_is_refetched(tmp_path: Path) -> None:
    lookup = ProviderLookup(
        candidates=[make_candidate("us")],
        available_accents=["us"],
    )
    service, _, downloads = make_service(tmp_path, lookup)

    first = service.resolve("hello", "auto")
    audio_path, _ = service.get_cached_audio(first.cache_id)
    audio_path.unlink()

    second = service.resolve("hello", "auto")
    assert second.cached is False
    assert len(downloads) == 2
    assert audio_path.is_file()


def test_invalid_cache_id_is_rejected(tmp_path: Path) -> None:
    service, _, _ = make_service(
        tmp_path,
        ProviderLookup(candidates=[], available_accents=[]),
    )

    with pytest.raises(AudioUnavailableError):
        service.get_cached_audio("not-a-cache-id")
