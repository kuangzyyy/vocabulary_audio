"""Logging helpers that keep private text out of access logs."""

from __future__ import annotations

import logging


class RedactQueryFilter(logging.Filter):
    """Strip query strings from Uvicorn access log request paths.

    The app passes clicked words and sentences as query parameters for simple
    GET audio lookup. Those are user content and must not be written to logs.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3:
            path = args[2]
            if isinstance(path, str) and "?" in path:
                record.args = (args[0], args[1], path.split("?", 1)[0], *args[3:])
        return True


def install_access_log_filter() -> None:
    """Install the filter once on the Uvicorn access logger."""
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, RedactQueryFilter) for item in logger.filters):
        logger.addFilter(RedactQueryFilter())
