"""Persistence for user subscriptions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.config import DATABASE_URL
from app.database.models import SubscriptionRecordModel
from app.database.session import session_scope


@dataclass(frozen=True)
class SubscriptionRecord:
    """Persisted subscription for one user-defined search."""

    subscription_id: str
    user_id: str
    topic_description: str
    query_terms: tuple[str, ...]
    created_at: str


def create_subscription(
    *,
    user_id: str,
    topic_description: str,
    query_terms: tuple[str, ...],
    database_url: str | None = None,
) -> SubscriptionRecord:
    """Create one subscription for a saved search."""

    resolved_database_url = database_url or DATABASE_URL
    created_at = _utc_now()
    record = SubscriptionRecordModel(
        subscription_id=f"sub_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        topic_description=topic_description,
        query_terms_json=list(query_terms),
        created_at=created_at,
    )

    with session_scope(resolved_database_url) as session:
        session.add(record)

    return _to_subscription_record(record)


def list_subscriptions_for_user(
    user_id: str,
    *,
    database_url: str | None = None,
) -> list[SubscriptionRecord]:
    """List subscriptions for one user, newest first."""

    resolved_database_url = database_url or DATABASE_URL
    statement = (
        select(SubscriptionRecordModel)
        .where(SubscriptionRecordModel.user_id == user_id)
        .order_by(SubscriptionRecordModel.created_at.desc())
    )

    with session_scope(resolved_database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_subscription_record(row) for row in rows]


def list_all_subscriptions(*, database_url: str | None = None) -> list[SubscriptionRecord]:
    """List all subscriptions across all users, newest first."""

    resolved_database_url = database_url or DATABASE_URL
    statement = select(SubscriptionRecordModel).order_by(
        SubscriptionRecordModel.created_at.desc()
    )

    with session_scope(resolved_database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_subscription_record(row) for row in rows]


def get_subscription_for_user(
    user_id: str,
    subscription_id: str,
    *,
    database_url: str | None = None,
) -> SubscriptionRecord | None:
    """Load one user-owned subscription."""

    resolved_database_url = database_url or DATABASE_URL
    statement = (
        select(SubscriptionRecordModel)
        .where(SubscriptionRecordModel.user_id == user_id)
        .where(SubscriptionRecordModel.subscription_id == subscription_id)
    )

    with session_scope(resolved_database_url) as session:
        row = session.scalar(statement)
    if row is None:
        return None
    return _to_subscription_record(row)


def delete_subscription_for_user(
    user_id: str,
    subscription_id: str,
    *,
    database_url: str | None = None,
) -> bool:
    """Delete one user-owned subscription."""

    resolved_database_url = database_url or DATABASE_URL
    with session_scope(resolved_database_url) as session:
        result = session.execute(
            delete(SubscriptionRecordModel)
            .where(SubscriptionRecordModel.user_id == user_id)
            .where(SubscriptionRecordModel.subscription_id == subscription_id)
        )
    return result.rowcount > 0


def _to_subscription_record(record: SubscriptionRecordModel) -> SubscriptionRecord:
    return SubscriptionRecord(
        subscription_id=record.subscription_id,
        user_id=record.user_id,
        topic_description=record.topic_description,
        query_terms=tuple(str(item) for item in (record.query_terms_json or [])),
        created_at=_ensure_utc(record.created_at).isoformat(timespec="seconds"),
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
