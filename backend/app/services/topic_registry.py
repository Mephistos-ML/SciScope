"""Accessors for runtime topics and profiles."""

from __future__ import annotations

from app.models.topic import ResearchProfile, ResearchTopic
from app.services.profile_builder import build_profile
from app.storage.subscriptions import list_all_subscriptions


def list_runtime_topics() -> tuple[ResearchTopic, ...]:
    """Return all topics that should participate in runtime processing."""

    subscriptions = _list_user_subscriptions()
    if subscriptions:
        return tuple(
            ResearchTopic(
                slug=subscription.subscription_id,
                label=subscription.topic_description.strip() or "Saved topic",
                description=subscription.topic_description,
            )
            for subscription in subscriptions
        )

    return ()


def list_runtime_profiles() -> tuple[ResearchProfile, ...]:
    """Return all profiles that should participate in runtime processing."""

    subscriptions = _list_user_subscriptions()
    if subscriptions:
        return tuple(
            build_profile(
                ResearchTopic(
                    slug=subscription.subscription_id,
                    label=subscription.topic_description.strip() or "Saved topic",
                    description=subscription.topic_description,
                ),
                profile_query_terms=subscription.query_terms,
            )
            for subscription in subscriptions
        )

    return ()


def _list_user_subscriptions():
    return tuple(list_all_subscriptions())
