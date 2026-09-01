"""Explore search built from topic descriptions."""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import monotonic

from app import config
from app.services.ai import (
    OpenAIClientConfigurationError,
    OpenAIResponseError,
    build_ai_search_plan,
    serialize_ai_search_plan,
)
from app.services.search.admission import run_repository_admission
from app.services.search.observability import (
    SearchLogContext,
    build_duration_ms,
    log_search_event,
)
from app.services.search.ranking import rank_repository_candidates
from app.services.search.retrieval import run_external_repository_retrieval

logger = logging.getLogger(__name__)

ExploreSearchProgressCallback = Callable[[dict[str, object]], None]


class ExploreSearchUnavailableError(RuntimeError):
    """Raised when every repository provider fails for one explore search."""

    def __init__(self, source_statuses: list[dict[str, object]]) -> None:
        super().__init__(
            "Repository search is temporarily unavailable across all providers."
        )
        self.source_statuses = source_statuses


class AiSearchPlanningError(RuntimeError):
    """Raised when the AI planner is unavailable."""


def run_explore_search(
    *,
    topic_description: str,
    progress_callback: ExploreSearchProgressCallback | None = None,
    soft_deadline_monotonic: float | None = None,
    hard_deadline_monotonic: float | None = None,
    log_context: SearchLogContext | None = None,
) -> dict[str, object]:
    """Run a read-only repository search from one topic description."""

    search_started_at = monotonic()
    current_stage = "ai_planning"
    repository_queries: tuple[str, ...] = ()
    retrieved = None
    if log_context is not None:
        log_search_event(
            logger=logger,
            event="explore_search_started",
            context=log_context,
            mode="async" if log_context.job_id else "sync",
        )

    try:
        planning_started_at = monotonic()
        ai_search_plan = _plan_explore_search(topic_description=topic_description)
        ai_search_plan_payload = serialize_ai_search_plan(ai_search_plan)
        repository_queries = tuple(ai_search_plan.queries)
        if log_context is not None:
            log_search_event(
                logger=logger,
                event="explore_ai_planning_completed",
                context=log_context,
                duration_ms=build_duration_ms(planning_started_at),
                query_count=len(repository_queries),
                planner=config.AI_PLANNER_MODE,
            )

        if not repository_queries:
            payload = {
                "topicDescription": topic_description,
                "aiSearchPlan": ai_search_plan_payload,
                "items": [],
                "sourceStatuses": [],
            }
            if log_context is not None:
                log_search_event(
                    logger=logger,
                    event="explore_search_completed",
                    context=log_context,
                    duration_ms=build_duration_ms(search_started_at),
                    query_count=0,
                    candidate_count=0,
                    visible_result_count=0,
                    response_build_duration_ms=0,
                    partial=False,
                    source_statuses=[],
                )
            return payload

        current_stage = "retrieval"
        if progress_callback is None:
            retrieval_options: dict[str, object] = {}
            if soft_deadline_monotonic is not None:
                retrieval_options["soft_deadline_monotonic"] = soft_deadline_monotonic
            if hard_deadline_monotonic is not None:
                retrieval_options["hard_deadline_monotonic"] = hard_deadline_monotonic
            retrieval_options["log_context"] = log_context
            retrieved = run_external_repository_retrieval(
                repository_queries,
                **retrieval_options,
            )
        else:
            retrieval_options = {
                "progress_callback": lambda partial: progress_callback(
                    _build_ranked_explore_search_payload(
                        topic_description=topic_description,
                        ai_search_plan_payload=ai_search_plan_payload,
                        retrieved=partial,
                        queries=repository_queries,
                    )
                ),
                "log_context": log_context,
            }
            if soft_deadline_monotonic is not None:
                retrieval_options["soft_deadline_monotonic"] = soft_deadline_monotonic
            if hard_deadline_monotonic is not None:
                retrieval_options["hard_deadline_monotonic"] = hard_deadline_monotonic
            retrieved = run_external_repository_retrieval(
                repository_queries,
                **retrieval_options,
            )
        if retrieved.successful_source_count == 0:
            if log_context is not None:
                log_search_event(
                    logger=logger,
                    event="explore_search_failed",
                    context=log_context,
                    level=logging.WARNING,
                    duration_ms=build_duration_ms(search_started_at),
                    stage="retrieval",
                    error_code="all_sources_unavailable",
                    error_message="Repository search is temporarily unavailable across all providers.",
                    partial=retrieved.partial,
                    query_count=len(repository_queries),
                    source_statuses=_summarize_source_statuses(retrieved.source_statuses),
                )
            raise ExploreSearchUnavailableError(list(retrieved.source_statuses))

        current_stage = "admission"
        admission = run_repository_admission(
            retrieved.candidates,
            log_context=log_context,
        )
        current_stage = "ranking"
        ranking = rank_repository_candidates(
            tuple(
                evaluated_candidate.candidate
                for evaluated_candidate in admission.visible_candidates
            ),
            queries=repository_queries,
        )
        if log_context is not None:
            visible_candidates = ranking.visible_candidates
            log_search_event(
                logger=logger,
                event="explore_ranking_completed",
                context=log_context,
                candidate_count=len(retrieved.candidates),
                admitted_candidate_count=len(admission.visible_candidates),
                visible_result_count=len(visible_candidates),
                relevance_cutoff=ranking.relevance_cutoff,
                top_score=(ranking.ranked_candidates[0].score if ranking.ranked_candidates else None),
                lowest_visible_score=(visible_candidates[-1].score if visible_candidates else None),
            )
        current_stage = "response_build"
        response_build_started_at = monotonic()
        payload = _build_explore_search_payload(
            topic_description=topic_description,
            ai_search_plan_payload=ai_search_plan_payload,
            retrieved=retrieved,
            ranking=ranking,
        )
        response_build_duration_ms = build_duration_ms(response_build_started_at)
        if log_context is not None:
            log_search_event(
                logger=logger,
                event="explore_search_completed",
                context=log_context,
                duration_ms=build_duration_ms(search_started_at),
                query_count=len(repository_queries),
                candidate_count=len(retrieved.candidates),
                admitted_candidate_count=len(admission.visible_candidates),
                visible_result_count=len(ranking.visible_candidates),
                relevance_cutoff=ranking.relevance_cutoff,
                response_build_duration_ms=response_build_duration_ms,
                partial=retrieved.partial,
                warning_count=len(retrieved.warnings),
                source_statuses=_summarize_source_statuses(retrieved.source_statuses),
            )
        return payload
    except (AiSearchPlanningError, ExploreSearchUnavailableError):
        raise
    except Exception as exc:
        if log_context is not None:
            log_search_event(
                logger=logger,
                event="explore_search_failed",
                context=log_context,
                level=logging.ERROR,
                duration_ms=build_duration_ms(search_started_at),
                stage=current_stage,
                error_code="unexpected_error",
                error_message=str(exc),
                partial=bool(getattr(retrieved, "partial", False)),
                query_count=len(repository_queries),
                source_statuses=_summarize_source_statuses(
                    getattr(retrieved, "source_statuses", ())
                ),
            )
        raise


def _plan_explore_search(*, topic_description: str):
    try:
        return build_ai_search_plan(topic_description=topic_description)
    except (OpenAIClientConfigurationError, OpenAIResponseError, RuntimeError) as exc:
        logger.exception(
            "AI search planning failed for topic=%r: %s",
            topic_description[:200],
            exc,
        )
        raise AiSearchPlanningError(
            "AI search planning is temporarily unavailable."
        ) from exc


def _build_explore_search_payload(
    *,
    topic_description: str,
    ai_search_plan_payload: dict[str, object],
    retrieved,
    ranking,
) -> dict[str, object]:
    items: list[dict[str, object]] = []
    for ranked_candidate in ranking.visible_candidates:
        candidate = ranked_candidate.candidate
        signal = candidate.signal

        items.append(
            {
                "itemId": signal.item_id,
                "source": signal.source,
                "fullName": signal.title,
                "url": signal.url,
                "description": _read_candidate_description(signal.raw_text),
                "language": signal.payload.get("language"),
                "stars": signal.payload.get("stars"),
                "query": signal.payload.get("query"),
                "score": ranked_candidate.score,
                "reason": "Matched by SciScope search.",
            }
        )

    return {
        "topicDescription": topic_description,
        "aiSearchPlan": dict(ai_search_plan_payload),
        "items": items,
        "sourceStatuses": list(retrieved.source_statuses),
        "partial": retrieved.partial,
        "message": _build_partial_message(retrieved.warnings) if retrieved.partial else None,
    }


def _read_candidate_description(raw_text: str) -> str:
    parts = [part.strip() for part in raw_text.splitlines() if part.strip()]
    if len(parts) >= 2:
        return parts[1]
    return ""


def _build_ranked_explore_search_payload(
    *,
    topic_description: str,
    ai_search_plan_payload: dict[str, object],
    retrieved,
    queries: tuple[str, ...],
) -> dict[str, object]:
    admission = run_repository_admission(retrieved.candidates)
    ranking = rank_repository_candidates(
        tuple(
            evaluated_candidate.candidate
            for evaluated_candidate in admission.visible_candidates
        ),
        queries=queries,
    )
    return _build_explore_search_payload(
        topic_description=topic_description,
        ai_search_plan_payload=ai_search_plan_payload,
        retrieved=retrieved,
        ranking=ranking,
    )


def _build_partial_message(warnings: tuple[str, ...]) -> str | None:
    if not warnings:
        return "Search completed with partial coverage."

    visible_warnings = list(dict.fromkeys(warnings))
    summary = "; ".join(visible_warnings[:2])
    if len(visible_warnings) > 2:
        summary += f"; and {len(visible_warnings) - 2} more"
    return f"Search completed with partial coverage: {summary}"


def _summarize_source_statuses(
    source_statuses: tuple[dict[str, object], ...] | list[dict[str, object]],
) -> list[dict[str, object]]:
    return [
        {
            "source": status.get("source"),
            "status": status.get("status"),
            "candidateCount": status.get("candidateCount"),
            "error": status.get("error"),
        }
        for status in source_statuses
    ]
