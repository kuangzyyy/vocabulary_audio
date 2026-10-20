"""Tests for privacy-safe access logging."""

from __future__ import annotations

import logging

from backend.app.logging_utils import RedactQueryFilter, install_access_log_filter


def make_record(path: str) -> logging.LogRecord:
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %s',
        args=("127.0.0.1:1234", "GET", path, "1.1", 200),
        exc_info=None,
    )
    return record


def test_query_text_is_removed_from_access_log() -> None:
    record = make_record("/api/audio/word?text=private-word&accent=auto")

    assert RedactQueryFilter().filter(record) is True
    assert record.args[2] == "/api/audio/word"
    assert "private-word" not in record.getMessage()


def test_sentence_text_is_removed_from_access_log() -> None:
    record = make_record("/api/audio/sentence?text=private%20sentence")

    RedactQueryFilter().filter(record)
    assert record.args[2] == "/api/audio/sentence"
    assert "private%20sentence" not in record.getMessage()


def test_path_without_query_is_unchanged() -> None:
    record = make_record("/api/photos/0123456789abcdef0123456789abcdef/file")

    RedactQueryFilter().filter(record)
    assert record.args[2] == "/api/photos/0123456789abcdef0123456789abcdef/file"


def test_install_is_idempotent() -> None:
    logger = logging.getLogger("uvicorn.access")
    install_access_log_filter()
    after_first = len(logger.filters)
    install_access_log_filter()
    assert len(logger.filters) == after_first
    assert any(isinstance(item, RedactQueryFilter) for item in logger.filters)
