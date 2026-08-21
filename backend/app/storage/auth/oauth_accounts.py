"""Persistence helpers for OAuth account records."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import DATABASE_URL
from app.database.records import OAuthAccountRecordModel
from app.database.session import session_scope


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
