"""SQLAlchemy persistence models for SciScope."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base


class UserRecordModel(Base):
    """Persisted first-party user identity."""

    __tablename__ = "users"
    __table_args__ = (
        Index("ux_users_email", "email", unique=True),
    )

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OAuthAccountRecordModel(Base):
    """Linked external identity provider account."""

    __tablename__ = "oauth_accounts"
    __table_args__ = (
        Index("ix_oauth_accounts_user_id_provider", "user_id", "provider"),
        Index(
            "ux_oauth_accounts_provider_subject",
            "provider",
            "provider_subject",
            unique=True,
        ),
    )

    oauth_account_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_subject: Mapped[str] = mapped_column(String, nullable=False)
    provider_email: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserSessionRecordModel(Base):
    """Durable first-party authenticated web session."""

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("ix_user_sessions_user_id", "user_id"),
        Index("ux_user_sessions_token_hash", "session_token_hash", unique=True),
        Index("ix_user_sessions_expires_at", "expires_at"),
    )

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    session_token_hash: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SeenSignalRecord(Base):
    """Durable source-scoped identity anchors for raw signals."""

    __tablename__ = "seen_signals"
    __table_args__ = (
        Index("ix_seen_signals_source", "source"),
    )

    source: Mapped[str] = mapped_column(String, primary_key=True)
    item_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RepositoryRecord(Base):
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


class RepositoryCheckpointRecord(Base):
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


class ExploreSearchEventRecord(Base):
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
