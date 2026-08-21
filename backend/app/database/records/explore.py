"""SQLAlchemy explore persistence record models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ExploreSearchEventRecordModel(Base):
    """Persisted explore access attempt for quotas, cooldowns, and telemetry."""

    __tablename__ = "explore_search_events"
    __table_args__ = (
        Index(
            "ix_explore_search_events_subject_created_at",
            "subject_type",
            "subject_key",
            "created_at",
        ),
        Index(
            "ix_explore_search_events_outcome_created_at",
            "outcome",
            "created_at",
        ),
        Index("ix_explore_search_events_created_at", "created_at"),
        Index("ix_explore_search_events_user_id_created_at", "user_id", "created_at"),
    )

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    subject_type: Mapped[str] = mapped_column(String, nullable=False)
    subject_key: Mapped[str] = mapped_column(String, nullable=False)
    ip_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    topic_hash: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
