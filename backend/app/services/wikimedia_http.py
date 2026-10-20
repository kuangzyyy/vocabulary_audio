"""HTTP transport for Wikimedia Commons.

The local Python system proxy can be rate-limited by Wikimedia while a direct
curl connection works. This module uses curl when available (Windows 10+ ships
it) and falls back to urllib. Both paths respect HTTP 429 responses.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from backend.app.services.errors import AudioRateLimitedError, AudioUpstreamError

CHUNK_SIZE = 64 * 1024
CURL_RETRIES = 4


def _find_curl() -> str | None:
    if os.name == "nt":
        system_curl = (
            Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "curl.exe"
        )
        if system_curl.is_file():
            return str(system_curl)
    return shutil.which("curl")


def get_json(
    url: str,
    *,
    user_agent: str,
    timeout: float,
    use_proxy: bool = False,
) -> dict[str, Any]:
    curl = None if use_proxy else _find_curl()
    if curl:
        payload = _curl_json(curl, url, user_agent, timeout)
    else:
        payload = _urllib_json(url, user_agent, timeout, use_proxy)
    if not isinstance(payload, dict):
        raise AudioUpstreamError("Wikimedia Commons 返回了意外的数据。")
    return payload


def download(
    url: str,
    destination: Path,
    *,
    user_agent: str,
    timeout: float,
    max_bytes: int,
    use_proxy: bool = False,
) -> None:
    curl = None if use_proxy else _find_curl()
    if curl:
        _curl_download(curl, url, destination, user_agent, timeout, max_bytes)
    else:
        _urllib_download(url, destination, user_agent, timeout, max_bytes, use_proxy)


def _curl_json(
    curl: str,
    url: str,
    user_agent: str,
    timeout: float,
) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        command = [
            curl,
            "--noproxy",
            "*",
            "--silent",
            "--show-error",
            "--location",
            "--max-time",
            str(max(1, int(timeout))),
            "--user-agent",
            user_agent,
            "--header",
            "Accept: application/json",
            "--output",
            str(temp_path),
            "--write-out",
            "%{http_code}",
            url,
        ]
        result, status = _run_curl_with_retries(command, timeout + 10)
        _raise_for_status(status, result, "Wikimedia Commons 音频查询失败")
        try:
            return json.loads(temp_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise AudioUpstreamError(
                "Wikimedia Commons 返回了无法解析的数据。"
            ) from exc
    finally:
        temp_path.unlink(missing_ok=True)


def _curl_download(
    curl: str,
    url: str,
    destination: Path,
    user_agent: str,
    timeout: float,
    max_bytes: int,
) -> None:
    with tempfile.NamedTemporaryFile(suffix=".headers", delete=False) as handle:
        header_path = Path(handle.name)
    try:
        command = [
            curl,
            "--noproxy",
            "*",
            "--silent",
            "--show-error",
            "--location",
            "--max-time",
            str(max(1, int(timeout))),
            "--max-filesize",
            str(max_bytes),
            "--user-agent",
            user_agent,
            "--header",
            "Accept: audio/*,*/*;q=0.8",
            "--dump-header",
            str(header_path),
            "--output",
            str(destination),
            "--write-out",
            "%{http_code}",
            url,
        ]
        result, status = _run_curl_with_retries(
            command,
            timeout + 10,
            destination=destination,
        )
        if status == 429:
            destination.unlink(missing_ok=True)
            raise AudioRateLimitedError(
                "音频源请求过于频繁，请稍后再试。",
                retry_after=_retry_after_from_file(header_path),
            )
        if status == 0 and result.returncode != 0:
            destination.unlink(missing_ok=True)
            raise AudioUpstreamError(_curl_error_message(result))
        if status < 200 or status >= 300:
            destination.unlink(missing_ok=True)
            raise AudioUpstreamError(
                f"下载发音失败（HTTP {status or 'unknown'}）。"
            )
        if result.returncode != 0:
            destination.unlink(missing_ok=True)
            raise AudioUpstreamError(_curl_error_message(result))
        if not destination.is_file() or destination.stat().st_size == 0:
            destination.unlink(missing_ok=True)
            raise AudioUpstreamError("音频源返回了空文件。")
        if destination.stat().st_size > max_bytes:
            destination.unlink(missing_ok=True)
            raise AudioUpstreamError("音频文件过大，已拒绝下载。")
    finally:
        header_path.unlink(missing_ok=True)


def _urllib_json(
    url: str,
    user_agent: str,
    timeout: float,
    use_proxy: bool,
) -> dict[str, Any]:
    opener = _build_opener(use_proxy)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept": "application/json"},
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise AudioRateLimitedError(
                "音频源请求过于频繁，请稍后再试。",
                retry_after=_retry_after_from_headers(exc.headers),
            ) from exc
        raise AudioUpstreamError(
            f"Wikimedia Commons 返回错误（HTTP {exc.code}）。"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise AudioUpstreamError(
            "无法连接 Wikimedia Commons，请检查网络后重试。"
        ) from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise AudioUpstreamError("Wikimedia Commons 返回了无法解析的数据。") from exc


def _urllib_download(
    url: str,
    destination: Path,
    user_agent: str,
    timeout: float,
    max_bytes: int,
    use_proxy: bool,
) -> None:
    opener = _build_opener(use_proxy)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept": "audio/*,*/*;q=0.8"},
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type.startswith("text/") or "html" in content_type:
                raise AudioUpstreamError("音频源返回了非音频内容。")
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    declared_size = int(length)
                except ValueError:
                    declared_size = 0
                if declared_size > max_bytes:
                    raise AudioUpstreamError("音频文件过大，已拒绝下载。")

            total = 0
            with destination.open("wb") as output:
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise AudioUpstreamError("音频文件过大，已拒绝下载。")
                    output.write(chunk)
            if total == 0:
                raise AudioUpstreamError("音频源返回了空文件。")
    except urllib.error.HTTPError as exc:
        destination.unlink(missing_ok=True)
        if exc.code == 429:
            raise AudioRateLimitedError(
                "音频源请求过于频繁，请稍后再试。",
                retry_after=_retry_after_from_headers(exc.headers),
            ) from exc
        raise AudioUpstreamError(f"下载发音失败（HTTP {exc.code}）。") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        destination.unlink(missing_ok=True)
        raise AudioUpstreamError("下载发音失败，请检查网络后重试。") from exc


def _build_opener(use_proxy: bool) -> urllib.request.OpenerDirector:
    proxy_handler = (
        urllib.request.ProxyHandler() if use_proxy else urllib.request.ProxyHandler({})
    )
    return urllib.request.build_opener(proxy_handler)


def _run_curl(command: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AudioUpstreamError("无法启动下载工具 curl。") from exc


def _run_curl_with_retries(
    command: list[str],
    timeout: float,
    *,
    destination: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], int]:
    last_result: subprocess.CompletedProcess[str] | None = None
    last_status = 0
    for attempt in range(CURL_RETRIES):
        if destination is not None:
            destination.unlink(missing_ok=True)
        last_result = _run_curl(command, timeout)
        last_status = _status_code(last_result.stdout)
        if last_status != 0 or last_result.returncode == 0:
            return last_result, last_status
        if attempt < CURL_RETRIES - 1:
            time.sleep(1.0 + attempt)
    if last_result is None:
        raise AudioUpstreamError("Wikimedia Commons 请求失败。")
    return last_result, last_status


def _status_code(stdout: str) -> int:
    lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
    if not lines:
        return 0
    try:
        return int(lines[-1])
    except ValueError:
        return 0


def _raise_for_status(
    status: int,
    result: subprocess.CompletedProcess[str],
    prefix: str,
) -> None:
    if status == 429:
        raise AudioRateLimitedError("音频源请求过于频繁，请稍后再试。")
    if status == 0 and result.returncode != 0:
        raise AudioUpstreamError(_curl_error_message(result))
    if status < 200 or status >= 300:
        raise AudioUpstreamError(f"{prefix}（HTTP {status or 'unknown'}）。")
    if result.returncode != 0:
        raise AudioUpstreamError(_curl_error_message(result))


def _curl_error_message(result: subprocess.CompletedProcess[str]) -> str:
    detail = (result.stderr or "").strip().splitlines()
    suffix = detail[-1][:160] if detail else f"curl 退出码 {result.returncode}"
    lowered = suffix.lower()
    if "connection was reset" in lowered or "could not connect" in lowered:
        return "无法连接 Wikimedia Commons，请检查网络后重试。"
    if "timed out" in lowered or "timeout" in lowered:
        return "连接 Wikimedia Commons 超时，请重试。"
    return f"Wikimedia Commons 请求失败：{suffix}"


def _retry_after_from_headers(headers: Any) -> float | None:
    if headers is None:
        return None
    value = headers.get("Retry-After")
    return _parse_retry_after(value)


def _retry_after_from_file(path: Path) -> float | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        if line.lower().startswith("retry-after:"):
            return _parse_retry_after(line.split(":", 1)[1].strip())
    return None


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
