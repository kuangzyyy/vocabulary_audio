"""Domain errors that map cleanly to HTTP responses."""

from __future__ import annotations


class PdfError(Exception):
    """Base class for user-facing PDF errors."""

    status_code = 400


class InvalidPdfError(PdfError):
    status_code = 400


class EncryptedPdfError(PdfError):
    status_code = 400


class EmptyPdfError(PdfError):
    status_code = 400


class UploadTooLargeError(PdfError):
    status_code = 413


class BookNotFoundError(PdfError):
    status_code = 404


class PageNotFoundError(PdfError):
    status_code = 404


class PageExtractionError(PdfError):
    status_code = 422


class AudioError(Exception):
    """Base class for word-audio errors."""

    status_code = 502


class InvalidWordError(AudioError):
    status_code = 400


class AudioUnavailableError(AudioError):
    status_code = 404


class AudioUpstreamError(AudioError):
    status_code = 502


class AudioRateLimitedError(AudioError):
    status_code = 503

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class AudioCacheError(AudioError):
    status_code = 500


class InvalidSentenceError(AudioError):
    status_code = 400


class SentenceTtsError(AudioError):
    status_code = 503


class PhotoError(Exception):
    """Base class for photo upload/OCR errors."""

    status_code = 400


class InvalidPhotoError(PhotoError):
    status_code = 400


class PhotoTooLargeError(PhotoError):
    status_code = 413


class PhotoOcrError(PhotoError):
    status_code = 422


class PhotoNotFoundError(PhotoError):
    status_code = 404
