"""Local, clearly-labelled sentence TTS with a disk cache.

There is no reliable legal source for arbitrary whole-sentence human recordings
from a PDF. Word recordings are therefore never spliced together. Instead we
use the local Windows SAPI voice and expose it as synthetic speech.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from backend.app.config import PROJECT_ROOT
from backend.app.services.errors import InvalidSentenceError, SentenceTtsError

ENGINE_NAME = "Windows SAPI (System.Speech)"
TTS_SCRIPT = PROJECT_ROOT / "scripts" / "tts_sapi.ps1"
SYNTHETIC_NOTE = "由本机 Windows 系统语音合成生成，不是真人录音。"
MAX_SENTENCE_CHARS = 500
MAX_AUDIO_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class SynthesisResult:
    voice: str
    locale: str


@dataclass(frozen=True)
class ResolvedSentenceAudio:
    cache_id: str
    text: str
    engine: str
    voice: str
    locale: str
    synthetic: bool
    cached: bool


class TtsProvider(Protocol):
    def synthesize(self, text: str, destination: Path) -> SynthesisResult:
        """Write a WAV file and return the selected voice metadata."""


class WindowsSapiProvider:
    """Generate WAV speech with Windows System.Speech, without network access."""

    def __init__(
        self,
        *,
        script_path: Path = TTS_SCRIPT,
        timeout: float = 30.0,
        powershell: str | None = None,
    ) -> None:
        self.script_path = Path(script_path)
        self.timeout = timeout
        self.powershell = powershell

    def synthesize(self, text: str, destination: Path) -> SynthesisResult:
        powershell = self.powershell or _find_powershell()
        if powershell is None:
            raise SentenceTtsError(
                "系统语音合成不可用：未找到 Windows PowerShell。"
            )
        if not self.script_path.is_file():
            raise SentenceTtsError("系统语音合成脚本缺失，请检查安装。")

        text_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                suffix=".txt",
                dir=destination.parent,
                delete=False,
            ) as handle:
                handle.write(text)
                text_path = Path(handle.name)

            command = [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.script_path),
                "-TextPath",
                str(text_path),
                "-OutputPath",
                str(destination),
            ]
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise SentenceTtsError("语音合成超时，请稍后重试。") from exc
            except OSError as exc:
                raise SentenceTtsError(
                    "无法启动系统语音合成，请检查 Windows 语音设置。"
                ) from exc

            if result.returncode != 0:
                raise SentenceTtsError(_tts_failure_message(result))

            voice, locale = _parse_voice(result.stdout)
            _validate_wav(destination)
            return SynthesisResult(voice=voice, locale=locale)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            if text_path is not None:
                text_path.unlink(missing_ok=True)


class SentenceAudioService:
    """Cache synthetic sentence WAV files and reuse them for duplicate clicks."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        provider: TtsProvider | None = None,
        max_chars: int = MAX_SENTENCE_CHARS,
        tts_timeout: float = 30.0,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_chars = max_chars
        self.provider = provider or WindowsSapiProvider(timeout=tts_timeout)
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def resolve(self, text: str) -> ResolvedSentenceAudio:
        normalized = normalize_sentence(text, self.max_chars)
        cache_id = _cache_key(normalized)
        lock = self._lock_for(cache_id)
        with lock:
            cached = self._find_cached(cache_id, normalized)
            if cached is not None:
                return cached
            return self._synthesize(cache_id, normalized)

    def _find_cached(
        self,
        cache_id: str,
        text: str,
    ) -> ResolvedSentenceAudio | None:
        metadata = self._read_metadata(cache_id)
        if metadata is None:
            return None
        if metadata.get("kind") != "sentence" or metadata.get("text") != text:
            return None
        cache_file = str(metadata.get("cache_file") or "")
        if not cache_file.startswith(f"{cache_id}."):
            return None
        if "/" in cache_file or "\\" in cache_file:
            return None
        if not (self.cache_dir / cache_file).is_file():
            return None
        return _resolved_from_metadata(cache_id, metadata, cached=True)

    def _synthesize(self, cache_id: str, text: str) -> ResolvedSentenceAudio:
        audio_path = self.cache_dir / f"{cache_id}.wav"
        metadata_path = self.cache_dir / f"{cache_id}.json"
        temp_audio = self.cache_dir / f".{cache_id}.wav.part"
        temp_metadata = self.cache_dir / f".{cache_id}.json.part"

        try:
            synthesis = self.provider.synthesize(text, temp_audio)
            _validate_wav(temp_audio)
            if temp_audio.stat().st_size > MAX_AUDIO_BYTES:
                raise SentenceTtsError("合成音频过大，已拒绝缓存。")

            metadata = {
                "cache_version": 1,
                "kind": "sentence",
                "synthetic": True,
                "text": text,
                "engine": ENGINE_NAME,
                "voice": synthesis.voice,
                "locale": synthesis.locale,
                "cache_file": audio_path.name,
                "mime": "audio/wav",
                "note": SYNTHETIC_NOTE,
                "generated_at": datetime.now(timezone.utc).isoformat(),
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

    def _lock_for(self, cache_id: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(cache_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[cache_id] = lock
            return lock


def normalize_sentence(text: str, max_chars: int = MAX_SENTENCE_CHARS) -> str:
    """Collapse whitespace and reject empty, non-English or overly long text."""
    value = re.sub(r"\s+", " ", text or "").strip()
    if not value:
        raise InvalidSentenceError("句子为空，无法生成语音。")
    if re.search(r"[A-Za-z]", value) is None:
        raise InvalidSentenceError("句子中没有英文内容，无法生成语音。")
    if len(value) > max_chars:
        raise InvalidSentenceError(
            f"句子过长（最多 {max_chars} 个字符），请点击更短的句子。"
        )
    return value


def _cache_key(text: str) -> str:
    raw = f"tts-sapi|v1|sentence|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _find_powershell() -> str | None:
    if os.name != "nt":
        return None
    candidates = [
        shutil.which("powershell"),
        str(
            Path(os.environ.get("SystemRoot", r"C:\Windows"))
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe"
        ),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def _validate_wav(path: Path) -> None:
    if not path.is_file():
        raise SentenceTtsError("系统语音没有生成音频文件。")
    if path.stat().st_size <= 44:
        raise SentenceTtsError("系统语音生成的音频文件为空。")
    with path.open("rb") as handle:
        header = handle.read(12)
    if not header.startswith(b"RIFF") or header[8:12] != b"WAVE":
        raise SentenceTtsError("系统语音生成的音频格式无效。")


def _parse_voice(stdout: str) -> tuple[str, str]:
    for line in (stdout or "").splitlines():
        if not line.startswith("VOICE|"):
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            return parts[1].strip() or "Windows voice", parts[2].strip()
        if len(parts) == 2:
            return parts[1].strip() or "Windows voice", ""
    return "Windows voice", ""


def _tts_failure_message(result: subprocess.CompletedProcess[str]) -> str:
    detail = (result.stderr or "").strip()
    if "No enabled English voice" in detail:
        return "系统没有可用的英文语音，请检查 Windows 语音设置。"
    return "系统语音合成失败，请检查 Windows 语音设置。"


def _resolved_from_metadata(
    cache_id: str,
    metadata: dict[str, object],
    *,
    cached: bool,
) -> ResolvedSentenceAudio:
    return ResolvedSentenceAudio(
        cache_id=cache_id,
        text=str(metadata.get("text") or ""),
        engine=str(metadata.get("engine") or ENGINE_NAME),
        voice=str(metadata.get("voice") or "Windows voice"),
        locale=str(metadata.get("locale") or ""),
        synthetic=True,
        cached=cached,
    )
