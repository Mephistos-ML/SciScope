"""Explore search built from topic descriptions."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.models.signal import RawSignal
from app.models.topic import ResearchProfile, ResearchTopic
from app.services.ai_planner import build_ai_search_plan
from app.services.ai_search_plans import serialize_ai_search_plan
from app.services.matching import match_signal_to_profile
from app.services.normalization import normalize_raw_signal
from app.services.profile_builder import build_profile
from app.services.openai_client import (
    OpenAIClientConfigurationError,
    OpenAIResponseError,
)
from app.sources.repositories.common import RepositorySourceError, build_source_status
from app.sources.repositories.github.discovery import (
    discover_repository_candidates as discover_github_repository_candidates,
)
from app.sources.repositories.gitlab.discovery import (
    discover_repository_candidates as discover_gitlab_repository_candidates,
)

logger = logging.getLogger(__name__)

SOURCE_DISPLAY_NAMES = {
    "github": "GitHub",
    "gitlab": "GitLab",
}


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

    profile = _build_explore_profile(
        topic_description,
        profile_query_terms=repository_queries,
    )
    candidates, source_statuses = _discover_candidates_across_sources(repository_queries)
    deduped = _dedupe_by_item_id(candidates)

    items: list[dict[str, object]] = []
    for raw_signal in deduped.values():
        normalized_signal = normalize_raw_signal(raw_signal)
        match = match_signal_to_profile(normalized_signal, profile)
        if not match.matched:
            continue

        items.append(
            {
                "itemId": raw_signal.item_id,
                "source": raw_signal.source,
                "fullName": raw_signal.title,
                "url": raw_signal.url,
                "description": _read_candidate_description(raw_signal.raw_text),
                "language": raw_signal.payload.get("language"),
                "stars": raw_signal.payload.get("stars"),
                "query": raw_signal.payload.get("query"),
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
        "sourceStatuses": source_statuses,
    }


def _build_explore_profile(
    topic_description: str,
    *,
    profile_query_terms: tuple[str, ...] = (),
) -> ResearchProfile:
    return build_profile(
        ResearchTopic(
            slug="explore",
            label=topic_description or "Untitled topic",
            description=topic_description,
        ),
        profile_query_terms=profile_query_terms,
    )


def _dedupe_by_item_id(candidates: list) -> dict[str, object]:
    deduped: dict[str, object] = {}
    for signal in candidates:
        existing = deduped.get(signal.item_id)
        if existing is None:
            deduped[signal.item_id] = signal
            continue

        existing_query = str(existing.payload.get("query") or "")
        incoming_query = str(signal.payload.get("query") or "")
        if len(incoming_query) > len(existing_query):
            deduped[signal.item_id] = signal

    return deduped


def _read_candidate_description(raw_text: str) -> str:
    parts = [part.strip() for part in raw_text.splitlines() if part.strip()]
    if len(parts) >= 2:
        return parts[1]
    return ""


def _discover_candidates_across_sources(
    queries: Sequence[str],
) -> tuple[list[RawSignal], list[dict[str, object]]]:
    candidates: list[RawSignal] = []
    source_statuses: list[dict[str, object]] = []
    successful_sources = 0

    for source_name, discover_candidates in (
        ("github", discover_github_repository_candidates),
        ("gitlab", discover_gitlab_repository_candidates),
    ):
        try:
            source_candidates = list(discover_candidates(queries))
        except RepositorySourceError as exc:
            logger.warning(
                "Repository source %s is unavailable for explore search: %s",
                source_name,
                exc.public_message,
            )
            source_statuses.append(
                build_source_status(
                    source=source_name,
                    status=exc.status,
                    candidate_count=0,
                    error=exc.public_message,
                )
            )
            continue
        except Exception:
            logger.exception(
                "Repository source %s failed during explore search.",
                source_name,
            )
            source_statuses.append(
                build_source_status(
                    source=source_name,
                    status="error",
                    candidate_count=0,
                    error=(
                        f"{SOURCE_DISPLAY_NAMES[source_name]} repository search is "
                        "unavailable right now."
                    ),
                )
            )
            continue

        successful_sources += 1
        candidates.extend(source_candidates)
        source_statuses.append(
            build_source_status(
                source=source_name,
                status="ok",
                candidate_count=len(source_candidates),
                error=None,
            )
        )

    if successful_sources == 0:
        raise ExploreSearchUnavailableError(source_statuses)

    return candidates, source_statuses
