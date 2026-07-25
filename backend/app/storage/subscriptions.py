"""Persistence for user subscriptions."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.storage.seen_signals import DB_PATH


@dataclass(frozen=True)
class SubscriptionRecord:
    """Persisted subscription for one user-defined search."""

    subscription_id: str
    user_id: str
    topic_description: str
    manual_keywords: tuple[str, ...]
    created_at: str


def init_subscription_storage(db_path: Path | None = None) -> None:
    """Initialise subscription tables."""

    db_path = db_path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                subscription_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                topic_description TEXT NOT NULL,
                manual_keywords_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def create_subscription(
    *,
    user_id: str,
    topic_description: str,
    manual_keywords: Sequence[str],
    db_path: Path | None = None,
) -> SubscriptionRecord:
    """Create one subscription for a saved search."""

    db_path = db_path or DB_PATH
    init_subscription_storage(db_path)
    record = SubscriptionRecord(
        subscription_id=f"sub_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        topic_description=topic_description,
        manual_keywords=tuple(manual_keywords),
        created_at=_utc_now_iso(),
    )

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO subscriptions (
                subscription_id,
                user_id,
                topic_description,
                manual_keywords_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record.subscription_id,
                record.user_id,
                record.topic_description,
                json.dumps(record.manual_keywords, ensure_ascii=False),
                record.created_at,
            ),
        )

    return record


def list_subscriptions_for_user(
    user_id: str,
    *,
    db_path: Path | None = None,
) -> list[SubscriptionRecord]:
    """List subscriptions for one user, newest first."""

    db_path = db_path or DB_PATH
    init_subscription_storage(db_path)

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT subscription_id, user_id, topic_description, manual_keywords_json, created_at
            FROM subscriptions
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()

    return [
        SubscriptionRecord(
            subscription_id=row[0],
            user_id=row[1],
            topic_description=row[2],
            manual_keywords=tuple(_loads_json_list(row[3])),
            created_at=row[4],
        )
        for row in rows
    ]


def get_subscription_for_user(
    user_id: str,
    subscription_id: str,
    *,
    db_path: Path | None = None,
) -> SubscriptionRecord | None:
    """Load one user-owned subscription."""

    db_path = db_path or DB_PATH
    init_subscription_storage(db_path)

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT subscription_id, user_id, topic_description, manual_keywords_json, created_at
            FROM subscriptions
            WHERE user_id = ? AND subscription_id = ?
            """,
            (user_id, subscription_id),
        ).fetchone()

    if row is None:
        return None

    return SubscriptionRecord(
        subscription_id=row[0],
        user_id=row[1],
        topic_description=row[2],
        manual_keywords=tuple(_loads_json_list(row[3])),
        created_at=row[4],
    )


def delete_subscription_for_user(
    user_id: str,
    subscription_id: str,
    *,
    db_path: Path | None = None,
) -> bool:
    """Delete one user-owned subscription."""

    db_path = db_path or DB_PATH
    init_subscription_storage(db_path)

    with sqlite3.connect(db_path) as connection:
        cursor = connection.execute(
            """
            DELETE FROM subscriptions
            WHERE user_id = ? AND subscription_id = ?
            """,
            (user_id, subscription_id),
        )

    return cursor.rowcount > 0


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _loads_json_list(value: str) -> list[str]:
    loaded = json.loads(value)
    if isinstance(loaded, list):
        return [str(item) for item in loaded]
    return []
