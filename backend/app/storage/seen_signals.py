"""Persistence contract for source-scoped seen signals.

This module exists because SciScope will need the same durable idea already
used in SignalWatch: a stable `(source, item_id)` identity anchor.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from app.models.signal import RawSignal

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "sciscope.sqlite3"


def init_db(db_path: Path = DB_PATH) -> None:
    """Initialise the seen signal storage."""

    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_signals (
                source TEXT NOT NULL,
                item_id TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (source, item_id)
            )
            """
        )


def load_seen_signal_ids(source: str, db_path: Path = DB_PATH) -> set[str]:
    """Load already seen item ids for one source."""

    init_db(db_path)

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT item_id
            FROM seen_signals
            WHERE source = ?
            """,
            (source,),
        )
        return {row[0] for row in rows}


def upsert_raw_signals(
    signals: Sequence[RawSignal],
    db_path: Path = DB_PATH,
) -> None:
    """Insert or update raw signals in persistent storage."""

    init_db(db_path)

    seen_at = _utc_now_iso()
    rows = [
        (
            signal.source,
            signal.item_id,
            signal.title,
            signal.url,
            seen_at,
            seen_at,
            json.dumps(signal.payload, ensure_ascii=False, sort_keys=True),
        )
        for signal in signals
    ]

    with sqlite3.connect(db_path) as connection:
        connection.executemany(
            """
            INSERT INTO seen_signals (
                source,
                item_id,
                title,
                url,
                first_seen_at,
                last_seen_at,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, item_id) DO UPDATE SET
                title = excluded.title,
                url = excluded.url,
                last_seen_at = excluded.last_seen_at,
                payload_json = excluded.payload_json
            """,
            rows,
        )


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
