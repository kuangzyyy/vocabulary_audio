"""Response models for the book and page APIs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BookInfo(BaseModel):
    book_id: str
    filename: str
    page_count: int
    title: str | None = None
    size_bytes: int


class WordItem(BaseModel):
    id: str
    text: str
    bbox: list[float] = Field(min_length=4, max_length=4)
    line_id: str
    sentence_id: str | None = None


class LineItem(BaseModel):
    id: str
    text: str
    bbox: list[float] = Field(min_length=4, max_length=4)


class SentenceSegment(BaseModel):
    line_id: str
    bbox: list[float] = Field(min_length=4, max_length=4)


class SentenceItem(BaseModel):
    id: str
    text: str
    bbox: list[float] = Field(min_length=4, max_length=4)
    segments: list[SentenceSegment] = Field(default_factory=list)


class PageData(BaseModel):
    book_id: str
    page: int
    page_count: int
    width: float
    height: float
    rotation: int
    has_text: bool
    is_scanned: bool
    message: str | None = None
    words: list[WordItem]
    lines: list[LineItem]
    sentences: list[SentenceItem]


class WordAudioInfo(BaseModel):
    word: str
    accent: str
    available_accents: list[str]
    audio_url: str
    source_page: str
    provider: str
    license: str
    license_url: str | None = None
    attribution: str | None = None
    cached: bool


class SentenceAudioInfo(BaseModel):
    text: str
    synthetic: bool = True
    engine: str
    voice: str
    locale: str
    audio_url: str
    cached: bool
    note: str


class PhotoData(BaseModel):
    photo_id: str
    filename: str
    width: int
    height: int
    photo_url: str
    has_text: bool
    has_english: bool
    message: str | None = None
    quality_warning: str | None = None
    word_box_method: str
    ocr_engine: str
    words: list[WordItem]
    lines: list[LineItem]
    sentences: list[SentenceItem]
