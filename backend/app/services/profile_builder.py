"""Research topic to research profile mapping lives here."""

from __future__ import annotations

from collections.abc import Sequence

from app.models.topic import ResearchProfile, ResearchTopic
from app.services.search_queries import normalize_profile_query_terms


def build_profile(
    topic: ResearchTopic,
    *,
    profile_query_terms: Sequence[str] = (),
) -> ResearchProfile:
    """Build one research profile from structured query terms.

    The topic description stays raw source-of-truth text. Until the real AI
    layer lands, optional profile query terms simulate the structured output
    that the agent will eventually produce.
    """

    normalized_terms = normalize_profile_query_terms(profile_query_terms)

    return ResearchProfile(
        topic_slug=topic.slug,
        core_terms=normalized_terms,
        seed_queries=normalized_terms,
        metadata={
            "profileSource": (
                "profile-query-terms"
                if normalized_terms
                else "topic-description-pending-ai"
            ),
            "topicDescription": topic.description,
        },
    )
