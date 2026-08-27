"""External repository retrieval orchestration for Explore."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from time import monotonic

from app.services.search.observability import (
    SearchLogContext,
    build_duration_ms,
    log_search_event,
)
from app.services.search.retrieval.discovery import (
    RetrievalProgressCallback,
    SourceRetriever,
    discover_candidates_across_sources,
)
from app.services.search.retrieval.merge import merge_retrieval_hits
from app.services.search.retrieval.models import RetrievedCandidates

logger = logging.getLogger(__name__)


def run_external_repository_retrieval(
    queries: Sequence[str],
    *,
    discoverers: Sequence[SourceRetriever] | None = None,
    progress_callback: RetrievalProgressCallback | None = None,
    soft_deadline_monotonic: float | None = None,
    hard_deadline_monotonic: float | None = None,
    log_context: SearchLogContext | None = None,
) -> RetrievedCandidates:
    """Retrieve and deduplicate repository candidates across active sources."""

    retrieval_started_at = monotonic() if log_context is not None else None
    retrieval_state = discover_candidates_across_sources(
        queries,
        discoverers=discoverers,
        progress_callback=progress_callback,
        soft_deadline_monotonic=soft_deadline_monotonic,
        hard_deadline_monotonic=hard_deadline_monotonic,
        log_context=log_context,
    )
    candidates = merge_retrieval_hits(tuple(retrieval_state["candidates"]))
    retrieved = RetrievedCandidates(
        candidates=candidates,
        source_statuses=tuple(retrieval_state["source_statuses"]),
        successful_source_count=int(retrieval_state["successful_source_count"]),
        partial=bool(retrieval_state["partial"]),
        warnings=tuple(str(warning) for warning in retrieval_state["warnings"]),
    )
    if log_context is not None and retrieval_started_at is not None:
        log_search_event(
            logger=logger,
            event="explore_retrieval_completed",
            context=log_context,
            duration_ms=build_duration_ms(retrieval_started_at),
            query_count=len(queries),
            candidate_hit_count=len(retrieval_state["candidates"]),
            candidate_count=len(candidates),
            successful_source_count=retrieved.successful_source_count,
            partial=retrieved.partial,
            warning_count=len(retrieved.warnings),
        )
    return retrieved
