"""Persistence helpers for subscription records."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.database.records import SubscriptionRecordModel
from app.database.session import session_scope


@dataclass(frozen=True)
class SubscriptionRecord:
    """Persisted direct repository watch for one user."""

    subscription_id: str
    user_id: str
    repository_id: str
    selected_query: str | None
    created_at: str


def create_subscription(
    *,
    user_id: str,
    repository_id: str,
    selected_query: str | None,
    database_url: str,
) -> SubscriptionRecord:
    """Create or return one direct repository watch."""

    with session_scope(database_url) as session:
        existing = session.scalar(
            select(SubscriptionRecordModel)
            .where(SubscriptionRecordModel.user_id == user_id)
            .where(SubscriptionRecordModel.repository_id == repository_id)
        )
        if existing is not None:
            return _to_subscription_record(existing)

        record = SubscriptionRecordModel(
            subscription_id=f"sub_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            repository_id=repository_id,
            selected_query=selected_query.strip() if selected_query else None,
            created_at=_utc_now(),
        )
        session.add(record)

    return _to_subscription_record(record)


def list_subscriptions_for_user(
    user_id: str,
    *,
    database_url: str,
) -> list[SubscriptionRecord]:
    """List repository watches for one user, newest first."""

    statement = (
        select(SubscriptionRecordModel)
        .where(SubscriptionRecordModel.user_id == user_id)
        .order_by(SubscriptionRecordModel.created_at.desc())
    )

    with session_scope(database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_subscription_record(row) for row in rows]


def list_all_subscriptions(*, database_url: str) -> list[SubscriptionRecord]:
    """List repository watches across all users, newest first."""

    statement = select(SubscriptionRecordModel).order_by(
        SubscriptionRecordModel.created_at.desc()
    )

    with session_scope(database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_subscription_record(row) for row in rows]


def get_subscription_for_user(
    user_id: str,
    subscription_id: str,
    *,
    database_url: str,
) -> SubscriptionRecord | None:
    """Load one user-owned repository watch."""

    statement = (
        select(SubscriptionRecordModel)
        .where(SubscriptionRecordModel.user_id == user_id)
        .where(SubscriptionRecordModel.subscription_id == subscription_id)
    )

    with session_scope(database_url) as session:
        row = session.scalar(statement)
    if row is None:
        return None
    return _to_subscription_record(row)


def delete_subscription_for_user(
    user_id: str,
    subscription_id: str,
    *,
    database_url: str,
) -> bool:
    """Delete one user-owned repository watch."""

    with session_scope(database_url) as session:
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
        repository_id=record.repository_id,
        selected_query=record.selected_query,
        created_at=_ensure_utc(record.created_at).isoformat(timespec="seconds"),
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
