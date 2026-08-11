"""Explore search route."""

from __future__ import annotations

from app.services.explore import run_explore_search


def search_explore_response(payload: dict[str, object]) -> dict[str, object]:
    """Run an explore search from one topic description."""

    topic_description = str(payload.get("topicDescription") or "").strip()
    profile_query_terms = payload.get("profileQueryTerms") or []
    return run_explore_search(
        topic_description=topic_description,
        profile_query_terms=(
            profile_query_terms if isinstance(profile_query_terms, list) else ()
        ),
    )
