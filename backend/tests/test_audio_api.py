"""API tests for word audio lookup and cached file serving."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api.audio import get_audio_service
from backend.app.main import app
from backend.app.services.audio_provider import AudioCandidate, ProviderLookup
from backend.app.services.audio_service import AudioService
from backend.app.services.errors import AudioUpstreamError


class FakeProvider:
    def __init__(self, lookup: ProviderLookup | Exception) -> None:
        self.lookup_result = lookup

    def lookup(self, word: str) -> ProviderLookup:
        if isinstance(self.lookup_result, Exception):
            raise self.lookup_result
        return self.lookup_result


def make_candidate(accent: str) -> AudioCandidate:
    return AudioCandidate(
        title=f"File:En-{accent}-hello.ogg",
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


def build_service(cache_dir: Path, lookup: ProviderLookup | Exception) -> AudioService:
    def fake_download(url: str, destination: Path, max_bytes: int) -> None:
        destination.write_bytes(b"ID3fake-audio")

    return AudioService(
        cache_dir,
        provider=FakeProvider(lookup),
        downloader=fake_download,
    )


@pytest.fixture
def audio_client(tmp_path: Path):
    lookup = ProviderLookup(
        candidates=[make_candidate("us"), make_candidate("uk")],
        available_accents=["us", "uk"],
    )
    service = build_service(tmp_path / "audio_cache", lookup)
    app.dependency_overrides[get_audio_service] = lambda: service
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_word_audio_response_and_cached_file(audio_client: TestClient) -> None:
    response = audio_client.get("/api/audio/word", params={"text": "hello"})

    assert response.status_code == 200
    data = response.json()
    assert data["word"] == "hello"
    assert data["accent"] == "us"
    assert data["available_accents"] == ["us", "uk"]
    assert data["provider"] == "Wikimedia Commons"
    assert data["license"] == "CC BY-SA 3.0"
    assert data["attribution"] == "Tester"
    assert data["cached"] is False
    assert data["audio_url"].startswith("/api/audio/cache/")

    audio = audio_client.get(data["audio_url"])
    assert audio.status_code == 200
    assert audio.headers["content-type"].startswith("audio/mpeg")
    assert audio.headers["cache-control"].startswith("public")
    assert audio.content == b"ID3fake-audio"

    cached = audio_client.get("/api/audio/word", params={"text": "hello"})
    assert cached.status_code == 200
    assert cached.json()["cached"] is True


def test_explicit_uk_accent(audio_client: TestClient) -> None:
    response = audio_client.get(
        "/api/audio/word",
        params={"text": "hello", "accent": "uk"},
    )

    assert response.status_code == 200
    assert response.json()["accent"] == "uk"
    assert response.json()["available_accents"] == ["us", "uk"]


def test_missing_recording_returns_404(tmp_path: Path) -> None:
    service = build_service(
        tmp_path / "audio_cache",
        ProviderLookup(candidates=[], available_accents=[]),
    )
    app.dependency_overrides[get_audio_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get("/api/audio/word", params={"text": "rotated"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "没有找到" in response.json()["detail"]


def test_invalid_word_returns_400(tmp_path: Path) -> None:
    service = build_service(
        tmp_path / "audio_cache",
        ProviderLookup(candidates=[], available_accents=[]),
    )
    app.dependency_overrides[get_audio_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get("/api/audio/word", params={"text": "hello!"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "英文单词" in response.json()["detail"]


def test_upstream_failure_returns_502(tmp_path: Path) -> None:
    service = build_service(
        tmp_path / "audio_cache",
        AudioUpstreamError("upstream down"),
    )
    app.dependency_overrides[get_audio_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get("/api/audio/word", params={"text": "hello"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert "upstream down" in response.json()["detail"]


def test_invalid_cache_id_returns_404(audio_client: TestClient) -> None:
    response = audio_client.get("/api/audio/cache/not-a-cache-id")

    assert response.status_code == 404
    assert "缓存" in response.json()["detail"]
