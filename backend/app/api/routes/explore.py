"""Explore search route."""

from __future__ import annotations

from app.models.ai import SearchScope
from app.services.explore import run_explore_search


def search_explore_response(payload: dict[str, object]) -> dict[str, object]:
    """Run an explore search from one topic description."""

    topic_description = str(payload.get("topicDescription") or "").strip()
    search_scope = str(payload.get("searchScope") or "repositories")
    override_queries = payload.get("overrideQueries") or []
    return run_explore_search(
        topic_description=topic_description,
        search_scope=(
            search_scope if search_scope in ("repositories", "all") else "repositories"
        ),
        override_queries=override_queries if isinstance(override_queries, list) else (),
    )
