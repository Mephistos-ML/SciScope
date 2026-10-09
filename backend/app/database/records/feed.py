"""SQLAlchemy feed-event persistence record models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base


class FeedEventRecordModel(Base):
    """Append-only feed event stored per user subscription."""

    __tablename__ = "user_feed_events"
    __table_args__ = (
        Index("ux_user_feed_events_group_scope", "event_id", "user_id", "subscription_id", "repository_id", unique=True),
        Index("ix_user_feed_events_user_created_at", "user_id", "created_at"),
        Index("ix_user_feed_events_user_published_at", "user_id", "published_at"),
        Index("ix_user_feed_events_subscription_created_at", "subscription_id", "created_at"),
        Index("ix_user_feed_events_repository_created_at", "repository_id", "created_at"),
    )

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    subscription_id: Mapped[str] = mapped_column(String, nullable=False)
    repository_id: Mapped[str] = mapped_column(String, nullable=False)
    repository_full_name: Mapped[str] = mapped_column(String, nullable=False)
    repository_source: Mapped[str] = mapped_column(String, nullable=False)
    repository_url: Mapped[str] = mapped_column(Text, nullable=False)
    selected_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    item_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FeedUpdateGroupRecordModel(Base):
    """Publication identity; content and read state remain in its member events."""

    __tablename__ = "user_feed_update_groups"
    __table_args__ = (
        CheckConstraint("kind IN ('release', 'commits')", name="ck_feed_update_group_kind"),
        Index("ux_feed_update_groups_scope", "group_id", "user_id", "subscription_id", "repository_id", unique=True),
        Index("ix_feed_update_groups_user_created", "user_id", "created_at", "group_id"),
        Index("ix_feed_update_groups_subscription_created", "subscription_id", "created_at", "group_id"),
    )

    group_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    subscription_id: Mapped[str] = mapped_column(String, nullable=False)
    repository_id: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FeedUpdateGroupMemberRecordModel(Base):
    """Each event belongs to at most one group, within exactly the same scope."""

    __tablename__ = "user_feed_update_group_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ["group_id", "user_id", "subscription_id", "repository_id"],
            ["user_feed_update_groups.group_id", "user_feed_update_groups.user_id",
             "user_feed_update_groups.subscription_id", "user_feed_update_groups.repository_id"],
            ondelete="CASCADE", name="fk_feed_group_member_group_scope",
        ),
        ForeignKeyConstraint(
            ["event_id", "user_id", "subscription_id", "repository_id"],
            ["user_feed_events.event_id", "user_feed_events.user_id",
             "user_feed_events.subscription_id", "user_feed_events.repository_id"],
            ondelete="CASCADE", name="fk_feed_group_member_event_scope",
        ),
        Index("ix_feed_update_group_members_group", "group_id"),
    )

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    group_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    subscription_id: Mapped[str] = mapped_column(String, nullable=False)
    repository_id: Mapped[str] = mapped_column(String, nullable=False)
