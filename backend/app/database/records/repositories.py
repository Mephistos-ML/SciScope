"""SQLAlchemy repository and subscription persistence record models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base


class RepositoryRecordModel(Base):
    """Globally known watched repository."""

    __tablename__ = "repositories"
    __table_args__ = (
        Index("ix_repositories_source", "source"),
        Index("ix_repositories_full_name", "full_name"),
    )

    repository_id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RepositoryCheckpointRecordModel(Base):
    """Per-subscription monitoring cursor for a repository."""

    __tablename__ = "repository_checkpoints"
    __table_args__ = (
        Index("ix_repository_checkpoints_subscription", "subscription_id"),
    )

    subscription_id: Mapped[str] = mapped_column(String, primary_key=True)
    repository_id: Mapped[str] = mapped_column(String, primary_key=True)
    checkpoint_key: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    checkpoint_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SubscriptionRecordModel(Base):
    """Persisted user subscription."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_user_id_created_at", "user_id", "created_at"),
        Index("ux_subscriptions_user_repository", "user_id", "repository_id", unique=True),
    )

    subscription_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    repository_id: Mapped[str] = mapped_column(String, nullable=False)
    selected_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
