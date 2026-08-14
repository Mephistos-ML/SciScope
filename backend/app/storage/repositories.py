"""Persistence for watched repositories and subscription-scoped repository memory."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.config import DATABASE_URL
from app.database.models import (
    RepositoryCheckpointRecord,
    RepositoryRecord,
    SubscriptionRepositoryMatchRecord,
)
from app.database.session import session_scope
from app.models.repository import (
    Repository,
    RepositoryCheckpoint,
    SubscriptionRepositoryMatch,
)


def upsert_repositories(
    repositories: Sequence[Repository],
    *,
    database_url: str | None = None,
) -> None:
    """Insert or update repositories."""

    if not repositories:
        return

    resolved_database_url = database_url or DATABASE_URL
    timestamp = _utc_now()
    with session_scope(resolved_database_url) as session:
        for repository in repositories:
            record = session.get(RepositoryRecord, repository.repository_id)
            if record is None:
                session.add(
                    RepositoryRecord(
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
    database_url: str | None = None,
) -> list[Repository]:
    """List repositories with an optional source filter."""

    resolved_database_url = database_url or DATABASE_URL
    statement = select(RepositoryRecord)
    if source is not None:
        statement = statement.where(RepositoryRecord.source == source)
    statement = statement.order_by(RepositoryRecord.full_name.asc())

    with session_scope(resolved_database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_repository(row) for row in rows]


def list_repositories_by_ids(
    repository_ids: Sequence[str],
    *,
    database_url: str | None = None,
) -> list[Repository]:
    """Load repositories by id while preserving the requested subset."""

    if not repository_ids:
        return []

    resolved_database_url = database_url or DATABASE_URL
    statement = (
        select(RepositoryRecord)
        .where(RepositoryRecord.repository_id.in_(tuple(repository_ids)))
        .order_by(RepositoryRecord.full_name.asc())
    )

    with session_scope(resolved_database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_repository(row) for row in rows]


def upsert_subscription_repository_matches(
    matches: Sequence[SubscriptionRepositoryMatch],
    *,
    database_url: str | None = None,
) -> None:
    """Insert or update subscription-to-repository relevance matches."""

    if not matches:
        return

    resolved_database_url = database_url or DATABASE_URL
    timestamp = _utc_now()
    with session_scope(resolved_database_url) as session:
        for match in matches:
            record = session.get(
                SubscriptionRepositoryMatchRecord,
                (match.subscription_id, match.repository_id),
            )
            if record is None:
                session.add(
                    SubscriptionRepositoryMatchRecord(
                        subscription_id=match.subscription_id,
                        repository_id=match.repository_id,
                        source=match.source,
                        score=match.score,
                        reason=match.reason,
                        matched_terms_json=list(match.matched_terms),
                        metadata_json=dict(match.metadata),
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                )
                continue

            record.source = match.source
            record.score = match.score
            record.reason = match.reason
            record.matched_terms_json = list(match.matched_terms)
            record.metadata_json = dict(match.metadata)
            record.updated_at = timestamp


def list_subscription_repository_matches(
    subscription_id: str,
    *,
    database_url: str | None = None,
) -> list[SubscriptionRepositoryMatch]:
    """List repository matches for one subscription."""

    resolved_database_url = database_url or DATABASE_URL
    statement = select(SubscriptionRepositoryMatchRecord).where(
        SubscriptionRepositoryMatchRecord.subscription_id == subscription_id
    )
    statement = statement.order_by(
        SubscriptionRepositoryMatchRecord.score.desc(),
        SubscriptionRepositoryMatchRecord.repository_id.asc(),
    )

    with session_scope(resolved_database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_subscription_repository_match(row) for row in rows]


def delete_subscription_repository_matches(
    subscription_id: str,
    *,
    database_url: str | None = None,
) -> list[str]:
    """Delete all repository matches for one subscription and return ids."""

    resolved_database_url = database_url or DATABASE_URL
    with session_scope(resolved_database_url) as session:
        repository_ids = session.scalars(
            select(SubscriptionRepositoryMatchRecord.repository_id).where(
                SubscriptionRepositoryMatchRecord.subscription_id == subscription_id
            )
        ).all()
        session.execute(
            delete(SubscriptionRepositoryMatchRecord).where(
                SubscriptionRepositoryMatchRecord.subscription_id == subscription_id
            )
        )
    return [str(repository_id) for repository_id in repository_ids]


def upsert_repository_checkpoints(
    checkpoints: Sequence[RepositoryCheckpoint],
    *,
    database_url: str | None = None,
) -> None:
    """Insert or update monitoring checkpoints for repositories."""

    if not checkpoints:
        return

    resolved_database_url = database_url or DATABASE_URL
    with session_scope(resolved_database_url) as session:
        for checkpoint in checkpoints:
            record = session.get(
                RepositoryCheckpointRecord,
                (
                    checkpoint.subscription_id,
                    checkpoint.repository_id,
                    checkpoint.checkpoint_key,
                ),
            )
            normalized_updated_at = _ensure_utc(checkpoint.updated_at)
            if record is None:
                session.add(
                    RepositoryCheckpointRecord(
                        subscription_id=checkpoint.subscription_id,
                        repository_id=checkpoint.repository_id,
                        source=checkpoint.source,
                        checkpoint_key=checkpoint.checkpoint_key,
                        checkpoint_value=checkpoint.checkpoint_value,
                        updated_at=normalized_updated_at,
                    )
                )
                continue

            record.source = checkpoint.source
            record.checkpoint_value = checkpoint.checkpoint_value
            record.updated_at = normalized_updated_at


def delete_repository_checkpoints_for_subscription(
    subscription_id: str,
    *,
    database_url: str | None = None,
) -> None:
    """Delete all repository checkpoints for one subscription."""

    resolved_database_url = database_url or DATABASE_URL
    with session_scope(resolved_database_url) as session:
        session.execute(
            delete(RepositoryCheckpointRecord).where(
                RepositoryCheckpointRecord.subscription_id == subscription_id
            )
        )


def list_repository_checkpoints(
    subscription_id: str,
    repository_id: str,
    *,
    database_url: str | None = None,
) -> list[RepositoryCheckpoint]:
    """List checkpoints for one subscription-owned repository."""

    resolved_database_url = database_url or DATABASE_URL
    statement = (
        select(RepositoryCheckpointRecord)
        .where(RepositoryCheckpointRecord.subscription_id == subscription_id)
        .where(RepositoryCheckpointRecord.repository_id == repository_id)
        .order_by(RepositoryCheckpointRecord.checkpoint_key.asc())
    )

    with session_scope(resolved_database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_repository_checkpoint(row) for row in rows]


def get_repository_checkpoint(
    subscription_id: str,
    repository_id: str,
    checkpoint_key: str,
    *,
    database_url: str | None = None,
) -> RepositoryCheckpoint | None:
    """Load one checkpoint for one subscription-owned repository."""

    resolved_database_url = database_url or DATABASE_URL
    with session_scope(resolved_database_url) as session:
        row = session.get(
            RepositoryCheckpointRecord,
            (subscription_id, repository_id, checkpoint_key),
        )
    if row is None:
        return None
    return _to_repository_checkpoint(row)


def _to_repository(record: RepositoryRecord) -> Repository:
    return Repository(
        repository_id=record.repository_id,
        source=record.source,
        full_name=record.full_name,
        url=record.url,
        metadata=dict(record.metadata_json or {}),
    )


def _to_subscription_repository_match(
    record: SubscriptionRepositoryMatchRecord,
) -> SubscriptionRepositoryMatch:
    return SubscriptionRepositoryMatch(
        subscription_id=record.subscription_id,
        repository_id=record.repository_id,
        source=record.source,
        score=float(record.score),
        reason=record.reason,
        matched_terms=tuple(str(item) for item in (record.matched_terms_json or [])),
        metadata=dict(record.metadata_json or {}),
    )


def _to_repository_checkpoint(
    record: RepositoryCheckpointRecord,
) -> RepositoryCheckpoint:
    return RepositoryCheckpoint(
        subscription_id=record.subscription_id,
        repository_id=record.repository_id,
        source=record.source,
        checkpoint_key=record.checkpoint_key,
        checkpoint_value=record.checkpoint_value,
        updated_at=_ensure_utc(record.updated_at),
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
