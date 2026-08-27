"""Application logging configuration."""

from __future__ import annotations

import logging
import sys

from app.config import APP_LOG_LEVEL


def configure_logging() -> None:
    """Apply the configured log level to application loggers."""

    level_name = APP_LOG_LEVEL.upper()
    level = getattr(logging, level_name, logging.INFO)
    app_logger = logging.getLogger("app")

    if not app_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        handler.setLevel(level)
        app_logger.addHandler(handler)

    app_logger.setLevel(level)
    app_logger.propagate = False
