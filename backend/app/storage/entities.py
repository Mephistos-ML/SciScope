"""Persistence for watched entities and subscription-scoped entity memory."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.config import DATABASE_URL
from app.db.models import (
    EntityCheckpointRecord,
    EntityRecord,
    SubscriptionEntityMatchRecord,
)
from app.db.session import session_scope
from app.models.entity import Entity, EntityCheckpoint, SubscriptionEntityMatch


def upsert_entities(
    entities: Sequence[Entity],
    *,
    database_url: str | None = None,
) -> None:
    """Insert or update global entities."""

    if not entities:
        return

    resolved_database_url = database_url or DATABASE_URL
    timestamp = _utc_now()
    with session_scope(resolved_database_url) as session:
        for entity in entities:
            record = session.get(EntityRecord, entity.entity_id)
            if record is None:
                session.add(
                    EntityRecord(
                        entity_id=entity.entity_id,
                        source=entity.source,
                        entity_type=entity.entity_type,
                        canonical_name=entity.canonical_name,
                        url=entity.url,
                        metadata_json=dict(entity.metadata),
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                )
                continue

            record.source = entity.source
            record.entity_type = entity.entity_type
            record.canonical_name = entity.canonical_name
            record.url = entity.url
            record.metadata_json = dict(entity.metadata)
            record.updated_at = timestamp


def list_entities(
    *,
    source: str | None = None,
    entity_type: str | None = None,
    database_url: str | None = None,
) -> list[Entity]:
    """List global entities with optional source/type filters."""

    resolved_database_url = database_url or DATABASE_URL
    statement = select(EntityRecord)
    if source is not None:
        statement = statement.where(EntityRecord.source == source)
    if entity_type is not None:
        statement = statement.where(EntityRecord.entity_type == entity_type)
    statement = statement.order_by(EntityRecord.canonical_name.asc())

    with session_scope(resolved_database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_entity(row) for row in rows]


def list_entities_by_ids(
    entity_ids: Sequence[str],
    *,
    database_url: str | None = None,
) -> list[Entity]:
    """Load entities by id while preserving the requested subset."""

    if not entity_ids:
        return []

    resolved_database_url = database_url or DATABASE_URL
    statement = (
        select(EntityRecord)
        .where(EntityRecord.entity_id.in_(tuple(entity_ids)))
        .order_by(EntityRecord.canonical_name.asc())
    )

    with session_scope(resolved_database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_entity(row) for row in rows]


def upsert_subscription_entity_matches(
    matches: Sequence[SubscriptionEntityMatch],
    *,
    database_url: str | None = None,
) -> None:
    """Insert or update subscription-to-entity relevance matches."""

    if not matches:
        return

    resolved_database_url = database_url or DATABASE_URL
    timestamp = _utc_now()
    with session_scope(resolved_database_url) as session:
        for match in matches:
            record = session.get(
                SubscriptionEntityMatchRecord,
                (match.subscription_id, match.entity_id),
            )
            if record is None:
                session.add(
                    SubscriptionEntityMatchRecord(
                        subscription_id=match.subscription_id,
                        entity_id=match.entity_id,
                        source=match.source,
                        score=match.score,
                        active=match.active,
                        reason=match.reason,
                        matched_terms_json=list(match.matched_terms),
                        excluded_terms_json=list(match.excluded_terms),
                        metadata_json=dict(match.metadata),
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                )
                continue

            record.source = match.source
            record.score = match.score
            record.active = match.active
            record.reason = match.reason
            record.matched_terms_json = list(match.matched_terms)
            record.excluded_terms_json = list(match.excluded_terms)
            record.metadata_json = dict(match.metadata)
            record.updated_at = timestamp


def list_subscription_entity_matches(
    subscription_id: str,
    *,
    active_only: bool = True,
    database_url: str | None = None,
) -> list[SubscriptionEntityMatch]:
    """List entity matches for one subscription."""

    resolved_database_url = database_url or DATABASE_URL
    statement = select(SubscriptionEntityMatchRecord).where(
        SubscriptionEntityMatchRecord.subscription_id == subscription_id
    )
    if active_only:
        statement = statement.where(SubscriptionEntityMatchRecord.active.is_(True))
    statement = statement.order_by(
        SubscriptionEntityMatchRecord.score.desc(),
        SubscriptionEntityMatchRecord.entity_id.asc(),
    )

    with session_scope(resolved_database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_subscription_entity_match(row) for row in rows]


def delete_subscription_entity_matches(
    subscription_id: str,
    *,
    database_url: str | None = None,
) -> list[str]:
    """Delete all entity matches for one subscription and return affected entity ids."""

    resolved_database_url = database_url or DATABASE_URL
    with session_scope(resolved_database_url) as session:
        entity_ids = session.scalars(
            select(SubscriptionEntityMatchRecord.entity_id).where(
                SubscriptionEntityMatchRecord.subscription_id == subscription_id
            )
        ).all()
        session.execute(
            delete(SubscriptionEntityMatchRecord).where(
                SubscriptionEntityMatchRecord.subscription_id == subscription_id
            )
        )
    return [str(entity_id) for entity_id in entity_ids]


def upsert_entity_checkpoints(
    checkpoints: Sequence[EntityCheckpoint],
    *,
    database_url: str | None = None,
) -> None:
    """Insert or update monitoring checkpoints for entities."""

    if not checkpoints:
        return

    resolved_database_url = database_url or DATABASE_URL
    with session_scope(resolved_database_url) as session:
        for checkpoint in checkpoints:
            record = session.get(
                EntityCheckpointRecord,
                (
                    checkpoint.subscription_id,
                    checkpoint.entity_id,
                    checkpoint.checkpoint_key,
                ),
            )
            normalized_updated_at = _ensure_utc(checkpoint.updated_at)
            if record is None:
                session.add(
                    EntityCheckpointRecord(
                        subscription_id=checkpoint.subscription_id,
                        entity_id=checkpoint.entity_id,
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


def delete_entity_checkpoints_for_subscription(
    subscription_id: str,
    *,
    database_url: str | None = None,
) -> None:
    """Delete all checkpoints for one subscription."""

    resolved_database_url = database_url or DATABASE_URL
    with session_scope(resolved_database_url) as session:
        session.execute(
            delete(EntityCheckpointRecord).where(
                EntityCheckpointRecord.subscription_id == subscription_id
            )
        )


def list_entity_checkpoints(
    subscription_id: str,
    entity_id: str,
    *,
    database_url: str | None = None,
) -> list[EntityCheckpoint]:
    """List checkpoints for one subscription-owned entity."""

    resolved_database_url = database_url or DATABASE_URL
    statement = (
        select(EntityCheckpointRecord)
        .where(EntityCheckpointRecord.subscription_id == subscription_id)
        .where(EntityCheckpointRecord.entity_id == entity_id)
        .order_by(EntityCheckpointRecord.checkpoint_key.asc())
    )

    with session_scope(resolved_database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_entity_checkpoint(row) for row in rows]


def get_entity_checkpoint(
    subscription_id: str,
    entity_id: str,
    checkpoint_key: str,
    *,
    database_url: str | None = None,
) -> EntityCheckpoint | None:
    """Load one checkpoint for one subscription-owned entity."""

    resolved_database_url = database_url or DATABASE_URL
    with session_scope(resolved_database_url) as session:
        row = session.get(
            EntityCheckpointRecord,
            (subscription_id, entity_id, checkpoint_key),
        )
    if row is None:
        return None
    return _to_entity_checkpoint(row)


def _to_entity(record: EntityRecord) -> Entity:
    return Entity(
        entity_id=record.entity_id,
        source=record.source,
        entity_type=record.entity_type,
        canonical_name=record.canonical_name,
        url=record.url,
        metadata=dict(record.metadata_json or {}),
    )


def _to_subscription_entity_match(
    record: SubscriptionEntityMatchRecord,
) -> SubscriptionEntityMatch:
    return SubscriptionEntityMatch(
        subscription_id=record.subscription_id,
        entity_id=record.entity_id,
        source=record.source,
        score=float(record.score),
        active=bool(record.active),
        reason=record.reason,
        matched_terms=tuple(str(item) for item in (record.matched_terms_json or [])),
        excluded_terms=tuple(str(item) for item in (record.excluded_terms_json or [])),
        metadata=dict(record.metadata_json or {}),
    )


def _to_entity_checkpoint(record: EntityCheckpointRecord) -> EntityCheckpoint:
    return EntityCheckpoint(
        subscription_id=record.subscription_id,
        entity_id=record.entity_id,
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
