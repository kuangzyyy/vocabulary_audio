"""Tests for EPUB upload validation and original-file serving."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api.epubs import get_epub_service
from backend.app.main import app
from backend.app.services.epubs import EpubService
from backend.tests.helpers import build_epub_bytes


@pytest.fixture
def client(tmp_path: Path):
    service = EpubService(tmp_path)
    app.dependency_overrides[get_epub_service] = lambda: service
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def upload_epub(
    client: TestClient,
    data: bytes,
    filename: str = "sample.epub",
    content_type: str = "application/epub+zip",
):
    return client.post(
        "/api/epubs",
        files={"file": (filename, data, content_type)},
    )


def test_upload_serve_and_read_metadata(client: TestClient) -> None:
    epub_bytes = build_epub_bytes(chapters=2, title="My Book", author="Ada")

    response = upload_epub(client, epub_bytes)

    assert response.status_code == 201
    epub = response.json()
    assert len(epub["epub_id"]) == 32
    assert epub["filename"] == "sample.epub"
    assert epub["title"] == "My Book"
    assert epub["author"] == "Ada"
    assert epub["language"] == "en"
    assert epub["chapter_count"] == 2
    assert epub["size_bytes"] == len(epub_bytes)

    file_response = client.get(f"/api/epubs/{epub['epub_id']}/file")
    assert file_response.status_code == 200
    assert file_response.headers["content-type"].startswith("application/epub+zip")
    assert file_response.content == epub_bytes


def test_epub_without_title_falls_back_to_filename(client: TestClient) -> None:
    data = build_epub_bytes(title="")
    epub = upload_epub(client, data, "fallback-name.epub").json()

    assert epub["title"] == "fallback-name"


def test_empty_upload_is_rejected(client: TestClient) -> None:
    response = upload_epub(client, b"", "empty.epub")

    assert response.status_code == 400
    assert "空" in response.json()["detail"]


def test_non_zip_upload_is_rejected(client: TestClient) -> None:
    response = upload_epub(client, b"this is not a zip", "fake.epub")

    assert response.status_code == 400
    assert "ZIP" in response.json()["detail"]


def test_zip_without_mimetype_is_rejected(client: TestClient) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("META-INF/container.xml", "<container/>")

    response = upload_epub(client, buffer.getvalue(), "no-mimetype.epub")

    assert response.status_code == 400
    assert "mimetype" in response.json()["detail"]


def test_wrong_mimetype_is_rejected(client: TestClient) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/zip")

    response = upload_epub(client, buffer.getvalue(), "wrong-mimetype.epub")

    assert response.status_code == 400
    assert "mimetype" in response.json()["detail"]


def test_missing_container_is_rejected(client: TestClient) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")

    response = upload_epub(client, buffer.getvalue(), "no-container.epub")

    assert response.status_code == 400
    assert "container.xml" in response.json()["detail"]


def test_path_traversal_rootfile_is_rejected(client: TestClient) -> None:
    response = upload_epub(
        client,
        build_epub_bytes(rootfile="../../outside.opf"),
        "traversal.epub",
    )

    assert response.status_code == 400
    assert "路径" in response.json()["detail"]


def test_epub_without_spine_is_rejected(client: TestClient) -> None:
    response = upload_epub(
        client,
        build_epub_bytes(chapters=0),
        "no-chapters.epub",
    )

    assert response.status_code == 400
    assert "章节" in response.json()["detail"]


def test_too_large_epub_is_rejected(tmp_path: Path) -> None:
    service = EpubService(tmp_path, max_upload_bytes=512)
    app.dependency_overrides[get_epub_service] = lambda: service
    try:
        with TestClient(app) as test_client:
            response = upload_epub(
                test_client,
                build_epub_bytes(),
                "large.epub",
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413
    assert "大小限制" in response.json()["detail"]


def test_missing_and_invalid_ids_return_404(client: TestClient) -> None:
    missing = client.get(f"/api/epubs/{'0' * 32}/file")
    assert missing.status_code == 404

    invalid = client.get("/api/epubs/not-an-epub/file")
    assert invalid.status_code == 404
    assert "ID" in invalid.json()["detail"]


def test_failed_upload_does_not_leave_partial_files(client: TestClient, tmp_path: Path) -> None:
    response = upload_epub(client, b"not a zip", "broken.epub")
    assert response.status_code == 400

    epubs_dir = tmp_path / "epubs"
    assert not list(epubs_dir.glob("*.part"))
    assert not list(epubs_dir.glob("*.epub"))
    assert not list(epubs_dir.glob("*.json"))
