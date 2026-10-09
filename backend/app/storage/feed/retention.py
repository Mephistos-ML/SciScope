"""Retention hooks for future feed pruning policies."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, exists

from app.database.records.feed import FeedEventRecordModel, FeedUpdateGroupRecordModel, FeedUpdateGroupMemberRecordModel
from app.storage.transaction import persistence_session


def delete_feed_events_older_than(
    cutoff: datetime,
    *,
    database_url: str,
) -> int:
    """Delete feed events older than a given cutoff.

    This is intentionally unused for now; it exists as the future retention seam.
    """

    with persistence_session(database_url) as session:
        result = session.execute(
            delete(FeedEventRecordModel).where(
                FeedEventRecordModel.created_at < cutoff
            )
        )
        session.execute(delete(FeedUpdateGroupRecordModel).where(~exists().where(
            FeedUpdateGroupMemberRecordModel.group_id == FeedUpdateGroupRecordModel.group_id,
        )))
    return int(result.rowcount or 0)
