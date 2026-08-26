"""Explore search built from topic descriptions."""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.services.ai import (
    OpenAIClientConfigurationError,
    OpenAIResponseError,
    build_ai_search_plan,
    serialize_ai_search_plan,
)
from app.services.search.admission import run_repository_admission
from app.services.search.matching import match_signal_to_terms
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
) -> dict[str, object]:
    """Run a read-only repository search from one topic description."""

    ai_search_plan = _plan_explore_search(topic_description=topic_description)
    ai_search_plan_payload = serialize_ai_search_plan(ai_search_plan)
    repository_queries = ai_search_plan.queries
    if not repository_queries:
        return {
            "topicDescription": topic_description,
            "aiSearchPlan": ai_search_plan_payload,
            "items": [],
            "sourceStatuses": [],
        }

    if progress_callback is None:
        retrieval_options: dict[str, object] = {}
        if soft_deadline_monotonic is not None:
            retrieval_options["soft_deadline_monotonic"] = soft_deadline_monotonic
        if hard_deadline_monotonic is not None:
            retrieval_options["hard_deadline_monotonic"] = hard_deadline_monotonic
        retrieved = run_external_repository_retrieval(
            repository_queries,
            **retrieval_options,
        )
    else:
        retrieval_options = {
            "progress_callback": lambda partial: progress_callback(
                _build_explore_search_payload(
                    topic_description=topic_description,
                    ai_search_plan_payload=ai_search_plan_payload,
                    retrieved=partial,
                )
            ),
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
        raise ExploreSearchUnavailableError(list(retrieved.source_statuses))

    return _build_explore_search_payload(
        topic_description=topic_description,
        ai_search_plan_payload=ai_search_plan_payload,
        retrieved=retrieved,
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


def _build_explore_search_payload(
    *,
    topic_description: str,
    ai_search_plan_payload: dict[str, object],
    retrieved,
) -> dict[str, object]:
    admission = run_repository_admission(retrieved.candidates)
    items: list[dict[str, object]] = []
    for evaluated_candidate in admission.visible_candidates:
        candidate = evaluated_candidate.candidate
        signal = candidate.signal
        match = match_signal_to_terms(
            signal,
            tuple(str(query) for query in ai_search_plan_payload.get("queries", [])),
        )

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
                "score": _build_candidate_score(candidate.provenance.hit_count, match.score),
                "reason": _build_candidate_reason(
                    match_reason=match.reason,
                    matched=match.matched,
                    matched_channels=candidate.provenance.matched_channels,
                    matched_queries=candidate.provenance.matched_queries,
                ),
                "matchedTerms": list(match.matched_terms),
            }
        )

    items.sort(
        key=lambda item: (
            -float(item["score"]),
            -int(item["stars"] or 0),
            str(item["fullName"]).casefold(),
        )
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


def _build_candidate_score(retrieval_hit_count: int, term_match_score: float) -> float:
    return max(float(retrieval_hit_count), term_match_score)


def _build_candidate_reason(
    *,
    match_reason: str,
    matched: bool,
    matched_channels: tuple[str, ...],
    matched_queries: tuple[str, ...],
) -> str:
    retrieval_reason = (
        "Retrieved via "
        f"{', '.join(matched_channels) or 'external search'}"
        f" for {', '.join(repr(query) for query in matched_queries[:3])}"
    )
    if len(matched_queries) > 3:
        retrieval_reason += f" and {len(matched_queries) - 3} more queries"
    retrieval_reason += "."

    if matched:
        return f"{match_reason} {retrieval_reason}"
    return retrieval_reason


def _build_partial_message(warnings: tuple[str, ...]) -> str | None:
    if not warnings:
        return "Search completed with partial coverage."

    visible_warnings = list(dict.fromkeys(warnings))
    summary = "; ".join(visible_warnings[:2])
    if len(visible_warnings) > 2:
        summary += f"; and {len(visible_warnings) - 2} more"
    return f"Search completed with partial coverage: {summary}"
