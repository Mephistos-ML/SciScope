"""Persistence helpers for seen signal records."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select

from app.database.records import SeenSignalRecordModel
from app.database.session import session_scope
from app.models.signal import Signal


def load_seen_signal_ids(
    source: str,
    *,
    database_url: str,
) -> set[str]:
    """Load already seen item ids for one source."""

    with session_scope(database_url) as session:
        rows = session.scalars(
            select(SeenSignalRecordModel.item_id).where(
                SeenSignalRecordModel.source == source
            )
        ).all()
    return set(rows)


def upsert_signals(
    signals: Sequence[Signal],
    *,
    database_url: str,
) -> None:
    """Insert or update signals in persistent storage."""

    if not signals:
        return

    seen_at = _utc_now()
    with session_scope(database_url) as session:
        for signal in signals:
            record = session.get(
                SeenSignalRecordModel,
                (signal.source, signal.item_id),
            )
            if record is None:
                session.add(
                    SeenSignalRecordModel(
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
