"""SQLAlchemy persistence models for SciScope."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
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


class EntityRecord(Base):
    """Globally known watchable entity."""

    __tablename__ = "entities"
    __table_args__ = (
        Index("ix_entities_source_entity_type", "source", "entity_type"),
        Index("ix_entities_canonical_name", "canonical_name"),
    )

    entity_id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SubscriptionEntityMatchRecord(Base):
    """Subscription-scoped relevance link to an entity."""

    __tablename__ = "subscription_entity_matches"
    __table_args__ = (
        Index("ix_subscription_entity_matches_subscription", "subscription_id"),
        Index("ix_subscription_entity_matches_source", "source"),
    )

    subscription_id: Mapped[str] = mapped_column(String, primary_key=True)
    entity_id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    active: Mapped[bool] = mapped_column(nullable=False, default=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    matched_terms_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    excluded_terms_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EntityCheckpointRecord(Base):
    """Per-subscription monitoring cursor for an entity."""

    __tablename__ = "entity_checkpoints"
    __table_args__ = (
        Index("ix_entity_checkpoints_subscription", "subscription_id"),
    )

    subscription_id: Mapped[str] = mapped_column(String, primary_key=True)
    entity_id: Mapped[str] = mapped_column(String, primary_key=True)
    checkpoint_key: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    checkpoint_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SubscriptionRecordModel(Base):
    """Persisted user subscription."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_user_id_created_at", "user_id", "created_at"),
    )

    subscription_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    topic_description: Mapped[str] = mapped_column(Text, nullable=False)
    search_scope: Mapped[str] = mapped_column(String, nullable=False, default="repositories")
    query_terms_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
