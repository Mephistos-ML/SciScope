"""Accessors for active topics and profiles in the current runtime."""

from __future__ import annotations

from app.models.topic import ResearchProfile, ResearchTopic
from app.services.profile_builder import get_seed_profile, get_seed_topic


DEFAULT_TOPIC_SLUG = "pnmr"


def get_active_topic() -> ResearchTopic:
    """Return the current active topic for the local runtime."""

    return get_seed_topic(DEFAULT_TOPIC_SLUG)


def get_active_profile() -> ResearchProfile:
    """Return the current active profile for the local runtime."""

    return get_seed_profile(DEFAULT_TOPIC_SLUG)
