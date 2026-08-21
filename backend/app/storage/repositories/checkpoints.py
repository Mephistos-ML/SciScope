"""Persistence helpers for repository checkpoint records."""

from __future__ import annotations

from datetime import UTC, datetime
from collections.abc import Sequence

from sqlalchemy import delete, select

from app.database.records import RepositoryCheckpointRecordModel
from app.database.session import session_scope
from app.models.repository import RepositoryCheckpoint


def upsert_repository_checkpoints(
    checkpoints: Sequence[RepositoryCheckpoint],
    *,
    database_url: str,
) -> None:
    """Insert or update monitoring checkpoints for repositories."""

    if not checkpoints:
        return

    with session_scope(database_url) as session:
        for checkpoint in checkpoints:
            record = session.get(
                RepositoryCheckpointRecordModel,
                (
                    checkpoint.subscription_id,
                    checkpoint.repository_id,
                    checkpoint.checkpoint_key,
                ),
            )
            normalized_updated_at = _ensure_utc(checkpoint.updated_at)
            if record is None:
                session.add(
                    RepositoryCheckpointRecordModel(
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
    database_url: str,
) -> None:
    """Delete all repository checkpoints for one subscription."""

    with session_scope(database_url) as session:
        session.execute(
            delete(RepositoryCheckpointRecordModel).where(
                RepositoryCheckpointRecordModel.subscription_id == subscription_id
            )
        )


def list_repository_checkpoints(
    subscription_id: str,
    repository_id: str,
    *,
    database_url: str,
) -> list[RepositoryCheckpoint]:
    """List checkpoints for one subscription-owned repository."""

    statement = (
        select(RepositoryCheckpointRecordModel)
        .where(RepositoryCheckpointRecordModel.subscription_id == subscription_id)
        .where(RepositoryCheckpointRecordModel.repository_id == repository_id)
        .order_by(RepositoryCheckpointRecordModel.checkpoint_key.asc())
    )

    with session_scope(database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_repository_checkpoint(row) for row in rows]


def get_repository_checkpoint(
    subscription_id: str,
    repository_id: str,
    checkpoint_key: str,
    *,
    database_url: str,
) -> RepositoryCheckpoint | None:
    """Load one checkpoint for one subscription-owned repository."""

    with session_scope(database_url) as session:
        row = session.get(
            RepositoryCheckpointRecordModel,
            (subscription_id, repository_id, checkpoint_key),
        )
    if row is None:
        return None
    return _to_repository_checkpoint(row)


def _to_repository_checkpoint(
    record: RepositoryCheckpointRecordModel,
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
