"""Explore search built from topic descriptions."""

from __future__ import annotations

import logging

from app.services.ai.openai_client import (
    OpenAIClientConfigurationError,
    OpenAIResponseError,
)
from app.services.ai.planner import build_ai_search_plan
from app.services.ai.search_plans import serialize_ai_search_plan
from app.services.search.matching import match_signal_to_terms
from app.services.search.retrieval import run_external_repository_retrieval
from app.services.search.retrieval.service import (
    discover_github_repository_candidates,
    discover_gitlab_repository_candidates,
)

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

    retrieved = run_external_repository_retrieval(
        repository_queries,
        discoverers=(
            ("github", discover_github_repository_candidates),
            ("gitlab", discover_gitlab_repository_candidates),
        ),
    )
    if retrieved.successful_source_count == 0:
        raise ExploreSearchUnavailableError(list(retrieved.source_statuses))

    items: list[dict[str, object]] = []
    for signal in retrieved.candidates:
        match = match_signal_to_terms(signal, repository_queries)
        if not match.matched:
            continue

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
                "score": match.score,
                "reason": match.reason,
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
