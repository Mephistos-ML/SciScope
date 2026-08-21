"""Persistence for direct user-to-repository subscriptions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.config import DATABASE_URL
from app.database.records import RepositoryRecordModel, SubscriptionRecordModel
from app.database.session import session_scope
from app.models.repository import Repository


@dataclass(frozen=True)
class SubscriptionRecord:
    """Persisted direct repository watch for one user."""

    subscription_id: str
    user_id: str
    repository_id: str
    selected_query: str | None
    created_at: str


@dataclass(frozen=True)
class SubscriptionWatchRecord:
    """Subscription joined with its watched repository projection."""

    subscription_id: str
    user_id: str
    repository: Repository
    selected_query: str | None
    created_at: str


def create_subscription(
    *,
    user_id: str,
    repository_id: str,
    selected_query: str | None,
    database_url: str | None = None,
) -> SubscriptionRecord:
    """Create or return one direct repository watch."""

    resolved_database_url = database_url or DATABASE_URL
    with session_scope(resolved_database_url) as session:
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
    database_url: str | None = None,
) -> list[SubscriptionRecord]:
    """List repository watches for one user, newest first."""

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
    """List repository watches across all users, newest first."""

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
    """Load one user-owned repository watch."""

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
    """Delete one user-owned repository watch."""

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
        repository_id=record.repository_id,
        selected_query=record.selected_query,
        created_at=_ensure_utc(record.created_at).isoformat(timespec="seconds"),
    )


def list_subscription_watches_for_user(
    user_id: str,
    *,
    database_url: str | None = None,
) -> list[SubscriptionWatchRecord]:
    """List one user's subscriptions joined with repository data."""

    resolved_database_url = database_url or DATABASE_URL
    statement = (
        select(SubscriptionRecordModel, RepositoryRecordModel)
        .join(
            RepositoryRecordModel,
            RepositoryRecordModel.repository_id == SubscriptionRecordModel.repository_id,
        )
        .where(SubscriptionRecordModel.user_id == user_id)
        .order_by(SubscriptionRecordModel.created_at.desc())
    )

    with session_scope(resolved_database_url) as session:
        rows = session.execute(statement).all()
    return [_to_subscription_watch_record(subscription, repository) for subscription, repository in rows]


def list_all_subscription_watches(
    *,
    database_url: str | None = None,
) -> list[SubscriptionWatchRecord]:
    """List all subscriptions joined with repository data."""

    resolved_database_url = database_url or DATABASE_URL
    statement = (
        select(SubscriptionRecordModel, RepositoryRecordModel)
        .join(
            RepositoryRecordModel,
            RepositoryRecordModel.repository_id == SubscriptionRecordModel.repository_id,
        )
        .order_by(SubscriptionRecordModel.created_at.desc())
    )

    with session_scope(resolved_database_url) as session:
        rows = session.execute(statement).all()
    return [_to_subscription_watch_record(subscription, repository) for subscription, repository in rows]


def _to_subscription_watch_record(
    subscription: SubscriptionRecordModel,
    repository: RepositoryRecordModel,
) -> SubscriptionWatchRecord:
    return SubscriptionWatchRecord(
        subscription_id=subscription.subscription_id,
        user_id=subscription.user_id,
        repository=Repository(
            repository_id=repository.repository_id,
            source=repository.source,
            full_name=repository.full_name,
            url=repository.url,
            metadata=dict(repository.metadata_json or {}),
        ),
        selected_query=subscription.selected_query,
        created_at=_ensure_utc(subscription.created_at).isoformat(timespec="seconds"),
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
