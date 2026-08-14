"""Gitee watched-repository state placeholder helpers."""

from __future__ import annotations

from datetime import datetime

from app.models.repository import Repository
from app.models.subscription import SubscriptionQueryProfile


def sync_gitee_baseline_for_profile(profile: SubscriptionQueryProfile) -> None:
    """No-op until the Gitee source is implemented."""

    del profile


def load_watched_gitee_repositories(subscription_id: str) -> tuple[Repository, ...]:
    """Return no watched repositories until the Gitee source is implemented."""

    del subscription_id
    return ()


def describe_watched_gitee_repositories(subscription_id: str) -> list[dict[str, object]]:
    """Return no watched repositories until the Gitee source is implemented."""

    del subscription_id
    return []


def describe_release_checkpoints(subscription_id: str) -> list[dict[str, object]]:
    """Return no checkpoints until the Gitee source is implemented."""

    del subscription_id
    return []


def resolve_release_checkpoint(
    subscription_id: str,
    repository: Repository,
    *,
    baseline_started_after: datetime | None,
) -> datetime | None:
    """Fall back to the baseline until the Gitee source is implemented."""

    del subscription_id, repository
    return baseline_started_after
