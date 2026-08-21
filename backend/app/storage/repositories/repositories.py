"""Persistence helpers for repository records."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select

from app.database.records import RepositoryRecordModel
from app.database.session import session_scope
from app.models.repository import Repository


def upsert_repositories(
    repositories: Sequence[Repository],
    *,
    database_url: str,
) -> None:
    """Insert or update repositories."""

    if not repositories:
        return

    timestamp = _utc_now()
    with session_scope(database_url) as session:
        for repository in repositories:
            record = session.get(RepositoryRecordModel, repository.repository_id)
            if record is None:
                session.add(
                    RepositoryRecordModel(
                        repository_id=repository.repository_id,
                        source=repository.source,
                        full_name=repository.full_name,
                        url=repository.url,
                        metadata_json=dict(repository.metadata),
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                )
                continue

            record.source = repository.source
            record.full_name = repository.full_name
            record.url = repository.url
            record.metadata_json = dict(repository.metadata)
            record.updated_at = timestamp


def list_repositories(
    *,
    source: str | None = None,
    database_url: str,
) -> list[Repository]:
    """List repositories with an optional source filter."""

    statement = select(RepositoryRecordModel)
    if source is not None:
        statement = statement.where(RepositoryRecordModel.source == source)
    statement = statement.order_by(RepositoryRecordModel.full_name.asc())

    with session_scope(database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_repository(row) for row in rows]


def list_repositories_by_ids(
    repository_ids: Sequence[str],
    *,
    database_url: str,
) -> list[Repository]:
    """Load repositories by id while preserving the requested subset."""

    if not repository_ids:
        return []

    statement = (
        select(RepositoryRecordModel)
        .where(RepositoryRecordModel.repository_id.in_(tuple(repository_ids)))
        .order_by(RepositoryRecordModel.full_name.asc())
    )

    with session_scope(database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_repository(row) for row in rows]


def get_repository(
    repository_id: str,
    *,
    database_url: str,
) -> Repository | None:
    """Load one repository by id."""

    with session_scope(database_url) as session:
        row = session.get(RepositoryRecordModel, repository_id)
    if row is None:
        return None
    return _to_repository(row)


def _to_repository(record: RepositoryRecordModel) -> Repository:
    return Repository(
        repository_id=record.repository_id,
        source=record.source,
        full_name=record.full_name,
        url=record.url,
        metadata=dict(record.metadata_json or {}),
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)
