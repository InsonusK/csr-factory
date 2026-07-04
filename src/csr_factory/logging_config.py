"""Logging configuration for csr_factory."""

from __future__ import annotations

import logging
import sys


DEFAULT_FORMAT = "%(levelname)s: %(message)s"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure root logging for the application.

    Adds a stderr handler with the default format if the root logger has no
    handlers, and sets the root logger level to ``level``.

    Args:
        level: Logging level (default: ``logging.INFO``).

    Returns:
        The configured root logger.
    """
    logger = logging.getLogger()
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger
