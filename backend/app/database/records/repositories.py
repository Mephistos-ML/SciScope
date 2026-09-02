"""SQLAlchemy repository and subscription persistence record models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base


class RepositoryRecordModel(Base):
    """Current global catalog profile for one provider repository."""

    __tablename__ = "repositories"
    __table_args__ = (
        Index("ix_repositories_source", "source"),
        Index("ix_repositories_full_name", "full_name"),
        Index(
            "ux_repositories_source_provider_repository_id",
            "source",
            "provider_repository_id",
            unique=True,
        ),
    )

    repository_id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    provider_repository_id: Mapped[str] = mapped_column(String, nullable=False)
    owner_login: Mapped[str] = mapped_column(String, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    language: Mapped[str] = mapped_column(String, nullable=False, default="")
    stars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    topics_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    search_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RepositorySearchEvidenceRecordModel(Base):
    """Durable source-independent retrieval evidence for one catalog repository."""

    __tablename__ = "repository_search_evidence"
    __table_args__ = (
        Index("ix_repository_search_evidence_query", "query_normalized"),
        Index("ix_repository_search_evidence_repository", "repository_id"),
    )

    repository_id: Mapped[str] = mapped_column(String, primary_key=True)
    query_normalized: Mapped[str] = mapped_column(String, primary_key=True)
    channel: Mapped[str] = mapped_column(String, primary_key=True)
    match_location: Mapped[str] = mapped_column(String, primary_key=True)
    matched_path: Mapped[str] = mapped_column(String, primary_key=True, default="")
    matched_excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    provider_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


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
