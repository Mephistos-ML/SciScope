"""GitCode watched-repository state placeholder helpers."""

from __future__ import annotations

from datetime import datetime

from app.models.entity import Entity
from app.models.topic import ResearchProfile


def sync_gitcode_baseline_for_profile(profile: ResearchProfile) -> None:
    """No-op until the GitCode source is implemented."""

    del profile


def load_watched_gitcode_repository_entities(subscription_id: str) -> tuple[Entity, ...]:
    """Return no watched entities until the GitCode source is implemented."""

    del subscription_id
    return ()


def describe_watched_gitcode_repositories(subscription_id: str) -> list[dict[str, object]]:
    """Return no watched repositories until the GitCode source is implemented."""

    del subscription_id
    return []


def describe_release_checkpoints(subscription_id: str) -> list[dict[str, object]]:
    """Return no checkpoints until the GitCode source is implemented."""

    del subscription_id
    return []


def resolve_release_checkpoint(
    subscription_id: str,
    entity: Entity,
    *,
    baseline_started_after: datetime | None,
) -> datetime | None:
    """Fall back to the baseline until the GitCode source is implemented."""

    del subscription_id, entity
    return baseline_started_after
