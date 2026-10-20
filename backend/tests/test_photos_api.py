"""API tests for photo upload, OCR data, file serving and deletion."""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.api.photos import get_photo_service
from backend.app.main import app
from backend.app.services.photo_ocr import PhotoOcrService


def quad(x0: float, y0: float, x1: float, y1: float):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def make_image_bytes() -> bytes:
    image = Image.new("RGB", (600, 400), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_oriented_jpeg_bytes() -> bytes:
    image = Image.new("RGB", (600, 400), "white")
    exif = Image.Exif()
    exif[274] = 6  # Rotate 90 degrees clockwise.
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def fake_result():
    return SimpleNamespace(
        boxes=[quad(50, 50, 550, 110)],
        txts=("Hello world.",),
        scores=(0.99,),
        word_results=(
            (
                ("Hello", 0.99, quad(50, 50, 180, 110)),
                ("world.", 0.99, quad(195, 50, 320, 110)),
            ),
        ),
    )


class FakeEngine:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    def __call__(self, image, return_word_box=True):
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def photo_client(tmp_path: Path):
    service = PhotoOcrService(
        tmp_path,
        engine=FakeEngine(fake_result()),
        max_upload_bytes=5 * 1024 * 1024,
    )
    app.dependency_overrides[get_photo_service] = lambda: service
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def upload_photo(client: TestClient, data: bytes | None = None):
    payload = make_image_bytes() if data is None else data
    return client.post(
        "/api/photos",
        files={"file": ("page.png", payload, "image/png")},
    )


def test_upload_ocr_file_and_delete(photo_client: TestClient) -> None:
    response = upload_photo(photo_client)

    assert response.status_code == 201
    data = response.json()
    assert len(data["photo_id"]) == 32
    assert data["has_text"] is True
    assert data["has_english"] is True
    assert data["message"] is None
    assert data["word_box_method"].startswith("RapidOCR return_word_box=True")
    assert [word["text"] for word in data["words"]] == ["Hello", "world"]
    assert data["photo_url"].startswith("/api/photos/")

    image = photo_client.get(data["photo_url"])
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/jpeg")
    assert image.content.startswith(b"\xff\xd8")

    deleted = photo_client.delete(f"/api/photos/{data['photo_id']}")
    assert deleted.status_code == 204
    assert photo_client.get(data["photo_url"]).status_code == 404


def test_empty_and_invalid_images_are_rejected(photo_client: TestClient) -> None:
    empty = upload_photo(photo_client, b"")
    assert empty.status_code == 400
    assert "空" in empty.json()["detail"]

    invalid = upload_photo(photo_client, b"not an image")
    assert invalid.status_code == 400
    assert "图片" in invalid.json()["detail"]


def test_exif_orientation_is_applied(photo_client: TestClient) -> None:
    response = upload_photo(photo_client, make_oriented_jpeg_bytes())

    assert response.status_code == 201
    data = response.json()
    assert data["width"] == 400
    assert data["height"] == 600


def test_ocr_failure_keeps_photo_and_returns_message(tmp_path: Path) -> None:
    service = PhotoOcrService(
        tmp_path,
        engine=FakeEngine(error=RuntimeError("ocr unavailable")),
    )
    app.dependency_overrides[get_photo_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = upload_photo(client)
            data = response.json()
            image = client.get(data["photo_url"])
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert data["has_text"] is False
    assert data["words"] == []
    assert "OCR" in data["message"]
    assert image.status_code == 200


def test_missing_photo_returns_404(photo_client: TestClient) -> None:
    assert photo_client.get(f"/api/photos/{'0' * 32}/file").status_code == 404
    assert photo_client.delete("/api/photos/not-a-photo").status_code == 404
