"""Structured logging helpers for search flows."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from time import monotonic

from app.services.search.observability.context import SearchLogContext


def build_duration_ms(started_at_monotonic: float) -> int:
    """Return elapsed wall-clock time in whole milliseconds."""

    return max(0, int((monotonic() - started_at_monotonic) * 1000))


def log_search_event(
    *,
    logger: logging.Logger,
    event: str,
    context: SearchLogContext,
    level: int = logging.INFO,
    **fields: object,
) -> None:
    """Write one structured search event to the active logger."""

    payload = {
        "event": event,
        "request_id": context.request_id,
        "job_id": context.job_id,
        "topic_hash": context.topic_hash,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    payload.update(fields)
    compact_payload = {
        key: value
        for key, value in payload.items()
        if value is not None
    }
    logger.log(
        level,
        "search_event=%s",
        json.dumps(compact_payload, sort_keys=True, default=str),
    )
