"""Tests for application logging configuration."""

from __future__ import annotations

import logging

from app import logging as app_logging


def test_configure_logging_adds_one_app_handler(monkeypatch) -> None:
    app_logger = logging.getLogger("app")
    original_handlers = list(app_logger.handlers)
    original_level = app_logger.level
    original_propagate = app_logger.propagate

    for handler in list(app_logger.handlers):
        app_logger.removeHandler(handler)

    monkeypatch.setattr(app_logging, "APP_LOG_LEVEL", "INFO")

    try:
        app_logging.configure_logging()
        app_logging.configure_logging()

        assert len(app_logger.handlers) == 1
        assert app_logger.level == logging.INFO
        assert app_logger.propagate is False
    finally:
        for handler in list(app_logger.handlers):
            app_logger.removeHandler(handler)
        for handler in original_handlers:
            app_logger.addHandler(handler)
        app_logger.setLevel(original_level)
        app_logger.propagate = original_propagate
