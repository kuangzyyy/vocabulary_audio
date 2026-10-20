"""Tests for synthetic sentence TTS caching and validation."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from backend.app.services.errors import InvalidSentenceError, SentenceTtsError
from backend.app.services.sentence_audio import (
    SentenceAudioService,
    SynthesisResult,
    normalize_sentence,
)

WAV_BYTES = b"RIFF" + struct.pack("<I", 84) + b"WAVE" + b"\x00" * 84


class FakeTtsProvider:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    def synthesize(self, text: str, destination: Path) -> SynthesisResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        destination.write_bytes(WAV_BYTES)
        return SynthesisResult(voice="Microsoft Zira Desktop", locale="en-US")


def make_service(
    tmp_path: Path,
    provider: FakeTtsProvider,
    *,
    max_chars: int = 500,
) -> SentenceAudioService:
    return SentenceAudioService(
        tmp_path / "audio_cache",
        provider=provider,
        max_chars=max_chars,
    )


def test_sentence_is_normalized_cached_and_reused(tmp_path: Path) -> None:
    provider = FakeTtsProvider()
    service = make_service(tmp_path, provider)

    first = service.resolve("  This   is a sentence.  ")
    assert first.text == "This is a sentence."
    assert first.synthetic is True
    assert first.voice == "Microsoft Zira Desktop"
    assert first.locale == "en-US"
    assert first.cached is False
    assert provider.calls == 1

    second = service.resolve("This is a sentence.")
    assert second.cached is True
    assert second.cache_id == first.cache_id
    assert provider.calls == 1

    metadata_path = tmp_path / "audio_cache" / f"{first.cache_id}.json"
    audio_path = tmp_path / "audio_cache" / f"{first.cache_id}.wav"
    assert audio_path.read_bytes() == WAV_BYTES
    assert metadata_path.is_file()
    assert '"synthetic": true' in metadata_path.read_text(encoding="utf-8")
    assert "Microsoft Zira Desktop" in metadata_path.read_text(encoding="utf-8")


def test_empty_non_english_and_too_long_sentences_are_rejected() -> None:
    with pytest.raises(InvalidSentenceError):
        normalize_sentence("   ")
    with pytest.raises(InvalidSentenceError):
        normalize_sentence("12345")
    with pytest.raises(InvalidSentenceError):
        normalize_sentence("This sentence is too long for the limit.", max_chars=10)


def test_tts_failure_cleans_partial_files(tmp_path: Path) -> None:
    provider = FakeTtsProvider(error=SentenceTtsError("voice unavailable"))
    service = make_service(tmp_path, provider)

    with pytest.raises(SentenceTtsError):
        service.resolve("This is a sentence.")

    assert not list((tmp_path / "audio_cache").glob("*.wav"))
    assert not list((tmp_path / "audio_cache").glob("*.json"))


def test_invalid_wav_output_is_rejected(tmp_path: Path) -> None:
    class BrokenProvider:
        def synthesize(self, text: str, destination: Path) -> SynthesisResult:
            destination.write_bytes(b"not a wav")
            return SynthesisResult(voice="Broken", locale="")

    service = SentenceAudioService(
        tmp_path / "audio_cache",
        provider=BrokenProvider(),
    )

    with pytest.raises(SentenceTtsError):
        service.resolve("This is a sentence.")
