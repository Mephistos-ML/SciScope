"""Explore search built from manual queries only."""

from __future__ import annotations

from app.models.topic import ResearchProfile
from app.services.normalization import normalize_raw_signal
from app.services.matching import match_signal_to_profile
from app.sources.repositories.github.discovery import discover_repository_candidates as discover_github_repository_candidates
from app.sources.repositories.gitlab.discovery import discover_repository_candidates as discover_gitlab_repository_candidates
from app.sources.repositories.common.query_builder import build_repository_search_queries


def run_explore_search(
    *,
    topic_description: str,
    manual_queries: list[str],
) -> dict[str, object]:
    """Run a read-only repository search from manual queries."""

    profile = _build_explore_profile(manual_queries)
    queries = build_repository_search_queries(profile)

    candidates = [
        *discover_github_repository_candidates(queries),
        *discover_gitlab_repository_candidates(queries),
    ]
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
        "manualQueries": manual_queries,
        "queries": list(queries),
        "items": items,
    }


def _build_explore_profile(manual_queries: list[str]) -> ResearchProfile:
    return ResearchProfile(
        topic_slug="explore",
        core_terms=tuple(manual_queries),
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
