"""Persistence helpers for durable feed events."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.database.records import FeedEventRecordModel
from app.database.session import session_scope
from app.models.feed import FeedEvent


def upsert_feed_events(
    events: Sequence[FeedEvent],
    *,
    database_url: str,
) -> None:
    """Insert or update user feed events idempotently."""

    if not events:
        return

    with session_scope(database_url) as session:
        for event in events:
            record = session.get(FeedEventRecordModel, event.event_id)
            normalized_published_at = (
                _ensure_utc(event.published_at) if event.published_at is not None else None
            )
            normalized_created_at = _ensure_utc(event.created_at or datetime.now(UTC))
            if record is None:
                session.add(
                    FeedEventRecordModel(
                        event_id=event.event_id,
                        user_id=event.user_id,
                        subscription_id=event.subscription_id,
                        repository_id=event.repository_id,
                        repository_full_name=event.repository_full_name,
                        repository_source=event.repository_source,
                        repository_url=event.repository_url,
                        selected_query=event.selected_query,
                        source=event.source,
                        kind=event.kind,
                        item_id=event.item_id,
                        title=event.title,
                        url=event.url,
                        published_at=normalized_published_at,
                        raw_text=event.raw_text,
                        normalized_text=event.normalized_text,
                        metadata_json=dict(event.metadata),
                        created_at=normalized_created_at,
                    )
                )
                continue

            record.user_id = event.user_id
            record.subscription_id = event.subscription_id
            record.repository_id = event.repository_id
            record.repository_full_name = event.repository_full_name
            record.repository_source = event.repository_source
            record.repository_url = event.repository_url
            record.selected_query = event.selected_query
            record.source = event.source
            record.kind = event.kind
            record.item_id = event.item_id
            record.title = event.title
            record.url = event.url
            record.published_at = normalized_published_at
            record.raw_text = event.raw_text
            record.normalized_text = event.normalized_text
            record.metadata_json = dict(event.metadata)


def list_feed_events_for_user(
    user_id: str,
    *,
    database_url: str,
) -> list[FeedEvent]:
    """List one user's feed events ordered for presentation."""

    statement = (
        select(FeedEventRecordModel)
        .where(FeedEventRecordModel.user_id == user_id)
        .order_by(
            FeedEventRecordModel.published_at.desc().nullslast(),
            FeedEventRecordModel.created_at.desc(),
            FeedEventRecordModel.event_id.desc(),
        )
    )

    with session_scope(database_url) as session:
        rows = session.scalars(statement).all()
    return [_to_feed_event(row) for row in rows]


def get_feed_event_for_user(
    user_id: str,
    event_id: str,
    *,
    database_url: str,
) -> FeedEvent | None:
    """Load one feed event if it belongs to the given user."""

    statement = (
        select(FeedEventRecordModel)
        .where(FeedEventRecordModel.user_id == user_id)
        .where(FeedEventRecordModel.event_id == event_id)
    )
    with session_scope(database_url) as session:
        row = session.scalars(statement).first()
    if row is None:
        return None
    return _to_feed_event(row)


def count_feed_events(*, database_url: str) -> int:
    """Return the total durable feed event count."""

    statement = select(func.count()).select_from(FeedEventRecordModel)
    with session_scope(database_url) as session:
        count = session.scalar(statement)
    return int(count or 0)


def _to_feed_event(record: FeedEventRecordModel) -> FeedEvent:
    return FeedEvent(
        event_id=record.event_id,
        user_id=record.user_id,
        subscription_id=record.subscription_id,
        repository_id=record.repository_id,
        repository_full_name=record.repository_full_name,
        repository_source=record.repository_source,
        repository_url=record.repository_url,
        selected_query=record.selected_query,
        source=record.source,
        kind=record.kind,
        item_id=record.item_id,
        title=record.title,
        url=record.url,
        published_at=(
            _ensure_utc(record.published_at) if record.published_at is not None else None
        ),
        raw_text=record.raw_text,
        normalized_text=record.normalized_text,
        metadata=dict(record.metadata_json or {}),
        created_at=_ensure_utc(record.created_at),
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
