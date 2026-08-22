"""Persistence helpers for explore search event records."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, func, select

from app.database.records import ExploreSearchEventRecordModel
from app.database.session import session_scope


@dataclass(frozen=True)
class ExploreSearchEvent:
    """Persisted explore usage event."""

    event_id: str
    created_at: str
    user_id: str | None
    subject_type: str
    subject_key: str
    ip_hash: str | None
    topic_hash: str
    outcome: str
    retry_after_seconds: int | None


def record_explore_search_event(
    *,
    user_id: str | None,
    subject_type: str,
    subject_key: str,
    ip_hash: str | None,
    topic_hash: str,
    outcome: str,
    retry_after_seconds: int | None = None,
    created_at: datetime | None = None,
    event_id: str | None = None,
    database_url: str,
) -> ExploreSearchEvent:
    """Persist one explore usage event."""

    event_created_at = _ensure_utc(created_at or _utc_now())
    record = ExploreSearchEventRecordModel(
        event_id=event_id or f"exp_{uuid.uuid4().hex[:20]}",
        created_at=event_created_at,
        user_id=user_id,
        subject_type=subject_type,
        subject_key=subject_key,
        ip_hash=ip_hash,
        topic_hash=topic_hash,
        outcome=outcome,
        retry_after_seconds=retry_after_seconds,
    )

    with session_scope(database_url) as session:
        session.add(record)

    return _to_explore_search_event(record)


def count_explore_events_since(
    *,
    subject_type: str,
    subject_key: str,
    since: datetime,
    outcomes: tuple[str, ...] | None = None,
    database_url: str,
) -> int:
    """Count one actor's explore events since the provided timestamp."""

    statement = _build_subject_count_statement(
        subject_type=subject_type,
        subject_key=subject_key,
        since=since,
        outcomes=outcomes,
    )

    with session_scope(database_url) as session:
        count = session.scalar(statement)
    return int(count or 0)


def get_last_explore_event_at(
    *,
    subject_type: str,
    subject_key: str,
    outcomes: tuple[str, ...] | None = None,
    database_url: str,
) -> datetime | None:
    """Return the latest explore event timestamp for one actor."""

    statement = (
        select(ExploreSearchEventRecordModel.created_at)
        .where(ExploreSearchEventRecordModel.subject_type == subject_type)
        .where(ExploreSearchEventRecordModel.subject_key == subject_key)
        .order_by(ExploreSearchEventRecordModel.created_at.desc())
        .limit(1)
    )
    if outcomes:
        statement = statement.where(ExploreSearchEventRecordModel.outcome.in_(outcomes))

    with session_scope(database_url) as session:
        value = session.scalar(statement)
    if value is None:
        return None
    return _ensure_utc(value)


def get_first_explore_event_at_since(
    *,
    subject_type: str,
    subject_key: str,
    since: datetime,
    outcomes: tuple[str, ...] | None = None,
    database_url: str,
) -> datetime | None:
    """Return the earliest explore event timestamp within one active window."""

    statement = (
        select(ExploreSearchEventRecordModel.created_at)
        .where(ExploreSearchEventRecordModel.subject_type == subject_type)
        .where(ExploreSearchEventRecordModel.subject_key == subject_key)
        .where(ExploreSearchEventRecordModel.created_at >= _ensure_utc(since))
        .order_by(ExploreSearchEventRecordModel.created_at.asc())
        .limit(1)
    )
    if outcomes:
        statement = statement.where(ExploreSearchEventRecordModel.outcome.in_(outcomes))

    with session_scope(database_url) as session:
        value = session.scalar(statement)
    if value is None:
        return None
    return _ensure_utc(value)


def count_global_explore_events_since(
    *,
    since: datetime,
    outcomes: tuple[str, ...] | None = None,
    database_url: str,
) -> int:
    """Count global explore events since the provided timestamp."""

    statement: Select[tuple[int]] = select(func.count()).select_from(
        ExploreSearchEventRecordModel
    ).where(ExploreSearchEventRecordModel.created_at >= _ensure_utc(since))
    if outcomes:
        statement = statement.where(ExploreSearchEventRecordModel.outcome.in_(outcomes))

    with session_scope(database_url) as session:
        count = session.scalar(statement)
    return int(count or 0)


def _build_subject_count_statement(
    *,
    subject_type: str,
    subject_key: str,
    since: datetime,
    outcomes: tuple[str, ...] | None,
) -> Select[tuple[int]]:
    statement: Select[tuple[int]] = select(func.count()).select_from(
        ExploreSearchEventRecordModel
    )
    statement = statement.where(ExploreSearchEventRecordModel.subject_type == subject_type)
    statement = statement.where(ExploreSearchEventRecordModel.subject_key == subject_key)
    statement = statement.where(
        ExploreSearchEventRecordModel.created_at >= _ensure_utc(since)
    )
    if outcomes:
        statement = statement.where(ExploreSearchEventRecordModel.outcome.in_(outcomes))
    return statement


def _to_explore_search_event(
    record: ExploreSearchEventRecordModel,
) -> ExploreSearchEvent:
    return ExploreSearchEvent(
        event_id=record.event_id,
        created_at=_ensure_utc(record.created_at).isoformat(timespec="seconds"),
        user_id=record.user_id,
        subject_type=record.subject_type,
        subject_key=record.subject_key,
        ip_hash=record.ip_hash,
        topic_hash=record.topic_hash,
        outcome=record.outcome,
        retry_after_seconds=record.retry_after_seconds,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
