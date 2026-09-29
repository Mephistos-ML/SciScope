"""Structured logging helpers for search flows."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from time import monotonic

from app.services.search.observability.context import SearchLogContext


FLY_EVENT_NAMES = {
    "explore_search_started": "search_run_started",
    "explore_ranking_completed": "search_stage_completed",
    "explore_search_completed": "search_run_completed",
    "explore_search_failed": "search_run_failed",
    "explore_retrieval_lane_failed": "search_provider_degraded",
    "explore_retrieval_query_failed": "search_provider_degraded",
}
UNSAFE_FIELD_NAMES = {"query", "queries", "url", "urls", "match_evidence"}


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
    """Write one safe, product-level structured event to Fly stdout."""

    fly_event = FLY_EVENT_NAMES.get(event)
    if fly_event is None:
        return

    payload = {
        "event": fly_event,
        "request_id": context.request_id,
        "run_id": context.run_id,
        "topic_hash": context.topic_hash,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    payload.update(
        {key: value for key, value in fields.items() if key not in UNSAFE_FIELD_NAMES}
    )
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
