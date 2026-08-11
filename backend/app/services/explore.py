"""Explore search built from topic descriptions."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.models.signal import RawSignal
from app.models.topic import ResearchProfile, ResearchTopic
from app.services.profile_builder import build_profile
from app.services.matching import match_signal_to_profile
from app.services.normalization import normalize_raw_signal
from app.sources.repositories.common.query_builder import (
    build_repository_search_queries,
)
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


def run_explore_search(
    *,
    topic_description: str,
) -> dict[str, object]:
    """Run a read-only repository search from one topic description."""

    profile = _build_explore_profile(topic_description)
    queries = build_repository_search_queries(profile)
    if not queries:
        return {
            "topicDescription": topic_description,
            "queries": [],
            "items": [],
            "sourceStatuses": [],
        }

    candidates, source_statuses = _discover_candidates_across_sources(queries)
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
        "queries": list(queries),
        "items": items,
        "sourceStatuses": source_statuses,
    }


def _build_explore_profile(topic_description: str) -> ResearchProfile:
    return build_profile(
        ResearchTopic(
            slug="explore",
            label=topic_description or "Untitled topic",
            description=topic_description,
        )
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
        except Exception:
            logger.exception(
                "Repository source %s failed during explore search.",
                source_name,
            )
            source_statuses.append(
                {
                    "source": source_name,
                    "status": "error",
                    "candidateCount": 0,
                    "error": (
                        f"{SOURCE_DISPLAY_NAMES[source_name]} repository search is "
                        "unavailable right now."
                    ),
                }
            )
            continue

        successful_sources += 1
        candidates.extend(source_candidates)
        source_statuses.append(
            {
                "source": source_name,
                "status": "ok",
                "candidateCount": len(source_candidates),
                "error": None,
            }
        )

    if successful_sources == 0:
        raise ExploreSearchUnavailableError(source_statuses)

    return candidates, source_statuses
