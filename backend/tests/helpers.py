"""Helpers that build small, self-owned PDFs for tests."""

from __future__ import annotations

import io

import pymupdf
from PIL import Image, ImageDraw


def build_pdf_bytes(*, pages: int = 2, rotation: int = 0) -> bytes:
    """Create a simple text PDF with predictable English words."""
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), "Hello world. This is a sample sentence.", fontsize=14)
        page.insert_text((72, 140), "Second paragraph has vocabulary and a test.", fontsize=14)
        if rotation:
            page.set_rotation(rotation)

        for _ in range(max(0, pages - 1)):
            extra = doc.new_page(width=595, height=842)
            extra.insert_text((72, 100), "Another page with a different word.", fontsize=14)

        return doc.tobytes()
    finally:
        doc.close()


def build_wrapped_sentence_pdf_bytes() -> bytes:
    """Create a page where one sentence wraps across multiple lines."""
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=400, height=600)
        page.insert_textbox(
            pymupdf.Rect(40, 80, 360, 220),
            (
                "This is a long example sentence that wraps across several lines "
                "and should stay one sentence for playback."
            ),
            fontsize=14,
        )
        return doc.tobytes()
    finally:
        doc.close()


def build_non_english_pdf_bytes() -> bytes:
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=400, height=600)
        page.insert_text((40, 100), "12345 67890", fontsize=14)
        return doc.tobytes()
    finally:
        doc.close()


def build_blank_pdf_bytes() -> bytes:
    doc = pymupdf.open()
    try:
        doc.new_page(width=400, height=600)
        return doc.tobytes()
    finally:
        doc.close()


def build_scanned_pdf_bytes() -> bytes:
    """Create a page containing only an image and no text layer."""
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=400, height=300)
        image = Image.new("RGB", (800, 600), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 40, 760, 560), outline="black", width=3)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        page.insert_image(pymupdf.Rect(0, 0, 400, 300), stream=buffer.getvalue())
        return doc.tobytes()
    finally:
        doc.close()


def build_encrypted_pdf_bytes() -> bytes:
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=400, height=600)
        page.insert_text((40, 100), "Secret words here.", fontsize=14)
        return doc.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner-password",
            user_pw="user-password",
        )
    finally:
        doc.close()
