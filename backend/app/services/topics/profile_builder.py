"""Research topic to research profile mapping lives here."""

from __future__ import annotations

from collections.abc import Sequence

from app.models.topic import ResearchProfile, ResearchTopic
from app.services.ai.search_plans import normalize_search_queries


def build_profile(
    topic: ResearchTopic,
    *,
    profile_query_terms: Sequence[str] = (),
) -> ResearchProfile:
    """Build one research profile from AI-generated query terms."""

    normalized_terms = normalize_search_queries(profile_query_terms)

    return ResearchProfile(
        topic_slug=topic.slug,
        core_terms=normalized_terms,
        seed_queries=normalized_terms,
        metadata={
            "profileSource": (
                "ai-generated-search-plan"
                if normalized_terms
                else "topic-description-pending-ai"
            ),
            "topicDescription": topic.description,
        },
    )
