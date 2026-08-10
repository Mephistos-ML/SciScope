"""SQLAlchemy persistence models for SciScope."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


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
    manual_keywords_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
