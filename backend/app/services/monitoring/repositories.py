"""Repository monitoring orchestration across source providers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Callable

from app.models.repository import Repository, RepositoryCheckpoint
from app.models.signal import Signal
from app.sources import github as github_source
from app.sources import gitlab as gitlab_source
from app.sources.common import (
    REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY,
    REPOSITORY_RELEASE_CHECKPOINT_KEY,
    RepositorySourceError,
    build_repository_main_commit_checkpoint,
    build_repository_release_checkpoint,
    read_repository_name,
)
from app.storage.repositories import (
    get_repository_checkpoint,
    upsert_repository_checkpoints,
)

logger = logging.getLogger(__name__)

RepositoryActivityLoader = Callable[..., list[Signal]]

MONITORED_CHECKPOINT_KEYS = (
    REPOSITORY_RELEASE_CHECKPOINT_KEY,
    REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY,
)


def sync_repository_baseline(
    subscription_id: str,
    repository: Repository,
    *,
    baseline_started_at: datetime | None = None,
    database_url: str,
) -> None:
    """Initialize monitoring checkpoints for one explicit repository watch."""

    if not _supports_repository_monitoring(repository):
        return

    repo_name = read_repository_name(repository)
    if repo_name is None:
        return

    now = _ensure_utc(baseline_started_at or datetime.now(UTC))
    missing_checkpoints: list[RepositoryCheckpoint] = []
    for checkpoint_key in MONITORED_CHECKPOINT_KEYS:
        checkpoint = get_repository_checkpoint(
            subscription_id,
            repository.repository_id,
            checkpoint_key,
            database_url=database_url,
        )
        if checkpoint is not None:
            continue
        missing_checkpoints.append(
            RepositoryCheckpoint(
                subscription_id=subscription_id,
                repository_id=repository.repository_id,
                source=repository.source,
                checkpoint_key=checkpoint_key,
                checkpoint_value=now.isoformat(),
                updated_at=now,
            )
        )

    upsert_repository_checkpoints(
        tuple(missing_checkpoints),
        database_url=database_url,
    )


def load_repository_signals(
    subscription_id: str,
    repository: Repository,
    *,
    baseline_started_after: datetime | None = None,
    database_url: str,
) -> list[Signal]:
    """Load live repository events and advance their checkpoints."""

    repo_name = read_repository_name(repository)
    if repo_name is None:
        return []

    release_started_after = _resolve_checkpoint(
        subscription_id,
        repository,
        checkpoint_key=REPOSITORY_RELEASE_CHECKPOINT_KEY,
        baseline_started_after=baseline_started_after,
        database_url=database_url,
    )
    commit_started_after = _resolve_checkpoint(
        subscription_id,
        repository,
        checkpoint_key=REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY,
        baseline_started_after=baseline_started_after,
        database_url=database_url,
    )
    if release_started_after is None and commit_started_after is None:
        return []

    source_loader = _resolve_activity_loader(repository)
    if source_loader is None:
        return []

    try:
        signals = source_loader(
            repo_name,
            release_started_after=release_started_after,
            commit_started_after=commit_started_after,
        )
    except RepositorySourceError as exc:
        logger.warning(
            "Repository monitoring source %s skipped: %s",
            repository.source,
            exc.public_message,
        )
        return []
    except Exception:
        logger.exception(
            "Repository monitoring source %s failed unexpectedly.",
            repository.source,
        )
        return []

    latest_release_published_at = max(
        (
            signal.published_at
            for signal in signals
            if signal.kind == "release" and signal.published_at is not None
        ),
        default=release_started_after,
    )
    latest_commit_published_at = max(
        (
            signal.published_at
            for signal in signals
            if signal.kind == "commit" and signal.published_at is not None
        ),
        default=commit_started_after,
    )

    checkpoints: list[RepositoryCheckpoint] = []
    if release_started_after is not None:
        checkpoint = build_repository_release_checkpoint(
            subscription_id,
            repository,
            latest_published_at=latest_release_published_at,
            fallback_started_after=release_started_after,
        )
        if checkpoint is not None:
            checkpoints.append(checkpoint)

    if commit_started_after is not None:
        checkpoint = build_repository_main_commit_checkpoint(
            subscription_id,
            repository,
            latest_published_at=latest_commit_published_at,
            fallback_started_after=commit_started_after,
        )
        if checkpoint is not None:
            checkpoints.append(checkpoint)

    upsert_repository_checkpoints(tuple(checkpoints), database_url=database_url)

    return signals


def _resolve_checkpoint(
    subscription_id: str,
    repository: Repository,
    *,
    checkpoint_key: str,
    baseline_started_after: datetime | None,
    database_url: str,
) -> datetime | None:
    checkpoint = get_repository_checkpoint(
        subscription_id,
        repository.repository_id,
        checkpoint_key,
        database_url=database_url,
    )
    if checkpoint is not None:
        return datetime.fromisoformat(checkpoint.checkpoint_value).astimezone(UTC)

    if baseline_started_after is None:
        return None
    return _ensure_utc(baseline_started_after)


def _resolve_activity_loader(
    repository: Repository,
) -> RepositoryActivityLoader | None:
    if repository.source == "github":
        return github_source.load_repo_activity
    if repository.source == "gitlab":
        return gitlab_source.load_repo_activity
    return None


def _supports_repository_monitoring(repository: Repository) -> bool:
    return repository.source in {"github", "gitlab"}


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
