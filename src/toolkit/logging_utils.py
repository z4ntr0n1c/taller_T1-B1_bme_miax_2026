"""Logging configuration for the ``toolkit`` package.

Each module creates its own logger with ``logging.getLogger(__name__)``; all of
them hang under the root ``toolkit`` logger, which can be configured once via
:func:`setup_logging`.
"""

from __future__ import annotations

import logging
import sys

PACKAGE_LOGGER = "toolkit"
DEFAULT_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
DEFAULT_DATEFMT = "%H:%M:%S"


def setup_logging(level: int | str = logging.INFO, fmt: str = DEFAULT_FORMAT) -> logging.Logger:
    """Configure the package root logger for console output.

    Idempotent: calling it multiple times (e.g. in a notebook with autoreload)
    will not duplicate log handlers.

    Args:
        level: Minimum log level (``"DEBUG"``, ``"INFO"``, ``logging.WARNING``, ...).
        fmt: Log line format string.

    Returns:
        The configured ``toolkit`` logger.
    """
    logger = logging.getLogger(PACKAGE_LOGGER)
    logger.setLevel(level)
    existing_toolkit_handlers = filter(
        lambda h: getattr(h, "_toolkit_handler", False),
        list(logger.handlers),
    )
    list(map(logger.removeHandler, existing_toolkit_handlers))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt=DEFAULT_DATEFMT))
    handler._toolkit_handler = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    logger.propagate = False
    return logger

