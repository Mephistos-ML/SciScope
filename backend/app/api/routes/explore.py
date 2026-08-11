"""Explore search route."""

from __future__ import annotations

from app.services.explore import run_explore_search


def search_explore_response(payload: dict[str, object]) -> dict[str, object]:
    """Run an explore search from one topic description."""

    topic_description = str(payload.get("topicDescription") or "").strip()
    query_overrides = payload.get("queryOverrides") or []
    return run_explore_search(
        topic_description=topic_description,
        query_overrides=query_overrides if isinstance(query_overrides, list) else (),
    )
