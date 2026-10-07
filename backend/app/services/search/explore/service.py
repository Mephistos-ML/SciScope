"""Explore search built from topic descriptions."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from time import monotonic

from app import config
from app.models.search_run import (
    SearchRankingCandidateReport,
    SearchProviderOutcomeReport,
    SearchStageReport,
)
from app.services.ai.openai.client import (
    OpenAIClientConfigurationError,
    OpenAIResponseError,
)
from app.services.ai.planner import build_ai_search_plan
from app.services.ai.search_plans import (
    serialize_ai_search_plan,
)
from app.services.search.explore.canonical import select_canonical_candidates
from app.services.search.explore.execution import ExploreQueryAttempt, ExploreSearchExecution
from app.services.search.catalog import (
    persist_catalog_candidates,
    retrieve_catalog_candidates,
)
from app.services.search.explore.evaluation import build_explore_search_evaluation
from app.services.search.explore.response import (
    build_empty_explore_search_payload,
    build_explore_search_payload,
)
from app.services.search.observability.service import (
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
ExploreSearchExecutionCallback = Callable[[ExploreSearchExecution], None]
ExploreSearchStageReportCallback = Callable[[SearchStageReport], None]
MAX_TIMEOUT_ATTEMPTS_PER_QUERY = 3


@dataclass(frozen=True)
class _RetrievalSequence:
    retrieved: RetrievedCandidates
    executed_queries: tuple[str, ...]
    attempts: tuple[ExploreQueryAttempt, ...]
    external_candidates: tuple
    catalog_retrieval_duration_ms: int
    candidate_merge_duration_ms: int


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
    execution_callback: ExploreSearchExecutionCallback | None = None,
    stage_report_callback: ExploreSearchStageReportCallback | None = None,
    log_context: SearchLogContext | None = None,
    database_url: str = config.DATABASE_URL,
) -> dict[str, object]:
    """Run a read-only repository search from one topic description."""

    search_started_at = monotonic()
    current_stage = "ai_planning"
    planned_queries: tuple[str, ...] = ()
    executed_queries: tuple[str, ...] = ()
    retrieved = None
    planning_duration_ms = 0
    retrieval_duration_ms = 0
    evaluation_duration_ms = 0
    if log_context is not None:
        log_search_event(
            logger=logger,
            event="explore_search_started",
            context=log_context,
            mode="async" if log_context.run_id else "sync",
        )

    try:
        planning_started_at = monotonic()
        ai_search_plan = _plan_explore_search(topic_description=topic_description)
        ai_search_plan_payload = serialize_ai_search_plan(ai_search_plan)
        planned_queries = tuple(ai_search_plan.queries)
        executed_queries = planned_queries[:1]
        planning_duration_ms = build_duration_ms(planning_started_at)
        if log_context is not None:
            log_search_event(
                logger=logger,
                event="explore_ai_planning_completed",
                context=log_context,
                duration_ms=planning_duration_ms,
                query_count=len(planned_queries),
                planner=config.AI_PLANNER_MODE,
                planner_model=(
                    config.OPENAI_MODEL if config.AI_PLANNER_MODE == "openai" else None
                ),
                planner_reasoning_effort=(
                    config.OPENAI_REASONING_EFFORT
                    if config.AI_PLANNER_MODE == "openai"
                    else None
                ),
            )

        if not executed_queries:
            response_build_started_at = monotonic()
            payload = build_empty_explore_search_payload(
                topic_description=topic_description,
                ai_search_plan_payload=ai_search_plan_payload,
            )
            response_build_duration_ms = build_duration_ms(response_build_started_at)
            if log_context is not None:
                log_search_event(
                    logger=logger,
                    event="explore_search_completed",
                    context=log_context,
                    duration_ms=build_duration_ms(search_started_at),
                    query_count=0,
                    candidate_count=0,
                    visible_result_count=0,
                    ai_planning_duration_ms=planning_duration_ms,
                    retrieval_duration_ms=0,
                    evaluation_duration_ms=0,
                    response_build_duration_ms=response_build_duration_ms,
                    partial=False,
                    source_statuses=[],
                )
            return payload

        retrieval_started_at = monotonic()
        current_stage = "external_retrieval"
        retrieval_sequence = _retrieve_planned_queries(
            queries=planned_queries,
            topic_description=topic_description,
            ai_search_plan_payload=ai_search_plan_payload,
            progress_callback=progress_callback,
            log_context=log_context,
            database_url=database_url,
        )
        executed_queries = retrieval_sequence.executed_queries
        retrieved = retrieval_sequence.retrieved
        retrieval_duration_ms = build_duration_ms(retrieval_started_at)
        evaluation_started_at = monotonic()
        evaluation = build_explore_search_evaluation(
            retrieved,
            queries=executed_queries,
            log_context=log_context,
        )
        admitted_repository_ids = {
            item.candidate.repository_id
            for item in evaluation.admission.visible_candidates
        }
        persistence_started_at = monotonic()
        persist_catalog_candidates(
            tuple(
                candidate
                for candidate in retrieval_sequence.external_candidates
                if candidate.repository_id in admitted_repository_ids
            ),
            database_url=database_url,
        )
        repository_persistence_duration_ms = build_duration_ms(persistence_started_at)
        evaluation_duration_ms = build_duration_ms(evaluation_started_at)

        execution = ExploreSearchExecution(
            ai_search_plan=ai_search_plan,
            executed_queries=executed_queries,
            retrieved=retrieved,
            attempts=retrieval_sequence.attempts,
        )
        if execution_callback is not None:
            execution_callback(execution)

        visible_candidates = select_canonical_candidates(evaluation)
        if retrieved.successful_source_count == 0:
            if stage_report_callback is not None:
                stage_report_callback(
                    _build_stage_report(
                        evaluation=evaluation,
                        executed_queries=execution.executed_queries,
                        retrieved=retrieved,
                        admitted_candidate_count=len(evaluation.admission.visible_candidates),
                        visible_candidate_count=len(visible_candidates),
                        ai_planning_duration_ms=planning_duration_ms,
                        retrieval_duration_ms=retrieval_duration_ms,
                        evaluation_duration_ms=evaluation_duration_ms,
                        response_build_duration_ms=0,
                        total_duration_ms=build_duration_ms(search_started_at),
                    )
                )
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
                    query_count=len(executed_queries),
                    source_statuses=_summarize_source_statuses(retrieved.source_statuses),
                )
            raise ExploreSearchUnavailableError(list(retrieved.source_statuses))

        current_stage = "evaluation"
        if log_context is not None:
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
                ai_planning_duration_ms=planning_duration_ms,
                retrieval_duration_ms=retrieval_duration_ms,
                evaluation_duration_ms=evaluation_duration_ms,
                stage_wall_time_ms=build_duration_ms(search_started_at),
            )
        current_stage = "response_build"
        response_build_started_at = monotonic()
        payload = build_explore_search_payload(
            topic_description=topic_description,
            ai_search_plan_payload=ai_search_plan_payload,
            evaluation=evaluation,
            can_expand=bool(execution.pending_queries),
        )
        response_build_duration_ms = build_duration_ms(response_build_started_at)
        if stage_report_callback is not None:
            stage_report_callback(
                _build_stage_report(
                    evaluation=evaluation,
                    executed_queries=execution.executed_queries,
                    retrieved=retrieved,
                    admitted_candidate_count=len(evaluation.admission.visible_candidates),
                    visible_candidate_count=len(visible_candidates),
                    ai_planning_duration_ms=planning_duration_ms,
                    retrieval_duration_ms=retrieval_duration_ms,
                    evaluation_duration_ms=evaluation_duration_ms,
                    response_build_duration_ms=response_build_duration_ms,
                    total_duration_ms=build_duration_ms(search_started_at),
                    catalog_retrieval_duration_ms=(
                        retrieval_sequence.catalog_retrieval_duration_ms
                    ),
                    candidate_merge_duration_ms=(
                        retrieval_sequence.candidate_merge_duration_ms
                    ),
                    admission_duration_ms=evaluation.admission_duration_ms,
                    ranking_duration_ms=evaluation.ranking_duration_ms,
                    repository_persistence_duration_ms=repository_persistence_duration_ms,
                )
            )
        if log_context is not None:
            log_search_event(
                logger=logger,
                event="explore_search_completed",
                context=log_context,
                duration_ms=build_duration_ms(search_started_at),
                query_count=len(executed_queries),
                candidate_count=len(retrieved.candidates),
                admitted_candidate_count=len(evaluation.admission.visible_candidates),
                visible_result_count=len(visible_candidates),
                relevance_cutoff=evaluation.ranking.relevance_cutoff,
                ai_planning_duration_ms=planning_duration_ms,
                retrieval_duration_ms=retrieval_duration_ms,
                evaluation_duration_ms=evaluation_duration_ms,
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
                query_count=len(executed_queries),
                source_statuses=_summarize_source_statuses(
                    getattr(retrieved, "source_statuses", ())
                ),
            )
        raise


def expand_explore_search(
    *,
    topic_description: str,
    execution: ExploreSearchExecution,
    execution_callback: ExploreSearchExecutionCallback | None = None,
    stage_report_callback: ExploreSearchStageReportCallback | None = None,
    log_context: SearchLogContext | None = None,
    database_url: str = config.DATABASE_URL,
) -> dict[str, object]:
    """Run exactly one pending query and rerank the accumulated candidate pool."""

    next_queries = execution.pending_queries
    if not next_queries:
        raise ValueError("Explore search plan has no pending queries.")

    search_started_at = monotonic()
    ai_search_plan_payload = serialize_ai_search_plan(execution.ai_search_plan)
    retrieval_started_at = monotonic()
    retrieval_sequence = _retrieve_planned_queries(
        queries=next_queries,
        topic_description=topic_description,
        ai_search_plan_payload=ai_search_plan_payload,
        progress_callback=None,
        log_context=log_context,
        database_url=database_url,
    )
    retrieved = _merge_retrieved_candidates(execution.retrieved, retrieval_sequence.retrieved)
    retrieval_duration_ms = build_duration_ms(retrieval_started_at)

    evaluation_started_at = monotonic()
    executed_queries = (*execution.executed_queries, *retrieval_sequence.executed_queries)
    evaluation = build_explore_search_evaluation(
        retrieved,
        queries=executed_queries,
        log_context=log_context,
    )
    admitted_repository_ids = {
        item.candidate.repository_id
        for item in evaluation.admission.visible_candidates
    }
    persistence_started_at = monotonic()
    persist_catalog_candidates(
        tuple(
            candidate
                for candidate in retrieval_sequence.external_candidates
            if candidate.repository_id in admitted_repository_ids
        ),
        database_url=database_url,
    )
    repository_persistence_duration_ms = build_duration_ms(persistence_started_at)
    evaluation_duration_ms = build_duration_ms(evaluation_started_at)
    expanded_execution = ExploreSearchExecution(
        ai_search_plan=execution.ai_search_plan,
        executed_queries=executed_queries,
        retrieved=retrieved,
        attempts=(*execution.attempts, *retrieval_sequence.attempts),
    )
    if execution_callback is not None:
        execution_callback(expanded_execution)

    response_build_started_at = monotonic()
    payload = build_explore_search_payload(
        topic_description=topic_description,
        ai_search_plan_payload=ai_search_plan_payload,
        evaluation=evaluation,
        can_expand=bool(expanded_execution.pending_queries),
    )
    response_build_duration_ms = build_duration_ms(response_build_started_at)
    if stage_report_callback is not None:
        stage_report_callback(
            _build_stage_report(
                evaluation=evaluation,
                executed_queries=retrieval_sequence.executed_queries,
                retrieved=retrieved,
                admitted_candidate_count=len(evaluation.admission.visible_candidates),
                visible_candidate_count=len(select_canonical_candidates(evaluation)),
                ai_planning_duration_ms=0,
                retrieval_duration_ms=retrieval_duration_ms,
                evaluation_duration_ms=evaluation_duration_ms,
                response_build_duration_ms=response_build_duration_ms,
                total_duration_ms=build_duration_ms(search_started_at),
                catalog_retrieval_duration_ms=(
                    retrieval_sequence.catalog_retrieval_duration_ms
                ),
                candidate_merge_duration_ms=(
                    retrieval_sequence.candidate_merge_duration_ms
                ),
                admission_duration_ms=evaluation.admission_duration_ms,
                ranking_duration_ms=evaluation.ranking_duration_ms,
                repository_persistence_duration_ms=repository_persistence_duration_ms,
            )
        )
    return payload


def _build_stage_report(
    *,
    evaluation,
    executed_queries: tuple[str, ...],
    retrieved: RetrievedCandidates,
    admitted_candidate_count: int,
    visible_candidate_count: int,
    ai_planning_duration_ms: int,
    retrieval_duration_ms: int,
    evaluation_duration_ms: int,
    response_build_duration_ms: int,
    total_duration_ms: int,
    catalog_retrieval_duration_ms: int = 0,
    candidate_merge_duration_ms: int = 0,
    admission_duration_ms: int = 0,
    ranking_duration_ms: int = 0,
    repository_persistence_duration_ms: int = 0,
) -> SearchStageReport:
    return SearchStageReport(
        executed_queries=executed_queries,
        retrieved_candidate_count=len(retrieved.candidates),
        admitted_candidate_count=admitted_candidate_count,
        visible_candidate_count=visible_candidate_count,
        timings={
            "ai_planning": ai_planning_duration_ms,
            "retrieval": retrieval_duration_ms,
            "catalog_retrieval": catalog_retrieval_duration_ms,
            "candidate_merge": candidate_merge_duration_ms,
            "evaluation": evaluation_duration_ms,
            "admission": admission_duration_ms,
            "ranking": ranking_duration_ms,
            "repository_persistence": repository_persistence_duration_ms,
            "response_serialization": response_build_duration_ms,
            "stage_wall_time": total_duration_ms,
        },
        provider_outcomes=tuple(
            SearchProviderOutcomeReport(
                source=outcome.source,
                channel=outcome.channel,
                query=outcome.query,
                attempt=outcome.attempt,
                status=outcome.status,
                candidate_count=outcome.candidate_count,
                duration_ms=outcome.duration_ms,
                retry_after_seconds=outcome.retry_after_seconds,
                error_code=outcome.error_code,
                error_message=outcome.error_message,
            )
            for outcome in retrieved.lane_outcomes
        ),
        ranking_candidates=_build_ranking_candidate_reports(
            evaluation,
        ),
    )


def _build_ranking_candidate_reports(
    evaluation,
) -> tuple[SearchRankingCandidateReport, ...]:
    admission_by_repository_id = {
        item.candidate.repository_id: item.admission
        for item in evaluation.admission.evaluated_candidates
    }
    return tuple(
        SearchRankingCandidateReport(
            repository_id=ranked.candidate.repository_id,
            repository_source=ranked.candidate.signal.source,
            rank_position=position,
            final_score=ranked.score,
            candidate_facts={
                "full_name": ranked.candidate.signal.title,
                "language": ranked.candidate.signal.payload.get("language"),
                "stars": ranked.candidate.signal.payload.get("stars"),
                "provider_updated_at": ranked.candidate.signal.payload.get(
                    "provider_updated_at"
                ),
            },
            retrieval_facts={
                "origins": list(ranked.candidate.provenance.origins),
                "matched_queries": list(ranked.candidate.provenance.matched_queries),
                "matched_channels": list(ranked.candidate.provenance.matched_channels),
                "best_rank_by_channel": dict(
                    ranked.candidate.provenance.best_rank_by_channel
                ),
                "hit_count": ranked.candidate.provenance.hit_count,
                "match_evidence": [
                    {
                        "query": evidence.query,
                        "location": evidence.location,
                        "path": evidence.path,
                        "alignment": evidence.alignment,
                        "channel": evidence.channel,
                        "origin": evidence.origin,
                        "retrieval_rank": evidence.retrieval_rank,
                    }
                    for evidence in ranked.candidate.provenance.match_evidence
                ],
            },
            admission_facts={
                "decision": admission_by_repository_id[
                    ranked.candidate.repository_id
                ].decision,
                "bucket": admission_by_repository_id[
                    ranked.candidate.repository_id
                ].bucket,
                "evidence": {
                    key: list(value) if isinstance(value, tuple) else value
                    for key, value in vars(
                        admission_by_repository_id[
                            ranked.candidate.repository_id
                        ].evidence
                    ).items()
                },
            },
            ranking_features=vars(ranked.features),
            score_breakdown=vars(ranked.score_breakdown),
        )
        for position, ranked in enumerate(evaluation.ranking.ranked_candidates, start=1)
    )


def _retrieve_planned_queries(
    *,
    queries: tuple[str, ...],
    topic_description: str,
    ai_search_plan_payload: dict[str, object],
    progress_callback: ExploreSearchProgressCallback | None,
    log_context: SearchLogContext | None,
    database_url: str,
) -> _RetrievalSequence:
    """Retrieve planned queries until one completes or every timeout fallback is exhausted."""

    accumulated: RetrievedCandidates | None = None
    executed_queries: list[str] = []
    attempts: list[ExploreQueryAttempt] = []
    external_candidates: list = []
    catalog_retrieval_duration_ms = 0
    candidate_merge_duration_ms = 0

    for query in queries:
        (
            step,
            step_attempts,
            step_external_candidates,
            exhausted_timeouts,
            step_catalog_retrieval_duration_ms,
            step_candidate_merge_duration_ms,
        ) = (
            _retrieve_query_with_timeout_retries(
                query=query,
                topic_description=topic_description,
                ai_search_plan_payload=ai_search_plan_payload,
                progress_callback=progress_callback if not attempts else None,
                log_context=log_context,
                database_url=database_url,
            )
        )
        executed_queries.append(query)
        attempts.extend(step_attempts)
        external_candidates.extend(step_external_candidates)
        catalog_retrieval_duration_ms += step_catalog_retrieval_duration_ms
        candidate_merge_duration_ms += step_candidate_merge_duration_ms
        accumulated = step if accumulated is None else _merge_retrieved_candidates(accumulated, step)
        if not exhausted_timeouts:
            break

    if accumulated is None:
        accumulated = RetrievedCandidates(
            candidates=(), source_statuses=(), successful_source_count=0
        )
    return _RetrievalSequence(
        retrieved=accumulated,
        executed_queries=tuple(executed_queries),
        attempts=tuple(attempts),
        external_candidates=tuple(external_candidates),
        catalog_retrieval_duration_ms=catalog_retrieval_duration_ms,
        candidate_merge_duration_ms=candidate_merge_duration_ms,
    )


def _retrieve_query_with_timeout_retries(
    *,
    query: str,
    topic_description: str,
    ai_search_plan_payload: dict[str, object],
    progress_callback: ExploreSearchProgressCallback | None,
    log_context: SearchLogContext | None,
    database_url: str,
) -> tuple[RetrievedCandidates, tuple[ExploreQueryAttempt, ...], tuple, bool, int, int]:
    """Retry one timed-out query before the plan moves to another angle."""

    attempts: list[ExploreQueryAttempt] = []
    external_candidates: list = []
    accumulated_retrieved: RetrievedCandidates | None = None
    catalog_retrieval_duration_ms = 0
    candidate_merge_duration_ms = 0
    for attempt_number in range(1, MAX_TIMEOUT_ATTEMPTS_PER_QUERY + 1):
        attempt_started_at = monotonic()
        catalog_retrieval_started_at = monotonic()
        local_candidates = retrieve_catalog_candidates((query,), database_url=database_url)
        catalog_retrieval_duration_ms += build_duration_ms(catalog_retrieval_started_at)
        external_retrieved = _run_external_retrieval(
            (query,),
            local_candidates=local_candidates,
            topic_description=topic_description,
            ai_search_plan_payload=ai_search_plan_payload,
            progress_callback=progress_callback if attempt_number == 1 else None,
            soft_deadline_monotonic=(
                attempt_started_at + config.EXPLORE_SEARCH_SOFT_TIMEOUT_SECONDS
            ),
            hard_deadline_monotonic=(
                attempt_started_at + config.EXPLORE_SEARCH_HARD_TIMEOUT_SECONDS
            ),
            log_context=log_context,
        )
        candidate_merge_started_at = monotonic()
        merged_candidates = merge_repository_candidates(
                (*local_candidates, *external_retrieved.candidates)
        )
        candidate_merge_duration_ms += build_duration_ms(candidate_merge_started_at)
        attempt_retrieved = RetrievedCandidates(
            candidates=merged_candidates,
            source_statuses=external_retrieved.source_statuses,
            successful_source_count=(
                external_retrieved.successful_source_count + (1 if local_candidates else 0)
            ),
            partial=external_retrieved.partial,
            warnings=external_retrieved.warnings,
            lane_outcomes=tuple(
                replace(outcome, query=query, attempt=attempt_number)
                for outcome in external_retrieved.lane_outcomes
            ),
        )
        timed_out = _query_attempt_timed_out(attempt_retrieved)
        accumulated_retrieved = (
            attempt_retrieved
            if accumulated_retrieved is None
            else _merge_retrieved_candidates(accumulated_retrieved, attempt_retrieved)
        )
        attempts.append(
            ExploreQueryAttempt(
                query=query,
                attempt=attempt_number,
                status="timed_out" if timed_out else "completed",
                duration_ms=build_duration_ms(attempt_started_at),
                candidate_count=len(attempt_retrieved.candidates),
            )
        )
        external_candidates.extend(external_retrieved.candidates)
        if not timed_out:
            assert accumulated_retrieved is not None
            return (
                accumulated_retrieved,
                tuple(attempts),
                tuple(external_candidates),
                False,
                catalog_retrieval_duration_ms,
                candidate_merge_duration_ms,
            )

    assert accumulated_retrieved is not None
    return (
        accumulated_retrieved,
        tuple(attempts),
        tuple(external_candidates),
        True,
        catalog_retrieval_duration_ms,
        candidate_merge_duration_ms,
    )


def _query_attempt_timed_out(retrieved: RetrievedCandidates) -> bool:
    """Treat partial provider timeouts as retryable query attempts."""

    if any(status.get("status") == "timed_out" for status in retrieved.source_statuses):
        return True
    return any(
        "timed_out" in warning or "timed out" in warning.casefold()
        for warning in retrieved.warnings
    )


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
            )
        )
    return run_external_repository_retrieval(queries, **retrieval_options)


def _build_explore_search_progress_payload(
    *,
    topic_description: str,
    ai_search_plan_payload: dict[str, object],
    retrieved,
    queries: tuple[str, ...],
) -> dict[str, object]:
    evaluation = build_explore_search_evaluation(
        retrieved,
        queries=queries,
    )
    return build_explore_search_payload(
        topic_description=topic_description,
        ai_search_plan_payload=ai_search_plan_payload,
        evaluation=evaluation,
    )


def _merge_retrieved_candidates(
    existing: RetrievedCandidates,
    incoming: RetrievedCandidates,
) -> RetrievedCandidates:
    """Preserve candidates and attempted-provider facts across search steps."""

    return RetrievedCandidates(
        candidates=merge_repository_candidates((*existing.candidates, *incoming.candidates)),
        source_statuses=(*existing.source_statuses, *incoming.source_statuses),
        successful_source_count=(
            existing.successful_source_count + incoming.successful_source_count
        ),
        partial=existing.partial or incoming.partial,
        warnings=tuple(dict.fromkeys((*existing.warnings, *incoming.warnings))),
        lane_outcomes=(*existing.lane_outcomes, *incoming.lane_outcomes),
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
