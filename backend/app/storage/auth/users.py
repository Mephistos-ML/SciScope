"""Persistence helpers for user records."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import DATABASE_URL
from app.database.records import UserRecordModel
from app.database.session import session_scope


@dataclass(frozen=True)
class UserRecord:
    """Persisted first-party user identity."""

    user_id: str
    email: str
    display_name: str
    avatar_url: str | None
    created_at: str
    updated_at: str


def create_user(
    *,
    email: str,
    display_name: str,
    avatar_url: str | None = None,
    user_id: str | None = None,
    database_url: str | None = None,
) -> UserRecord:
    """Create one first-party user record."""

    resolved_database_url = database_url or DATABASE_URL
    now = _utc_now()
    record = UserRecordModel(
        user_id=user_id or f"user_{uuid.uuid4().hex[:12]}",
        email=email,
        display_name=display_name,
        avatar_url=avatar_url,
        created_at=now,
        updated_at=now,
    )

    with session_scope(resolved_database_url) as session:
        session.add(record)

    return _to_user_record(record)


def get_user_by_id(user_id: str, *, database_url: str | None = None) -> UserRecord | None:
    """Load one user by primary key."""

    resolved_database_url = database_url or DATABASE_URL
    statement = select(UserRecordModel).where(UserRecordModel.user_id == user_id)

    with session_scope(resolved_database_url) as session:
        row = session.scalar(statement)

    if row is None:
        return None
    return _to_user_record(row)


def get_user_by_email(email: str, *, database_url: str | None = None) -> UserRecord | None:
    """Load one user by email address."""

    resolved_database_url = database_url or DATABASE_URL
    statement = select(UserRecordModel).where(UserRecordModel.email == email)

    with session_scope(resolved_database_url) as session:
        row = session.scalar(statement)

    if row is None:
        return None
    return _to_user_record(row)


def update_user(
    user_id: str,
    *,
    email: str,
    display_name: str,
    avatar_url: str | None,
    database_url: str | None = None,
) -> UserRecord:
    """Refresh one persisted user profile."""

    resolved_database_url = database_url or DATABASE_URL

    with session_scope(resolved_database_url) as session:
        row = session.scalar(
            select(UserRecordModel).where(UserRecordModel.user_id == user_id)
        )
        if row is None:
            raise ValueError(f"User not found: {user_id}")

        row.email = email
        row.display_name = display_name
        row.avatar_url = avatar_url
        row.updated_at = _utc_now()
        session.flush()

    return _to_user_record(row)


def _to_user_record(record: UserRecordModel) -> UserRecord:
    return UserRecord(
        user_id=record.user_id,
        email=record.email,
        display_name=record.display_name,
        avatar_url=record.avatar_url,
        created_at=_ensure_utc(record.created_at).isoformat(timespec="seconds"),
        updated_at=_ensure_utc(record.updated_at).isoformat(timespec="seconds"),
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
