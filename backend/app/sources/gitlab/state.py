"""GitLab-specific watched-project state and checkpoint helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.repository import Repository, RepositoryCheckpoint
from app.models.subscription import SubscriptionQueryProfile
from app.sources.common import (
    REPOSITORY_RELEASE_CHECKPOINT_KEY,
    read_repository_name,
)
from app.storage.repositories import (
    get_repository_checkpoint,
    list_repositories_by_ids,
    list_subscription_repository_matches,
    upsert_repository_checkpoints,
)


def sync_gitlab_baseline_for_profile(profile: SubscriptionQueryProfile) -> None:
    """Initialize checkpoints for watched GitLab projects that have none yet."""

    watched_repositories = load_watched_gitlab_repositories(profile.subscription_id)
    checkpoints_to_upsert: list[RepositoryCheckpoint] = []

    for repository in watched_repositories:
        repo_name = read_repository_name(repository)
        if repo_name is None:
            continue

        checkpoint = get_repository_checkpoint(
            profile.subscription_id,
            repository.repository_id,
            REPOSITORY_RELEASE_CHECKPOINT_KEY,
        )
        if checkpoint is not None:
            continue

        now = datetime.now(UTC)
        checkpoints_to_upsert.append(
            RepositoryCheckpoint(
                subscription_id=profile.subscription_id,
                repository_id=repository.repository_id,
                source=repository.source,
                checkpoint_key=REPOSITORY_RELEASE_CHECKPOINT_KEY,
                checkpoint_value=now.isoformat(),
                updated_at=now,
            )
        )

    upsert_repository_checkpoints(checkpoints_to_upsert)


def load_watched_gitlab_repositories(subscription_id: str) -> tuple[Repository, ...]:
    """Load watched GitLab repositories for one subscription."""

    matches = list_subscription_repository_matches(subscription_id)
    repository_ids = [
        match.repository_id for match in matches if match.source == "gitlab"
    ]
    repositories = list_repositories_by_ids(repository_ids)

    watched: list[Repository] = []
    for repository in repositories:
        if repository.source != "gitlab":
            continue
        if read_repository_name(repository) is not None:
            watched.append(repository)
    return tuple(watched)


def describe_watched_gitlab_repositories(subscription_id: str) -> list[dict[str, object]]:
    """Return watched GitLab repository metadata for debug visibility."""

    repositories = load_watched_gitlab_repositories(subscription_id)
    return [
        {
            "repositoryId": repository.repository_id,
            "source": repository.source,
            "repo": read_repository_name(repository),
            "url": repository.url,
            "stars": repository.metadata.get("stars"),
            "query": repository.metadata.get("query"),
            "language": repository.metadata.get("language"),
        }
        for repository in repositories
    ]


def describe_release_checkpoints(subscription_id: str) -> list[dict[str, object]]:
    """Return release checkpoint state for watched GitLab repositories."""

    repositories = load_watched_gitlab_repositories(subscription_id)
    checkpoints: list[dict[str, object]] = []
    for repository in repositories:
        checkpoint = get_repository_checkpoint(
            subscription_id,
            repository.repository_id,
            REPOSITORY_RELEASE_CHECKPOINT_KEY,
        )
        checkpoints.append(
            {
                "repositoryId": repository.repository_id,
                "source": repository.source,
                "repo": read_repository_name(repository),
                "checkpointKey": REPOSITORY_RELEASE_CHECKPOINT_KEY,
                "checkpointValue": (
                    checkpoint.checkpoint_value if checkpoint is not None else None
                ),
                "updatedAt": (
                    checkpoint.updated_at.isoformat(timespec="seconds")
                    if checkpoint is not None
                    else None
                ),
            }
        )

    return checkpoints


def resolve_release_checkpoint(
    subscription_id: str,
    repository: Repository,
    *,
    baseline_started_after: datetime | None,
) -> datetime | None:
    """Resolve the monitoring cursor for one watched GitLab repository."""

    checkpoint = get_repository_checkpoint(
        subscription_id,
        repository.repository_id,
        REPOSITORY_RELEASE_CHECKPOINT_KEY,
    )
    if checkpoint is not None:
        return datetime.fromisoformat(checkpoint.checkpoint_value).astimezone(UTC)

    return baseline_started_after
