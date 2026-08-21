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
    REPOSITORY_RELEASE_CHECKPOINT_KEY,
    RepositorySourceError,
    build_repository_release_checkpoint,
    read_repository_name,
)
from app.storage.repositories import (
    get_repository_checkpoint,
    upsert_repository_checkpoints,
)

logger = logging.getLogger(__name__)

RepositoryActivityLoader = Callable[[str], list[Signal]]


def sync_repository_baseline(
    subscription_id: str,
    repository: Repository,
    *,
    baseline_started_at: datetime | None = None,
    database_url: str,
) -> None:
    """Initialize the monitoring checkpoint for one explicit repository watch."""

    if not _supports_release_monitoring(repository):
        return

    repo_name = read_repository_name(repository)
    if repo_name is None:
        return

    checkpoint = get_repository_checkpoint(
        subscription_id,
        repository.repository_id,
        REPOSITORY_RELEASE_CHECKPOINT_KEY,
        database_url=database_url,
    )
    if checkpoint is not None:
        return

    now = _ensure_utc(baseline_started_at or datetime.now(UTC))
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
        ),
        database_url=database_url,
    )


def load_repository_signals(
    subscription_id: str,
    repository: Repository,
    *,
    baseline_started_after: datetime | None = None,
    database_url: str,
) -> list[Signal]:
    """Load live repository release signals and advance its checkpoint."""

    repo_name = read_repository_name(repository)
    if repo_name is None:
        return []

    started_after = _resolve_release_checkpoint(
        subscription_id,
        repository,
        baseline_started_after=baseline_started_after,
        database_url=database_url,
    )
    if started_after is None:
        return []

    source_loader = _resolve_activity_loader(repository)
    if source_loader is None:
        return []

    try:
        signals = source_loader(
            repo_name,
            started_after=started_after,
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

    latest_published_at = max(
        (
            signal.published_at
            for signal in signals
            if signal.published_at is not None
        ),
        default=started_after,
    )
    checkpoint = build_repository_release_checkpoint(
        subscription_id,
        repository,
        latest_published_at=latest_published_at,
        fallback_started_after=started_after,
    )
    if checkpoint is not None:
        upsert_repository_checkpoints((checkpoint,), database_url=database_url)

    return signals


def _resolve_release_checkpoint(
    subscription_id: str,
    repository: Repository,
    *,
    baseline_started_after: datetime | None,
    database_url: str,
) -> datetime | None:
    checkpoint = get_repository_checkpoint(
        subscription_id,
        repository.repository_id,
        REPOSITORY_RELEASE_CHECKPOINT_KEY,
        database_url=database_url,
    )
    if checkpoint is not None:
        return datetime.fromisoformat(checkpoint.checkpoint_value).astimezone(UTC)

    if baseline_started_after is None:
        return None
    return _ensure_utc(baseline_started_after)


def _resolve_activity_loader(
    repository: Repository,
) -> Callable[[str, datetime | None], list[Signal]] | None:
    if repository.source == "github":
        return github_source.load_repo_activity
    if repository.source == "gitlab":
        return gitlab_source.load_repo_activity
    return None


def _supports_release_monitoring(repository: Repository) -> bool:
    return repository.source in {"github", "gitlab"}


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
