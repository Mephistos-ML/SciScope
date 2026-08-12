"""Research topic to research profile mapping lives here."""

from __future__ import annotations

from collections.abc import Sequence

from app.models.topic import ResearchProfile, ResearchTopic
from app.services.ai_search_plans import normalize_override_queries


def build_profile(
    topic: ResearchTopic,
    *,
    override_queries: Sequence[str] = (),
) -> ResearchProfile:
    """Build one research profile from temporary override queries.

    The topic description stays raw source-of-truth text. Until the real AI
    layer lands, optional override queries simulate the structured output
    that the agent will eventually produce.
    """

    normalized_terms = normalize_override_queries(override_queries)

    return ResearchProfile(
        topic_slug=topic.slug,
        core_terms=normalized_terms,
        seed_queries=normalized_terms,
        metadata={
            "profileSource": (
                "override-queries"
                if normalized_terms
                else "topic-description-pending-ai"
            ),
            "topicDescription": topic.description,
        },
    )
