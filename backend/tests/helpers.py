"""Helpers that build small, self-owned PDFs and EPUBs for tests."""

from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

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


def build_epub_bytes(
    *,
    chapters: int = 2,
    title: str = "Test EPUB",
    author: str = "Test Author",
    language: str = "en",
    rootfile: str = "OEBPS/content.opf",
) -> bytes:
    """Create a minimal, self-owned EPUB 3 container with one TOC entry per chapter."""
    chapter_ids = [f"chapter{i}" for i in range(1, chapters + 1)]
    chapter_titles = [f"Chapter {i}" for i in range(1, chapters + 1)]
    chapter_paragraphs = [
        (
            "Hello world. This is the first chapter. "
            "The quick brown fox jumps over the lazy dog."
        )
        if index == 0
        else f"Another chapter has different vocabulary. This is chapter {index + 1}."
        for index in range(chapters)
    ]

    manifest_items = "\n".join(
        f'    <item id="{chapter_id}" href="{chapter_id}.xhtml" '
        'media-type="application/xhtml+xml"/>'
        for chapter_id in chapter_ids
    )
    spine_items = "\n".join(
        f'    <itemref idref="{chapter_id}"/>' for chapter_id in chapter_ids
    )
    nav_items = "\n".join(
        f'      <li><a href="{chapter_id}.xhtml">{escape(chapter_title)}</a></li>'
        for chapter_id, chapter_title in zip(chapter_ids, chapter_titles, strict=True)
    )

    package = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:test-epub</dc:identifier>
    <dc:title>{escape(title)}</dc:title>
    <dc:creator>{escape(author)}</dc:creator>
    <dc:language>{escape(language)}</dc:language>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
{manifest_items}
  </manifest>
  <spine>
{spine_items}
  </spine>
</package>
"""

    nav = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <head><title>Contents</title></head>
  <body>
    <nav epub:type="toc">
      <h1>Contents</h1>
      <ol>
{nav_items}
      </ol>
    </nav>
  </body>
</html>
"""

    container = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
""".replace("OEBPS/content.opf", rootfile)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED
        )
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/content.opf", package)
        archive.writestr("OEBPS/nav.xhtml", nav)
        for chapter_id, paragraph in zip(
            chapter_ids, chapter_paragraphs, strict=True
        ):
            archive.writestr(
                f"OEBPS/{chapter_id}.xhtml",
                f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>{escape(chapter_id)}</title></head>
  <body><h1>{escape(chapter_id)}</h1><p>{escape(paragraph)}</p></body>
</html>
""",
            )
    return buffer.getvalue()
