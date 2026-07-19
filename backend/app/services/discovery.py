"""Source-agnostic discovery orchestration."""

from __future__ import annotations

from pathlib import Path

from app.models.discovery import DiscoveryResult
from app.models.topic import ResearchProfile
from app.sources.github.discovery import discover_github_entities_for_profile
from app.storage.seen_signals import DB_PATH


def discover_entities_for_profile(
    profile: ResearchProfile,
    *,
    db_path: Path = DB_PATH,
) -> DiscoveryResult:
    """Discover source entities relevant to one research profile."""

    return discover_github_entities_for_profile(profile, db_path=db_path)
