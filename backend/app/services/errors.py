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
