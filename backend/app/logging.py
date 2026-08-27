"""Application logging configuration."""

from __future__ import annotations

import logging

from app.config import APP_LOG_LEVEL


def configure_logging() -> None:
    """Apply the configured log level to application loggers."""

    level_name = APP_LOG_LEVEL.upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.getLogger().setLevel(level)
    logging.getLogger("app").setLevel(level)
