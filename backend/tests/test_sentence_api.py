"""API tests for synthetic sentence audio and cached WAV serving."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api.audio import get_audio_service, get_sentence_service
from backend.app.main import app
from backend.app.services.audio_provider import ProviderLookup
from backend.app.services.audio_service import AudioService
from backend.app.services.errors import SentenceTtsError
from backend.app.services.sentence_audio import SentenceAudioService, SynthesisResult

WAV_BYTES = b"RIFF" + struct.pack("<I", 84) + b"WAVE" + b"\x00" * 84


class FakeTtsProvider:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def synthesize(self, text: str, destination: Path) -> SynthesisResult:
        if self.error is not None:
            raise self.error
        destination.write_bytes(WAV_BYTES)
        return SynthesisResult(voice="Microsoft Zira Desktop", locale="en-US")


class EmptyAudioProvider:
    def lookup(self, word: str) -> ProviderLookup:
        return ProviderLookup(candidates=[], available_accents=[])


def override_services(tmp_path: Path, provider: FakeTtsProvider):
    cache_dir = tmp_path / "audio_cache"
    sentence_service = SentenceAudioService(cache_dir, provider=provider)
    word_service = AudioService(
        cache_dir,
        provider=EmptyAudioProvider(),
        downloader=lambda *args, **kwargs: None,
    )
    app.dependency_overrides[get_sentence_service] = lambda: sentence_service
    app.dependency_overrides[get_audio_service] = lambda: word_service
    return sentence_service


@pytest.fixture
def sentence_client(tmp_path: Path):
    override_services(tmp_path, FakeTtsProvider())
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_sentence_audio_response_and_cache_file(sentence_client: TestClient) -> None:
    response = sentence_client.get(
        "/api/audio/sentence",
        params={"text": "This is a sentence."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "This is a sentence."
    assert data["synthetic"] is True
    assert data["engine"] == "Windows SAPI (System.Speech)"
    assert data["voice"] == "Microsoft Zira Desktop"
    assert data["locale"] == "en-US"
    assert data["cached"] is False
    assert "不是真人录音" in data["note"]
    assert data["audio_url"].startswith("/api/audio/cache/")

    audio = sentence_client.get(data["audio_url"])
    assert audio.status_code == 200
    assert audio.headers["content-type"].startswith("audio/wav")
    assert audio.content == WAV_BYTES

    cached = sentence_client.get(
        "/api/audio/sentence",
        params={"text": "This is a sentence."},
    )
    assert cached.status_code == 200
    assert cached.json()["cached"] is True


def test_empty_or_non_english_sentence_returns_400(sentence_client: TestClient) -> None:
    for text in ("   ", "12345"):
        response = sentence_client.get("/api/audio/sentence", params={"text": text})
        assert response.status_code == 400
        assert "句子" in response.json()["detail"]


def test_sentence_tts_failure_returns_503(tmp_path: Path) -> None:
    override_services(
        tmp_path,
        FakeTtsProvider(error=SentenceTtsError("系统语音合成不可用。")),
    )
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/audio/sentence",
                params={"text": "This is a sentence."},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "语音合成" in response.json()["detail"]
