"""Tests for safe product-level Fly search events."""

from __future__ import annotations

import json
import logging

from app.services.search.observability.context import SearchLogContext
from app.services.search.observability.service import log_search_event


def test_fly_event_uses_run_identity_and_excludes_raw_query(caplog) -> None:
    logger = logging.getLogger("tests.search_observability")
    with caplog.at_level(logging.INFO, logger=logger.name):
        log_search_event(
            logger=logger,
            event="explore_retrieval_query_failed",
            context=SearchLogContext(
                request_id="request_1",
                run_id="run_1",
                topic_hash="topic_hash",
            ),
            source="github",
            channel="code_search",
            query="raw private query",
            error_code="timed_out",
        )

    payload = json.loads(caplog.records[0].message.removeprefix("search_event="))
    assert payload["event"] == "search_provider_degraded"
    assert payload["run_id"] == "run_1"
    assert payload["source"] == "github"
    assert "query" not in payload


def test_non_product_event_is_not_emitted(caplog) -> None:
    logger = logging.getLogger("tests.search_observability")
    with caplog.at_level(logging.INFO, logger=logger.name):
        log_search_event(
            logger=logger,
            event="explore_ai_planning_completed",
            context=SearchLogContext(
                request_id="request_1",
                topic_hash="topic_hash",
            ),
        )

    assert not caplog.records
