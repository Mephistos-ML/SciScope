"""Source discovery orchestration for external retrieval."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from queue import Empty, Queue

from app.services.search.observability.context import SearchLogContext
from app.services.search.retrieval.lanes import (
    LaneResult,
    RetrievalProgressCallback,
    build_lane_outcome,
    consume_lane_result,
    emit_retrieval_progress,
    start_lane_worker,
)
from app.services.search.retrieval.timeouts import (
    build_deadline_warning,
    build_lane_deadline_monotonic,
    read_wait_timeout_seconds,
)
from app.services.search.retrieval.models import RetrievalLane

logger = logging.getLogger(__name__)


def discover_candidates_across_sources(
    queries: Sequence[str],
    *,
    lanes: Sequence[RetrievalLane],
    progress_callback: RetrievalProgressCallback | None = None,
    soft_deadline_monotonic: float | None = None,
    hard_deadline_monotonic: float | None = None,
    log_context: SearchLogContext | None = None,
) -> dict[str, object]:
    """Discover repository candidates across all active retrieval lanes."""

    candidates = []
    source_statuses_by_source: dict[str, dict[str, object]] = {}
    successful_sources: set[str] = set()
    warnings: list[str] = []
    partial = False
    lane_outcomes = []

    lane_results: Queue[LaneResult] = Queue()
    for lane in lanes:
        start_lane_worker(
            source_name=lane.source,
            channel_name=lane.channel,
            discover_candidates=lane.discover,
            queries=queries,
            deadline_monotonic=build_lane_deadline_monotonic(
                channel_name=lane.channel,
                soft_deadline_monotonic=soft_deadline_monotonic,
                hard_deadline_monotonic=hard_deadline_monotonic,
            ),
            result_queue=lane_results,
        )

    remaining_lane_count = len(lanes)
    while remaining_lane_count > 0:
        wait_timeout_seconds = read_wait_timeout_seconds(
            soft_deadline_monotonic=soft_deadline_monotonic,
            hard_deadline_monotonic=hard_deadline_monotonic,
        )
        try:
            lane_result = (
                lane_results.get(
                    timeout=wait_timeout_seconds,
                )
                if wait_timeout_seconds is not None
                else lane_results.get()
            )
        except Empty:
            partial = True
            warning, log_level = build_deadline_warning(
                soft_deadline_monotonic=soft_deadline_monotonic,
                hard_deadline_monotonic=hard_deadline_monotonic,
            )
            warnings.append(warning)
            logger.log(log_level, warning)
            break

        remaining_lane_count -= 1
        lane_outcomes.append(build_lane_outcome(lane_result))
        lane_partial, lane_warning = consume_lane_result(
            lane_result,
            queries=queries,
            candidates=candidates,
            source_statuses_by_source=source_statuses_by_source,
            successful_sources=successful_sources,
            log_context=log_context,
        )
        if lane_partial:
            partial = True
        if lane_warning is not None:
            warnings.append(lane_warning)
        emit_retrieval_progress(
            candidates,
            source_statuses_by_source,
            successful_sources,
            progress_callback,
            partial=partial,
            warnings=warnings,
        )

    source_statuses = list(source_statuses_by_source.values())
    if partial and not source_statuses and warnings:
        source_statuses = [
            {
                "source": "system",
                "status": "timed_out",
                "candidateCount": 0,
                "error": warnings[0],
            }
        ]

    return {
        "candidates": candidates,
        "source_statuses": source_statuses,
        "successful_source_count": len(successful_sources),
        "partial": partial,
        "warnings": warnings,
        "lane_outcomes": lane_outcomes,
    }
