"""Tests for English word, line and sentence extraction."""

from __future__ import annotations

import pymupdf
import pytest

from backend.app.services.errors import PageNotFoundError
from backend.app.services.pdf_extractor import extract_page_data
from backend.tests.helpers import (
    build_blank_pdf_bytes,
    build_non_english_pdf_bytes,
    build_pdf_bytes,
    build_scanned_pdf_bytes,
    build_wrapped_sentence_pdf_bytes,
)


def open_stream(data: bytes) -> pymupdf.Document:
    return pymupdf.open(stream=data, filetype="pdf")


def assert_valid_bbox(bbox: list[float]) -> None:
    assert len(bbox) == 4
    x0, y0, x1, y1 = bbox
    assert 0.0 <= x0 < x1 <= 1.0
    assert 0.0 <= y0 < y1 <= 1.0


def test_extracts_english_words_with_coordinates() -> None:
    doc = open_stream(build_pdf_bytes(pages=2))
    try:
        data = extract_page_data(doc, 1, "test-book")
    finally:
        doc.close()

    texts = [word.text for word in data.words]
    assert "Hello" in texts
    assert "world" in texts
    assert "vocabulary" in texts
    assert "12345" not in texts

    assert data.has_text is True
    assert data.is_scanned is False
    assert data.message is None
    assert data.page == 1
    assert data.page_count == 2
    assert data.rotation == 0

    line_ids = {line.id for line in data.lines}
    sentence_ids = {sentence.id for sentence in data.sentences}
    assert line_ids
    assert sentence_ids

    for word in data.words:
        assert_valid_bbox(word.bbox)
        assert word.line_id in line_ids
        assert word.sentence_id in sentence_ids

    for line in data.lines:
        assert_valid_bbox(line.bbox)
    for sentence in data.sentences:
        assert_valid_bbox(sentence.bbox)

    assert any(sentence.text == "Hello world." for sentence in data.sentences)
    assert any("sample sentence" in sentence.text for sentence in data.sentences)


def test_wrapped_sentence_remains_one_sentence() -> None:
    doc = open_stream(build_wrapped_sentence_pdf_bytes())
    try:
        data = extract_page_data(doc, 1, "test-book")
    finally:
        doc.close()

    matching = [
        sentence
        for sentence in data.sentences
        if "long example sentence" in sentence.text
    ]
    assert len(matching) == 1
    sentence = matching[0]
    assert sentence.text.endswith("playback.")
    assert sentence.bbox[3] - sentence.bbox[1] > 0.03


def test_rotated_page_returns_visual_coordinates() -> None:
    doc = open_stream(build_pdf_bytes(pages=1, rotation=90))
    try:
        data = extract_page_data(doc, 1, "test-book")
    finally:
        doc.close()

    assert data.rotation == 90
    assert data.width > data.height
    hello = next(word for word in data.words if word.text == "Hello")
    x0, y0, x1, y1 = hello.bbox
    assert x0 > 0.5
    assert y0 < 0.3
    assert 0.0 <= x0 < x1 <= 1.0
    assert 0.0 <= y0 < y1 <= 1.0


def test_non_english_text_has_explicit_message() -> None:
    doc = open_stream(build_non_english_pdf_bytes())
    try:
        data = extract_page_data(doc, 1, "test-book")
    finally:
        doc.close()

    assert data.has_text is True
    assert data.is_scanned is False
    assert data.words == []
    assert data.message is not None
    assert "英文单词" in data.message


def test_blank_page_has_explicit_message() -> None:
    doc = open_stream(build_blank_pdf_bytes())
    try:
        data = extract_page_data(doc, 1, "test-book")
    finally:
        doc.close()

    assert data.has_text is False
    assert data.is_scanned is False
    assert data.words == []
    assert data.message is not None
    assert "空白页" in data.message


def test_scanned_page_is_detected_and_not_faked() -> None:
    doc = open_stream(build_scanned_pdf_bytes())
    try:
        data = extract_page_data(doc, 1, "test-book")
    finally:
        doc.close()

    assert data.has_text is False
    assert data.is_scanned is True
    assert data.words == []
    assert data.message is not None
    assert "扫描版" in data.message


def test_page_out_of_range_raises() -> None:
    doc = open_stream(build_pdf_bytes(pages=1))
    try:
        with pytest.raises(PageNotFoundError):
            extract_page_data(doc, 2, "test-book")
    finally:
        doc.close()
