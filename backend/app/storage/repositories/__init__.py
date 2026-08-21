"""Persistence helpers for repositories and repository checkpoints."""

from app.config import DATABASE_URL
from app.models.repository import Repository, RepositoryCheckpoint
from app.storage.repositories import checkpoints as checkpoint_storage
from app.storage.repositories import repositories as repository_storage
from app.storage.repositories.checkpoints import (
    delete_repository_checkpoints_for_subscription,
    get_repository_checkpoint,
    list_repository_checkpoints,
    upsert_repository_checkpoints,
)


def upsert_repositories(
    repositories: tuple[Repository, ...] | list[Repository],
    *,
    database_url: str | None = None,
) -> None:
    repository_storage.upsert_repositories(
        repositories,
        database_url=database_url or DATABASE_URL,
    )


def list_repositories(
    *,
    source: str | None = None,
    database_url: str | None = None,
) -> list[Repository]:
    return repository_storage.list_repositories(
        source=source,
        database_url=database_url or DATABASE_URL,
    )


def list_repositories_by_ids(
    repository_ids,
    *,
    database_url: str | None = None,
) -> list[Repository]:
    return repository_storage.list_repositories_by_ids(
        repository_ids,
        database_url=database_url or DATABASE_URL,
    )


def get_repository(
    repository_id: str,
    *,
    database_url: str | None = None,
) -> Repository | None:
    return repository_storage.get_repository(
        repository_id,
        database_url=database_url or DATABASE_URL,
    )


def upsert_repository_checkpoints(
    checkpoints: tuple[RepositoryCheckpoint, ...] | list[RepositoryCheckpoint],
    *,
    database_url: str | None = None,
) -> None:
    checkpoint_storage.upsert_repository_checkpoints(
        checkpoints,
        database_url=database_url or DATABASE_URL,
    )


def delete_repository_checkpoints_for_subscription(
    subscription_id: str,
    *,
    database_url: str | None = None,
) -> None:
    checkpoint_storage.delete_repository_checkpoints_for_subscription(
        subscription_id,
        database_url=database_url or DATABASE_URL,
    )


def list_repository_checkpoints(
    subscription_id: str,
    repository_id: str,
    *,
    database_url: str | None = None,
) -> list[RepositoryCheckpoint]:
    return checkpoint_storage.list_repository_checkpoints(
        subscription_id,
        repository_id,
        database_url=database_url or DATABASE_URL,
    )


def get_repository_checkpoint(
    subscription_id: str,
    repository_id: str,
    checkpoint_key: str,
    *,
    database_url: str | None = None,
) -> RepositoryCheckpoint | None:
    return checkpoint_storage.get_repository_checkpoint(
        subscription_id,
        repository_id,
        checkpoint_key,
        database_url=database_url or DATABASE_URL,
    )

__all__ = [
    "DATABASE_URL",
    "delete_repository_checkpoints_for_subscription",
    "get_repository",
    "get_repository_checkpoint",
    "list_repositories",
    "list_repositories_by_ids",
    "list_repository_checkpoints",
    "upsert_repositories",
    "upsert_repository_checkpoints",
]
