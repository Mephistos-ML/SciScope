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
from app.services.search.explore.canonical import select_canonical_candidates
from app.services.search.catalog import (
    persist_catalog_candidates,
    retrieve_catalog_candidates,
)
from app.services.search.explore.evaluation import build_explore_search_evaluation
from app.services.search.explore.response import (
    ExploreResponseMode,
    build_empty_explore_search_payload,
    build_explore_search_payload,
)
from app.services.search.observability import (
    SearchLogContext,
    build_duration_ms,
    log_search_event,
)
from app.services.search.retrieval import (
    RetrievedCandidates,
    merge_repository_candidates,
    run_external_repository_retrieval,
)

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
    response_mode: ExploreResponseMode = "canonical",
    progress_callback: ExploreSearchProgressCallback | None = None,
    soft_deadline_monotonic: float | None = None,
    hard_deadline_monotonic: float | None = None,
    log_context: SearchLogContext | None = None,
    database_url: str = config.DATABASE_URL,
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
            response_mode=response_mode,
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
            payload = build_empty_explore_search_payload(
                topic_description=topic_description,
                ai_search_plan_payload=ai_search_plan_payload,
                response_mode=response_mode,
            )
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

        current_stage = "local_retrieval"
        local_candidates = retrieve_catalog_candidates(
            repository_queries,
            database_url=database_url,
        )
        local_retrieved = RetrievedCandidates(
            candidates=local_candidates,
            source_statuses=(),
            successful_source_count=1 if local_candidates else 0,
        )
        local_evaluation = build_explore_search_evaluation(
            local_retrieved,
            queries=repository_queries,
            log_context=log_context,
        )
        if len(select_canonical_candidates(local_evaluation)) >= config.EXPLORE_LOCAL_RESULT_MINIMUM:
            retrieved = local_retrieved
            evaluation = local_evaluation
        else:
            current_stage = "external_retrieval"
            external_retrieved = _run_external_retrieval(
                repository_queries,
                local_candidates=local_candidates,
                topic_description=topic_description,
                ai_search_plan_payload=ai_search_plan_payload,
                response_mode=response_mode,
                progress_callback=progress_callback,
                soft_deadline_monotonic=soft_deadline_monotonic,
                hard_deadline_monotonic=hard_deadline_monotonic,
                log_context=log_context,
            )
            retrieved = RetrievedCandidates(
                candidates=merge_repository_candidates(
                    (*local_candidates, *external_retrieved.candidates)
                ),
                source_statuses=external_retrieved.source_statuses,
                successful_source_count=(
                    external_retrieved.successful_source_count
                    + (1 if local_candidates else 0)
                ),
                partial=external_retrieved.partial,
                warnings=external_retrieved.warnings,
            )
            evaluation = build_explore_search_evaluation(
                retrieved,
                queries=repository_queries,
                log_context=log_context,
            )
            admitted_repository_ids = {
                item.candidate.repository_id
                for item in evaluation.admission.visible_candidates
            }
            persist_catalog_candidates(
                tuple(
                    candidate
                    for candidate in external_retrieved.candidates
                    if candidate.repository_id in admitted_repository_ids
                ),
                database_url=database_url,
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

        current_stage = "evaluation"
        if log_context is not None:
            visible_candidates = select_canonical_candidates(evaluation)
            log_search_event(
                logger=logger,
                event="explore_ranking_completed",
                context=log_context,
                candidate_count=len(retrieved.candidates),
                admitted_candidate_count=len(evaluation.admission.visible_candidates),
                visible_result_count=len(visible_candidates),
                relevance_cutoff=evaluation.ranking.relevance_cutoff,
                top_score=(
                    evaluation.ranking.ranked_candidates[0].score
                    if evaluation.ranking.ranked_candidates
                    else None
                ),
                lowest_visible_score=(visible_candidates[-1].score if visible_candidates else None),
            )
        current_stage = "response_build"
        response_build_started_at = monotonic()
        payload = build_explore_search_payload(
            topic_description=topic_description,
            ai_search_plan_payload=ai_search_plan_payload,
            evaluation=evaluation,
            response_mode=response_mode,
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
                admitted_candidate_count=len(evaluation.admission.visible_candidates),
                visible_result_count=len(visible_candidates),
                relevance_cutoff=evaluation.ranking.relevance_cutoff,
                response_mode=response_mode,
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


def _run_external_retrieval(
    queries: tuple[str, ...],
    *,
    local_candidates,
    topic_description: str,
    ai_search_plan_payload: dict[str, object],
    response_mode: ExploreResponseMode,
    progress_callback: ExploreSearchProgressCallback | None,
    soft_deadline_monotonic: float | None,
    hard_deadline_monotonic: float | None,
    log_context: SearchLogContext | None,
) -> RetrievedCandidates:
    retrieval_options: dict[str, object] = {"log_context": log_context}
    if soft_deadline_monotonic is not None:
        retrieval_options["soft_deadline_monotonic"] = soft_deadline_monotonic
    if hard_deadline_monotonic is not None:
        retrieval_options["hard_deadline_monotonic"] = hard_deadline_monotonic
    if progress_callback is not None:
        retrieval_options["progress_callback"] = lambda partial: progress_callback(
            _build_explore_search_progress_payload(
                topic_description=topic_description,
                ai_search_plan_payload=ai_search_plan_payload,
                retrieved=RetrievedCandidates(
                    candidates=merge_repository_candidates(
                        (*local_candidates, *partial.candidates)
                    ),
                    source_statuses=partial.source_statuses,
                    successful_source_count=(
                        partial.successful_source_count + (1 if local_candidates else 0)
                    ),
                    partial=partial.partial,
                    warnings=partial.warnings,
                ),
                queries=queries,
                response_mode=response_mode,
            )
        )
    return run_external_repository_retrieval(queries, **retrieval_options)


def _build_explore_search_progress_payload(
    *,
    topic_description: str,
    ai_search_plan_payload: dict[str, object],
    retrieved,
    queries: tuple[str, ...],
    response_mode: ExploreResponseMode,
) -> dict[str, object]:
    evaluation = build_explore_search_evaluation(
        retrieved,
        queries=queries,
    )
    return build_explore_search_payload(
        topic_description=topic_description,
        ai_search_plan_payload=ai_search_plan_payload,
        evaluation=evaluation,
        response_mode=response_mode,
    )


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
