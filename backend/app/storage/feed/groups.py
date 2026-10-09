"""Immutable Feed publication persistence; member events own content and read state."""

from collections.abc import Sequence
from datetime import UTC
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.database.records.feed import (
    FeedEventRecordModel, FeedUpdateGroupMemberRecordModel, FeedUpdateGroupRecordModel,
)
from app.models.feed import FeedEvent, FeedUpdateGroup, FeedUpdateKind, read_feed_release_commit_details
from app.models.persistence import PersistenceConflictError
from app.storage.feed.events import write_feed_events
from app.storage.transaction import persistence_session


def publish_feed_update_groups(
    events: Sequence[FeedEvent], groups: Sequence[FeedUpdateGroup], *, database_url: str,
) -> None:
    """Commit events and their publications together, or leave neither changed."""
    with persistence_session(database_url) as session:
        write_feed_events(session, events)
        session.flush()
        write_feed_update_groups(session, groups)


def write_feed_update_groups(session: Session, groups: Sequence[FeedUpdateGroup]) -> None:
    """Publish inside a caller-owned transaction, including a fenced scan."""
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        insert = postgres_insert
    elif dialect == "sqlite":
        insert = sqlite_insert
    else:
        raise ValueError(f"Feed publication does not support database dialect: {dialect}")
    for group in groups:
        scope = {"user_id": group.user_id, "subscription_id": group.subscription_id,
                 "repository_id": group.repository_id}
        statement = insert(FeedUpdateGroupRecordModel).values(
            group_id=group.group_id, kind=group.kind,
            created_at=group.created_at.astimezone(UTC), **scope,
        ).on_conflict_do_nothing(index_elements=["group_id"]).returning(FeedUpdateGroupRecordModel.group_id)
        inserted = session.scalar(statement)
        if inserted is None:
            existing = session.get(FeedUpdateGroupRecordModel, group.group_id)
            member_ids = set(session.scalars(select(FeedUpdateGroupMemberRecordModel.event_id).where(
                FeedUpdateGroupMemberRecordModel.group_id == group.group_id,
            )))
            if (
                existing is None
                or any(getattr(existing, key) != value for key, value in scope.items())
                or existing.kind != group.kind
                or member_ids != set(group.event_ids)
            ):
                raise PersistenceConflictError("A published Feed group's scope and membership are immutable.")
        kinds = []
        release_id = None
        for start in range(0, len(group.event_ids), 500):
            rows = session.execute(select(FeedEventRecordModel.event_id, FeedEventRecordModel.kind).where(
                FeedEventRecordModel.event_id.in_(group.event_ids[start:start + 500]),
                FeedEventRecordModel.user_id == group.user_id,
                FeedEventRecordModel.subscription_id == group.subscription_id,
                FeedEventRecordModel.repository_id == group.repository_id,
            )).all()
            kinds.extend(row.kind for row in rows)
            release_id = next((row.event_id for row in rows if row.kind == "release"), release_id)
        if len(kinds) != len(group.event_ids):
            raise PersistenceConflictError("Group members must exist in the same subscription and repository scope.")
        if (group.kind == "commits" and any(kind != "commit" for kind in kinds)) or (
            group.kind == "release" and (kinds.count("release") != 1 or any(kind not in {"release", "commit"} for kind in kinds))
        ):
            raise PersistenceConflictError("Group members do not match its update kind.")
        if inserted is None:
            continue
        if release_id is not None:
            release = session.get(FeedEventRecordModel, release_id)
            references = read_feed_release_commit_details(release.metadata_json).event_ids
            if references:
                matched = set(session.scalars(select(FeedEventRecordModel.event_id).where(
                    FeedEventRecordModel.event_id.in_(references), FeedEventRecordModel.kind == "commit",
                    FeedEventRecordModel.user_id == group.user_id,
                    FeedEventRecordModel.subscription_id == group.subscription_id,
                    FeedEventRecordModel.repository_id == group.repository_id,
                )))
                if matched != set(references):
                    raise PersistenceConflictError("Release references must identify commit facts in the same scope.")
        session.add_all(FeedUpdateGroupMemberRecordModel(
            event_id=event_id, group_id=group.group_id, **scope,
        ) for event_id in group.event_ids)
        session.flush()


def get_feed_update_group_for_user(
    user_id: str, group_id: str, *, database_url: str,
) -> FeedUpdateGroup | None:
    """Read a publication only within the requesting user's scope."""
    with persistence_session(database_url) as session:
        row = session.scalar(select(FeedUpdateGroupRecordModel).where(
            FeedUpdateGroupRecordModel.group_id == group_id, FeedUpdateGroupRecordModel.user_id == user_id,
        ))
        if row is None:
            return None
        event_ids = tuple(session.scalars(select(FeedUpdateGroupMemberRecordModel.event_id).where(
            FeedUpdateGroupMemberRecordModel.group_id == row.group_id,
            FeedUpdateGroupMemberRecordModel.user_id == user_id,
        ).order_by(FeedUpdateGroupMemberRecordModel.event_id)))
        created_at = row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at.astimezone(UTC)
        return FeedUpdateGroup(row.group_id, row.user_id, row.subscription_id, row.repository_id,
                               cast(FeedUpdateKind, row.kind), event_ids, created_at)
