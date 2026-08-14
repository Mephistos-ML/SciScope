"""GitHub-specific repository checkpoint helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.repository import Repository, RepositoryCheckpoint
from app.sources.common import (
    REPOSITORY_RELEASE_CHECKPOINT_KEY,
    read_repository_name,
)
from app.storage.repositories import (
    get_repository_checkpoint,
    upsert_repository_checkpoints,
)


def sync_github_baseline(subscription_id: str, repository: Repository) -> None:
    """Initialize the release checkpoint for one watched GitHub repository."""

    if repository.source != "github":
        return

    repo_name = read_repository_name(repository)
    if repo_name is None:
        return

    checkpoint = get_repository_checkpoint(
        subscription_id,
        repository.repository_id,
        REPOSITORY_RELEASE_CHECKPOINT_KEY,
    )
    if checkpoint is not None:
        return

    now = datetime.now(UTC)
    upsert_repository_checkpoints(
        (
            RepositoryCheckpoint(
                subscription_id=subscription_id,
                repository_id=repository.repository_id,
                source=repository.source,
                checkpoint_key=REPOSITORY_RELEASE_CHECKPOINT_KEY,
                checkpoint_value=now.isoformat(),
                updated_at=now,
            ),
        )
    )


def resolve_release_checkpoint(
    subscription_id: str,
    repository: Repository,
    *,
    baseline_started_after: datetime | None,
) -> datetime | None:
    """Resolve the monitoring cursor for one watched repository."""

    checkpoint = get_repository_checkpoint(
        subscription_id,
        repository.repository_id,
        REPOSITORY_RELEASE_CHECKPOINT_KEY,
    )
    if checkpoint is not None:
        return datetime.fromisoformat(checkpoint.checkpoint_value).astimezone(UTC)

    return baseline_started_after
