"""SQLAlchemy feed-event persistence record models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base


class FeedEventRecordModel(Base):
    """Append-only feed event stored per user subscription."""

    __tablename__ = "feed_events"
    __table_args__ = (
        Index("ix_feed_events_user_created_at", "user_id", "created_at"),
        Index("ix_feed_events_user_published_at", "user_id", "published_at"),
        Index("ix_feed_events_subscription_created_at", "subscription_id", "created_at"),
        Index("ix_feed_events_repository_created_at", "repository_id", "created_at"),
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
