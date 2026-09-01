"""Shared repository item serialization for Explore response modes."""

from __future__ import annotations

from app.services.search.ranking import RankedRepositoryCandidate


def build_repository_item(ranked_candidate: RankedRepositoryCandidate) -> dict[str, object]:
    """Serialize one ranked repository into the Explore API shape."""

    signal = ranked_candidate.candidate.signal
    return {
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


def _read_candidate_description(raw_text: str) -> str:
    parts = [part.strip() for part in raw_text.splitlines() if part.strip()]
    if len(parts) >= 2:
        return parts[1]
    return ""
