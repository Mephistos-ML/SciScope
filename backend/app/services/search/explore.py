"""Explore search built from topic descriptions."""

from __future__ import annotations

import logging

from app.services.ai import (
    OpenAIClientConfigurationError,
    OpenAIResponseError,
    build_ai_search_plan,
    serialize_ai_search_plan,
)
from app.services.search.matching import match_signal_to_terms
from app.services.search.retrieval import run_external_repository_retrieval

logger = logging.getLogger(__name__)


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
) -> dict[str, object]:
    """Run a read-only repository search from one topic description."""

    try:
        ai_search_plan = build_ai_search_plan(topic_description=topic_description)
    except (OpenAIClientConfigurationError, OpenAIResponseError, RuntimeError) as exc:
        logger.exception(
            "AI search planning failed for topic=%r: %s",
            topic_description[:200],
            exc,
        )
        raise AiSearchPlanningError(
            "AI search planning is temporarily unavailable."
        ) from exc

    repository_queries = ai_search_plan.queries
    if not repository_queries:
        return {
            "topicDescription": topic_description,
            "aiSearchPlan": serialize_ai_search_plan(ai_search_plan),
            "items": [],
            "sourceStatuses": [],
        }

    retrieved = run_external_repository_retrieval(repository_queries)
    if retrieved.successful_source_count == 0:
        raise ExploreSearchUnavailableError(list(retrieved.source_statuses))

    items: list[dict[str, object]] = []
    for candidate in retrieved.candidates:
        signal = candidate.signal
        match = match_signal_to_terms(signal, repository_queries)

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
        "aiSearchPlan": serialize_ai_search_plan(ai_search_plan),
        "items": items,
        "sourceStatuses": list(retrieved.source_statuses),
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
