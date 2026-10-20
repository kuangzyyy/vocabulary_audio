"""Tests for the book upload and page API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api.books import get_book_service
from backend.app.main import app
from backend.app.services.books import BookService
from backend.tests.helpers import (
    build_blank_pdf_bytes,
    build_encrypted_pdf_bytes,
    build_pdf_bytes,
    build_scanned_pdf_bytes,
)


@pytest.fixture
def client(tmp_path: Path):
    service = BookService(tmp_path)
    app.dependency_overrides[get_book_service] = lambda: service
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def upload_pdf(client: TestClient, data: bytes, filename: str = "sample.pdf"):
    return client.post(
        "/api/books",
        files={"file": (filename, data, "application/pdf")},
    )


def test_upload_serve_and_fetch_page(client: TestClient) -> None:
    pdf_bytes = build_pdf_bytes(pages=2)
    response = upload_pdf(client, pdf_bytes)

    assert response.status_code == 201
    book = response.json()
    assert len(book["book_id"]) == 32
    assert book["filename"] == "sample.pdf"
    assert book["page_count"] == 2
    assert book["size_bytes"] == len(pdf_bytes)

    file_response = client.get(f"/api/books/{book['book_id']}/file")
    assert file_response.status_code == 200
    assert file_response.headers["content-type"].startswith("application/pdf")
    assert file_response.content == pdf_bytes

    page_response = client.get(f"/api/books/{book['book_id']}/pages/1")
    assert page_response.status_code == 200
    page = page_response.json()
    assert page["page"] == 1
    assert page["page_count"] == 2
    assert page["has_text"] is True
    assert page["is_scanned"] is False
    assert any(word["text"] == "Hello" for word in page["words"])
    for word in page["words"]:
        assert len(word["bbox"]) == 4
        assert 0.0 <= word["bbox"][0] < word["bbox"][2] <= 1.0

    page_two = client.get(f"/api/books/{book['book_id']}/pages/2")
    assert page_two.status_code == 200
    assert any(
        word["text"] == "Another" for word in page_two.json()["words"]
    )


def test_empty_upload_is_rejected(client: TestClient) -> None:
    response = upload_pdf(client, b"", "empty.pdf")

    assert response.status_code == 400
    assert "空" in response.json()["detail"]


def test_non_pdf_upload_is_rejected(client: TestClient) -> None:
    response = upload_pdf(client, b"this is not a pdf", "fake.pdf")

    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_encrypted_pdf_is_rejected(client: TestClient) -> None:
    response = upload_pdf(client, build_encrypted_pdf_bytes(), "locked.pdf")

    assert response.status_code == 400
    assert "加密" in response.json()["detail"]


def test_missing_book_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/books/{'0' * 32}/pages/1")

    assert response.status_code == 404


def test_invalid_book_id_returns_404(client: TestClient) -> None:
    response = client.get("/api/books/not-a-book/pages/1")

    assert response.status_code == 404


def test_page_out_of_range_returns_404(client: TestClient) -> None:
    book = upload_pdf(client, build_pdf_bytes(pages=1)).json()

    response = client.get(f"/api/books/{book['book_id']}/pages/99")

    assert response.status_code == 404
    assert "页码" in response.json()["detail"]


def test_scanned_page_returns_message_instead_of_fake_words(client: TestClient) -> None:
    book = upload_pdf(client, build_scanned_pdf_bytes(), "scan.pdf").json()

    response = client.get(f"/api/books/{book['book_id']}/pages/1")

    assert response.status_code == 200
    page = response.json()
    assert page["is_scanned"] is True
    assert page["words"] == []
    assert "扫描版" in page["message"]


def test_blank_page_is_not_reported_as_scanned(client: TestClient) -> None:
    book = upload_pdf(client, build_blank_pdf_bytes(), "blank.pdf").json()

    response = client.get(f"/api/books/{book['book_id']}/pages/1")

    assert response.status_code == 200
    page = response.json()
    assert page["has_text"] is False
    assert page["is_scanned"] is False
    assert "空白页" in page["message"]


def test_page_extraction_failure_returns_422(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    book = upload_pdf(client, build_pdf_bytes(pages=1)).json()

    def boom(*args, **kwargs):
        raise RuntimeError("simulated extraction failure")

    monkeypatch.setattr("backend.app.services.books.extract_page_data", boom)

    response = client.get(f"/api/books/{book['book_id']}/pages/1")

    assert response.status_code == 422
    assert "提取失败" in response.json()["detail"]
