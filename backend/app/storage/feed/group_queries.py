"""User-scoped, bounded publication reads and explicit member read updates."""

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import and_, case, func, or_, select, update

from app.database.records.feed import (
    FeedEventRecordModel as Event, FeedUpdateGroupMemberRecordModel as Member,
    FeedUpdateGroupRecordModel as Group,
)
from app.models.feed import FeedCursor, FeedGroupCursor, FeedGroupSummary, FeedUpdateKind, FeedEvent
from app.storage.feed.events import to_feed_event
from app.storage.transaction import persistence_session


def _summaries(user_id: str):
    # Aggregate before pagination. Member count never controls card page size.
    return select(
        Group.group_id, Group.subscription_id, Group.repository_id, Group.kind, Group.created_at,
        case((Group.kind == "release", func.max(case((Event.kind == "release", Event.published_at)))),
             else_=func.max(Event.published_at)).label("published_at"),
        func.count(Event.event_id).label("event_count"),
        func.sum(case((Event.kind == "commit", 1), else_=0)).label("commit_count"),
        func.sum(case((Event.read_at.is_(None), 1), else_=0)).label("unread_event_count"),
    ).join(Member, Member.group_id == Group.group_id).join(Event, Event.event_id == Member.event_id).where(
        Group.user_id == user_id, Member.user_id == user_id, Event.user_id == user_id,
    ).group_by(Group.group_id, Group.subscription_id, Group.repository_id, Group.kind, Group.created_at).subquery()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _after(published_column, created_column, id_column, *,
           published_at: datetime | None, created_at: datetime, identity: str):
    tail = or_(created_column < created_at,
               and_(created_column == created_at, id_column < identity))
    if published_at is None:
        return and_(published_column.is_(None), tail)
    return or_(published_column.is_(None), published_column < published_at,
               and_(published_column == published_at, tail))


def list_feed_group_summaries_for_user(
    user_id: str, *, database_url: str, limit: int,
    cursor: FeedGroupCursor | None = None, unread_only: bool = False,
    subscription_id: str | None = None, group_id: str | None = None,
) -> list[FeedGroupSummary]:
    """Fetch bounded summaries without loading all member content into memory."""
    if not 1 <= limit <= 51:
        raise ValueError("Group query limit must be between 1 and 51.")
    stats = _summaries(user_id)
    statement = select(stats).order_by(stats.c.published_at.desc().nullslast(),
                                      stats.c.created_at.desc(), stats.c.group_id.desc()).limit(limit)
    if cursor is not None:
        statement = statement.where(_after(
            stats.c.published_at, stats.c.created_at, stats.c.group_id,
            published_at=cursor.published_at, created_at=cursor.created_at, identity=cursor.group_id,
        ))
    if unread_only:
        statement = statement.where(stats.c.unread_event_count > 0)
    if subscription_id is not None:
        statement = statement.where(stats.c.subscription_id == subscription_id)
    if group_id is not None:
        statement = statement.where(stats.c.group_id == group_id)
    page = statement.cte("feed_group_page")
    # Rank only selected groups and fetch content for one event per card, all in
    # one statement so concurrent deletion cannot separate summaries from content.
    ranked = select(Member.group_id, Event.event_id, func.row_number().over(
        partition_by=Member.group_id,
        order_by=(case((Event.kind == "release", 0), else_=1),
                  Event.published_at.desc().nullslast(), Event.created_at.desc(), Event.event_id.desc()),
    ).label("position")).join(Event, Event.event_id == Member.event_id).join(
        page, page.c.group_id == Member.group_id,
    ).where(Member.user_id == user_id, Event.user_id == user_id).subquery()
    statement = select(page, Event).join(ranked, ranked.c.group_id == page.c.group_id).join(
        Event, Event.event_id == ranked.c.event_id,
    ).where(ranked.c.position == 1).order_by(page.c.published_at.desc().nullslast(),
                                            page.c.created_at.desc(), page.c.group_id.desc())
    with persistence_session(database_url) as session:
        return [FeedGroupSummary(
            row.group_id, row.subscription_id, row.repository_id, cast(FeedUpdateKind, row.kind),
            _utc(row.created_at), _utc(row.published_at) if row.published_at else None,
            row.event_count, row.commit_count, row.unread_event_count, to_feed_event(row[-1]),
        ) for row in session.execute(statement)]


def count_unread_feed_groups_for_user(user_id: str, *, database_url: str) -> int:
    """Count unread cards, including partially read publications, rather than events."""
    stats = _summaries(user_id)
    with persistence_session(database_url) as session:
        return int(session.scalar(select(func.count()).select_from(stats).where(stats.c.unread_event_count > 0)) or 0)


def list_feed_group_commits_for_user(
    user_id: str, group_id: str, *, database_url: str, limit: int, cursor: FeedCursor | None = None,
) -> list[FeedEvent]:
    """Read a bounded commit page; never include a release in the dropdown."""
    if not 1 <= limit <= 51:
        raise ValueError("Commit query limit must be between 1 and 51.")
    statement = select(Event).join(Member, Member.event_id == Event.event_id).join(
        Group, Group.group_id == Member.group_id,
    ).where(Group.group_id == group_id, Group.user_id == user_id,
            Member.user_id == user_id, Event.user_id == user_id, Event.kind == "commit").order_by(
        Event.published_at.desc().nullslast(), Event.created_at.desc(), Event.event_id.desc(),
    ).limit(limit)
    if cursor is not None:
        statement = statement.where(_after(
            Event.published_at, Event.created_at, Event.event_id,
            published_at=cursor.published_at, created_at=cursor.created_at, identity=cursor.event_id,
        ))
    with persistence_session(database_url) as session:
        return [to_feed_event(row) for row in session.scalars(statement)]


def mark_feed_group_read_for_user(user_id: str, group_id: str, *, database_url: str) -> bool:
    """Mark all members atomically; opening details never invokes this operation."""
    with persistence_session(database_url) as session:
        owned = session.scalar(select(Group.group_id).where(Group.group_id == group_id, Group.user_id == user_id))
        if owned is None:
            return False
        members = select(Member.event_id).where(Member.group_id == group_id, Member.user_id == user_id)
        session.execute(update(Event).where(Event.user_id == user_id, Event.event_id.in_(members),
                                            Event.read_at.is_(None)).values(read_at=datetime.now(UTC)))
    return True
