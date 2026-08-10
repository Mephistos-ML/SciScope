"""Explore search route."""

from __future__ import annotations

from app.services.explore import run_explore_search


def search_explore_response(payload: dict[str, object]) -> dict[str, object]:
    """Run an explore search from manual queries."""

    topic_description = str(payload.get("topicDescription") or "").strip()
    manual_queries = [
        str(term).strip()
        for term in payload.get("manualQueries", [])
        if str(term).strip()
    ]
    return run_explore_search(
        topic_description=topic_description,
        manual_queries=manual_queries,
    )
