#!/usr/bin/env python3
"""Check the local development environment for Vocabulary Audio.

This script uses only the standard library so it can run even before the
project dependencies are installed. It prints ASCII markers so it works in
Windows terminals with non-UTF-8 code pages.

Usage (from the project root):
    python scripts/check_env.py

Exit code 0 means every required check passed; 1 means something is missing.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 12)
MIN_NODE = (22, 13)
MIN_NPM = (10, 0)

required_python_packages = [
    ("fastapi", "FastAPI"),
    ("uvicorn", "Uvicorn"),
    ("pymupdf", "PyMuPDF"),
    ("rapidocr", "RapidOCR"),
    ("onnxruntime", "ONNX Runtime"),
    ("PIL", "Pillow"),
    ("multipart", "python-multipart"),
]


def run_version(command):
    """Return (version string, error) for a command that prints its version."""
    executable = shutil.which(command)
    if executable is None:
        return None, "not found on PATH"
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    output = (result.stdout or result.stderr).strip().splitlines()
    if not output:
        return None, "no version output"
    return output[0].strip(), None


def parse_version(text):
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    if not match:
        return None
    return tuple(int(part) for part in match.groups(default="0"))


def report(ok, label, detail):
    marker = "[OK]  " if ok else "[--]  "
    print("{0}{1:<24} {2}".format(marker, label, detail))
    return ok


def main():
    print("=" * 72)
    print("Vocabulary Audio - environment check")
    print("=" * 72)
    print("Project root: {0}".format(ROOT))
    print("Interpreter:  {0}".format(sys.executable))
    print("In venv:      {0}".format(sys.prefix != sys.base_prefix))
    print()

    failures = 0

    print("Required runtime")
    py_ok = sys.version_info >= MIN_PYTHON
    report(
        py_ok,
        "Python",
        "{0}.{1}.{2} (need >= {3}.{4})".format(
            sys.version_info.major,
            sys.version_info.minor,
            sys.version_info.micro,
            MIN_PYTHON[0],
            MIN_PYTHON[1],
        ),
    )
    if not py_ok:
        failures += 1

    node_text, node_error = run_version("node")
    node_version = parse_version(node_text)
    node_ok = node_version is not None and node_version >= MIN_NODE
    report(node_ok, "Node.js", node_text or node_error)
    if not node_ok:
        failures += 1

    npm_text, npm_error = run_version("npm")
    npm_version = parse_version(npm_text)
    npm_ok = npm_version is not None and npm_version >= MIN_NPM
    report(npm_ok, "npm", npm_text or npm_error)
    if not npm_ok:
        failures += 1

    git_text, git_error = run_version("git")
    git_ok = git_text is not None
    report(git_ok, "Git", git_text or git_error)
    if not git_ok:
        failures += 1

    print()
    print("Backend Python packages (current interpreter)")
    missing_packages = []
    for module_name, display_name in required_python_packages:
        found = importlib.util.find_spec(module_name) is not None
        report(found, display_name, "installed" if found else "MISSING")
        if not found:
            missing_packages.append(display_name)
    if missing_packages:
        failures += 1

    print()
    print("Frontend packages")
    package_json = ROOT / "frontend" / "package.json"
    report(package_json.is_file(), "package.json", str(package_json.relative_to(ROOT)))
    node_modules = ROOT / "frontend" / "node_modules"
    npm_installed = node_modules.is_dir()
    report(npm_installed, "node_modules", "installed" if npm_installed else "run npm install")
    lockfile = ROOT / "frontend" / "package-lock.json"
    report(lockfile.is_file(), "package-lock.json", "present" if lockfile.is_file() else "missing")
    for package_name in ("pdfjs-dist", "vite"):
        manifest = node_modules / package_name / "package.json"
        if manifest.is_file():
            try:
                version = json.loads(manifest.read_text(encoding="utf-8")).get("version", "?")
            except (OSError, ValueError):
                version = "unreadable"
            report(True, package_name, version)
        else:
            report(False, package_name, "not installed")
            failures += 1

    print()
    print("Project data directories")
    for relative in ("data/books", "data/photos", "data/audio_cache"):
        path = ROOT / relative
        report(path.is_dir(), relative, "present" if path.is_dir() else "missing")

    print()
    print("Optional / not required by this stack")
    tesseract_text, tesseract_error = run_version("tesseract")
    report(tesseract_text is not None, "Tesseract OCR", tesseract_text or "not installed (not required)")
    docker_text, docker_error = run_version("docker")
    report(docker_text is not None, "Docker", docker_text or "not installed (not required)")

    print()
    print("=" * 72)
    if failures == 0:
        print("RESULT: all required checks passed.")
        print("Next: run the backend and frontend using the commands in README.md.")
        return 0

    print("RESULT: {0} check group(s) need attention.".format(failures))
    if not py_ok:
        print("Install Python 3.12 first: https://www.python.org/downloads/windows/")
        print("Then create the project venv with: py -3.12 -m venv .venv")
    if missing_packages:
        print("Install backend deps inside the venv: pip install -r requirements-dev.txt")
    if not npm_installed:
        print("Install frontend deps: cd frontend && npm install")
    print("See README.md and docs/environment.md for details.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
