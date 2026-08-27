"""Retention hooks for future feed pruning policies."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete

from app.database.records import FeedEventRecordModel
from app.database.session import session_scope


def delete_feed_events_older_than(
    cutoff: datetime,
    *,
    database_url: str,
) -> int:
    """Delete feed events older than a given cutoff.

    This is intentionally unused for now; it exists as the future retention seam.
    """

    with session_scope(database_url) as session:
        result = session.execute(
            delete(FeedEventRecordModel).where(
                FeedEventRecordModel.created_at < cutoff
            )
        )
    return int(result.rowcount or 0)
