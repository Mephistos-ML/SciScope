"""Source-agnostic discovery orchestration."""

from __future__ import annotations

from app.config import DATABASE_URL
from app.models.discovery import DiscoveryResult
from app.models.topic import ResearchProfile
from app.sources.repositories.runtime import discover_repository_entities_for_profile


def discover_entities_for_profile(
    profile: ResearchProfile,
    *,
    database_url: str | None = None,
) -> DiscoveryResult:
    """Discover source entities relevant to one research profile."""

    return discover_repository_entities_for_profile(
        profile,
        database_url=database_url or DATABASE_URL,
    )
