"""Persistence helpers for users, OAuth identities, and authenticated sessions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, select, update

from app.config import DATABASE_URL
from app.database.models import (
    OAuthAccountRecordModel,
    UserRecordModel,
    UserSessionRecordModel,
)
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


@dataclass(frozen=True)
class UserSessionRecord:
    """Persisted authenticated user session."""

    session_id: str
    user_id: str
    session_token_hash: str
    expires_at: str
    created_at: str
    last_seen_at: str
    revoked_at: str | None


@dataclass(frozen=True)
class OAuthAccountRecord:
    """Linked external OAuth account."""

    oauth_account_id: str
    user_id: str
    provider: str
    provider_subject: str
    provider_email: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class AuthenticatedSessionRecord:
    """Resolved active session joined with its user."""

    user: UserRecord
    session: UserSessionRecord


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


def create_oauth_account(
    *,
    user_id: str,
    provider: str,
    provider_subject: str,
    provider_email: str | None,
    oauth_account_id: str | None = None,
    database_url: str | None = None,
) -> OAuthAccountRecord:
    """Create one linked OAuth identity."""

    resolved_database_url = database_url or DATABASE_URL
    now = _utc_now()
    record = OAuthAccountRecordModel(
        oauth_account_id=oauth_account_id or f"oauth_{uuid.uuid4().hex[:20]}",
        user_id=user_id,
        provider=provider,
        provider_subject=provider_subject,
        provider_email=provider_email,
        created_at=now,
        updated_at=now,
    )

    with session_scope(resolved_database_url) as session:
        session.add(record)

    return _to_oauth_account_record(record)


def get_oauth_account_by_provider_subject(
    provider: str,
    provider_subject: str,
    *,
    database_url: str | None = None,
) -> OAuthAccountRecord | None:
    """Load one OAuth account by provider subject."""

    resolved_database_url = database_url or DATABASE_URL
    statement = (
        select(OAuthAccountRecordModel)
        .where(OAuthAccountRecordModel.provider == provider)
        .where(OAuthAccountRecordModel.provider_subject == provider_subject)
    )

    with session_scope(resolved_database_url) as session:
        row = session.scalar(statement)

    if row is None:
        return None
    return _to_oauth_account_record(row)


def update_oauth_account(
    oauth_account_id: str,
    *,
    provider_email: str | None,
    database_url: str | None = None,
) -> OAuthAccountRecord:
    """Refresh one linked OAuth account."""

    resolved_database_url = database_url or DATABASE_URL

    with session_scope(resolved_database_url) as session:
        row = session.scalar(
            select(OAuthAccountRecordModel).where(
                OAuthAccountRecordModel.oauth_account_id == oauth_account_id
            )
        )
        if row is None:
            raise ValueError(f"OAuth account not found: {oauth_account_id}")

        row.provider_email = provider_email
        row.updated_at = _utc_now()
        session.flush()

    return _to_oauth_account_record(row)


def create_user_session(
    *,
    user_id: str,
    session_token_hash: str,
    expires_at: datetime,
    session_id: str | None = None,
    database_url: str | None = None,
) -> UserSessionRecord:
    """Persist one authenticated session."""

    resolved_database_url = database_url or DATABASE_URL
    now = _utc_now()
    record = UserSessionRecordModel(
        session_id=session_id or f"sess_{uuid.uuid4().hex[:20]}",
        user_id=user_id,
        session_token_hash=session_token_hash,
        expires_at=_ensure_utc(expires_at),
        created_at=now,
        last_seen_at=now,
        revoked_at=None,
    )

    with session_scope(resolved_database_url) as session:
        session.add(record)

    return _to_user_session_record(record)


def get_authenticated_session_by_token_hash(
    session_token_hash: str,
    *,
    now: datetime | None = None,
    database_url: str | None = None,
) -> AuthenticatedSessionRecord | None:
    """Resolve one non-expired, non-revoked session and its user."""

    resolved_database_url = database_url or DATABASE_URL
    effective_now = _ensure_utc(now or _utc_now())
    statement: Select[tuple[UserRecordModel, UserSessionRecordModel]] = (
        select(UserRecordModel, UserSessionRecordModel)
        .join(
            UserSessionRecordModel,
            UserSessionRecordModel.user_id == UserRecordModel.user_id,
        )
        .where(UserSessionRecordModel.session_token_hash == session_token_hash)
        .where(UserSessionRecordModel.revoked_at.is_(None))
        .where(UserSessionRecordModel.expires_at > effective_now)
    )

    with session_scope(resolved_database_url) as session:
        row = session.execute(statement).one_or_none()

    if row is None:
        return None

    user_record, session_record = row
    return AuthenticatedSessionRecord(
        user=_to_user_record(user_record),
        session=_to_user_session_record(session_record),
    )


def touch_user_session(
    session_id: str,
    *,
    seen_at: datetime | None = None,
    database_url: str | None = None,
) -> None:
    """Update session activity timestamp."""

    resolved_database_url = database_url or DATABASE_URL
    with session_scope(resolved_database_url) as session:
        session.execute(
            update(UserSessionRecordModel)
            .where(UserSessionRecordModel.session_id == session_id)
            .values(last_seen_at=_ensure_utc(seen_at or _utc_now()))
        )


def revoke_user_session_by_token_hash(
    session_token_hash: str,
    *,
    revoked_at: datetime | None = None,
    database_url: str | None = None,
) -> bool:
    """Revoke one active session by its cookie token hash."""

    resolved_database_url = database_url or DATABASE_URL
    with session_scope(resolved_database_url) as session:
        result = session.execute(
            update(UserSessionRecordModel)
            .where(UserSessionRecordModel.session_token_hash == session_token_hash)
            .where(UserSessionRecordModel.revoked_at.is_(None))
            .values(revoked_at=_ensure_utc(revoked_at or _utc_now()))
        )
    return result.rowcount > 0


def _to_user_record(record: UserRecordModel) -> UserRecord:
    return UserRecord(
        user_id=record.user_id,
        email=record.email,
        display_name=record.display_name,
        avatar_url=record.avatar_url,
        created_at=_ensure_utc(record.created_at).isoformat(timespec="seconds"),
        updated_at=_ensure_utc(record.updated_at).isoformat(timespec="seconds"),
    )


def _to_user_session_record(record: UserSessionRecordModel) -> UserSessionRecord:
    return UserSessionRecord(
        session_id=record.session_id,
        user_id=record.user_id,
        session_token_hash=record.session_token_hash,
        expires_at=_ensure_utc(record.expires_at).isoformat(timespec="seconds"),
        created_at=_ensure_utc(record.created_at).isoformat(timespec="seconds"),
        last_seen_at=_ensure_utc(record.last_seen_at).isoformat(timespec="seconds"),
        revoked_at=(
            _ensure_utc(record.revoked_at).isoformat(timespec="seconds")
            if record.revoked_at is not None
            else None
        ),
    )


def _to_oauth_account_record(record: OAuthAccountRecordModel) -> OAuthAccountRecord:
    return OAuthAccountRecord(
        oauth_account_id=record.oauth_account_id,
        user_id=record.user_id,
        provider=record.provider,
        provider_subject=record.provider_subject,
        provider_email=record.provider_email,
        created_at=_ensure_utc(record.created_at).isoformat(timespec="seconds"),
        updated_at=_ensure_utc(record.updated_at).isoformat(timespec="seconds"),
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
