"""Persistence contract for source-scoped seen signals."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import DATABASE_URL
from app.db.models import SeenSignalRecord
from app.db.session import session_scope
from app.models.signal import RawSignal


def load_seen_signal_ids(
    source: str,
    *,
    database_url: str | None = None,
) -> set[str]:
    """Load already seen item ids for one source."""

    resolved_database_url = database_url or DATABASE_URL
    with session_scope(resolved_database_url) as session:
        rows = session.scalars(
            select(SeenSignalRecord.item_id).where(SeenSignalRecord.source == source)
        ).all()
    return set(rows)


def upsert_raw_signals(
    signals: Sequence[RawSignal],
    *,
    database_url: str | None = None,
) -> None:
    """Insert or update raw signals in persistent storage."""

    if not signals:
        return

    resolved_database_url = database_url or DATABASE_URL
    seen_at = _utc_now()
    with session_scope(resolved_database_url) as session:
        for signal in signals:
            record = session.get(SeenSignalRecord, (signal.source, signal.item_id))
            if record is None:
                session.add(
                    SeenSignalRecord(
                        source=signal.source,
                        item_id=signal.item_id,
                        title=signal.title,
                        url=signal.url,
                        payload_json=dict(signal.payload),
                        first_seen_at=seen_at,
                        last_seen_at=seen_at,
                    )
                )
                continue

            record.title = signal.title
            record.url = signal.url
            record.payload_json = dict(signal.payload)
            record.last_seen_at = seen_at


def _utc_now() -> datetime:
    return datetime.now(UTC)
