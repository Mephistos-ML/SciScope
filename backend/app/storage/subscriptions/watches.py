"""Persistence helpers for subscription watch projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from app.database.records import RepositoryRecordModel, SubscriptionRecordModel
from app.database.session import session_scope
from app.models.repository import Repository


@dataclass(frozen=True)
class SubscriptionWatchRecord:
    """Subscription joined with its watched repository projection."""

    subscription_id: str
    user_id: str
    repository: Repository
    selected_query: str | None
    created_at: str


def list_subscription_watches_for_user(
    user_id: str,
    *,
    database_url: str,
) -> list[SubscriptionWatchRecord]:
    """List one user's subscriptions joined with repository data."""

    statement = (
        select(SubscriptionRecordModel, RepositoryRecordModel)
        .join(
            RepositoryRecordModel,
            RepositoryRecordModel.repository_id == SubscriptionRecordModel.repository_id,
        )
        .where(SubscriptionRecordModel.user_id == user_id)
        .order_by(SubscriptionRecordModel.created_at.desc())
    )

    with session_scope(database_url) as session:
        rows = session.execute(statement).all()
    return [
        _to_subscription_watch_record(subscription, repository)
        for subscription, repository in rows
    ]


def list_all_subscription_watches(
    *,
    database_url: str,
) -> list[SubscriptionWatchRecord]:
    """List all subscriptions joined with repository data."""

    statement = (
        select(SubscriptionRecordModel, RepositoryRecordModel)
        .join(
            RepositoryRecordModel,
            RepositoryRecordModel.repository_id == SubscriptionRecordModel.repository_id,
        )
        .order_by(SubscriptionRecordModel.created_at.desc())
    )

    with session_scope(database_url) as session:
        rows = session.execute(statement).all()
    return [
        _to_subscription_watch_record(subscription, repository)
        for subscription, repository in rows
    ]


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
            provider_repository_id=repository.provider_repository_id,
            owner_login=repository.owner_login,
            description=repository.description,
            language=repository.language,
            stars=repository.stars,
            topics=tuple(repository.topics_json or []),
            first_seen_at=_ensure_utc(repository.first_seen_at),
            last_seen_at=_ensure_utc(repository.last_seen_at),
            last_retrieved_at=_ensure_utc(repository.last_retrieved_at),
            provider_updated_at=(
                _ensure_utc(repository.provider_updated_at)
                if repository.provider_updated_at is not None
                else None
            ),
        ),
        selected_query=subscription.selected_query,
        created_at=_ensure_utc(subscription.created_at).isoformat(timespec="seconds"),
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
