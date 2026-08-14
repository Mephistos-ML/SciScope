"""Gitee watched-repository state placeholder helpers."""

from __future__ import annotations

from datetime import datetime

from app.models.repository import Repository


def sync_gitee_baseline(subscription_id: str, repository: Repository) -> None:
    """No-op until the Gitee source is implemented."""

    del subscription_id, repository


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
