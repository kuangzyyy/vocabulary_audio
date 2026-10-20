"""Tests for PDF page coordinate normalization."""

from __future__ import annotations

import pymupdf
import pytest

from backend.app.services.pdf_extractor import normalize_rect


def make_page(rotation: int = 0) -> tuple[pymupdf.Document, pymupdf.Page]:
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=600)
    if rotation:
        page.set_rotation(rotation)
    return doc, page


def test_identity_mapping_uses_top_left_origin() -> None:
    doc, page = make_page()
    try:
        bbox = normalize_rect(page, pymupdf.Rect(40, 60, 140, 90))
        assert bbox == pytest.approx([0.1, 0.1, 0.35, 0.15])
    finally:
        doc.close()


def test_rect_outside_page_is_clamped() -> None:
    doc, page = make_page()
    try:
        bbox = normalize_rect(page, pymupdf.Rect(-20, -30, 420, 630))
        assert bbox == pytest.approx([0.0, 0.0, 1.0, 1.0])
    finally:
        doc.close()


def test_rotation_90_moves_top_left_content_to_top_right() -> None:
    doc, page = make_page(90)
    try:
        bbox = normalize_rect(page, pymupdf.Rect(40, 60, 140, 90))
        x0, y0, x1, y1 = bbox
        assert 0.0 <= x0 < x1 <= 1.0
        assert 0.0 <= y0 < y1 <= 1.0
        assert x0 > 0.7
        assert y0 < 0.25
    finally:
        doc.close()


def test_rotation_180_moves_top_left_content_to_bottom_right() -> None:
    doc, page = make_page(180)
    try:
        bbox = normalize_rect(page, pymupdf.Rect(40, 60, 140, 90))
        x0, y0, x1, y1 = bbox
        assert x0 > 0.6
        assert y0 > 0.7
        assert x1 <= 1.0
        assert y1 <= 1.0
    finally:
        doc.close()


def test_rotation_270_moves_top_left_content_to_bottom_left() -> None:
    doc, page = make_page(270)
    try:
        bbox = normalize_rect(page, pymupdf.Rect(40, 60, 140, 90))
        x0, y0, x1, y1 = bbox
        assert x0 < 0.25
        assert y0 > 0.6
        assert x1 <= 1.0
        assert y1 <= 1.0
    finally:
        doc.close()
