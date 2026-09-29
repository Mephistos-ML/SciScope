"""SQLAlchemy records for durable Explore search execution reports."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base


class SearchRunRecordModel(Base):
    __tablename__ = "search_runs"
    __table_args__ = (
        Index("ix_search_runs_owner_created", "owner_user_id", "created_at"),
        Index("ix_search_runs_status_created", "status", "created_at"),
    )

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    topic_description: Mapped[str] = mapped_column(Text, nullable=False)
    topic_hash: Mapped[str] = mapped_column(String, nullable=False)
    response_mode: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    planner_mode: Mapped[str] = mapped_column(String, nullable=False)
    planner_model: Mapped[str | None] = mapped_column(String, nullable=True)
    ranking_policy_version: Mapped[str] = mapped_column(String, nullable=False)
    backend_revision: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    execution_state_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class SearchRunOperationRecordModel(Base):
    __tablename__ = "search_run_operations"
    __table_args__ = (Index("ix_search_run_operations_run_queued", "run_id", "queued_at"),)

    operation_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("search_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_holder_id: Mapped[str | None] = mapped_column(String, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class SearchRunStageRecordModel(Base):
    __tablename__ = "search_run_stages"
    __table_args__ = (Index("ix_search_run_stages_operation", "operation_id"),)

    run_id: Mapped[str] = mapped_column(
        ForeignKey("search_runs.run_id", ondelete="CASCADE"),
        primary_key=True,
    )
    stage_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    operation_id: Mapped[str] = mapped_column(
        ForeignKey("search_run_operations.operation_id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    executed_query_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    retrieved_candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    admitted_candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    visible_candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    timings_json: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SearchRunProviderOutcomeRecordModel(Base):
    __tablename__ = "search_run_provider_outcomes"
    __table_args__ = (
        Index(
            "ix_search_run_provider_outcomes_stage",
            "run_id",
            "stage_number",
        ),
        Index(
            "ix_search_run_provider_outcomes_source_channel",
            "source",
            "channel",
        ),
    )

    outcome_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("search_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    operation_id: Mapped[str] = mapped_column(
        ForeignKey("search_run_operations.operation_id", ondelete="CASCADE"),
        nullable=False,
    )
    stage_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    query_id: Mapped[str] = mapped_column(String, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class SearchRunRankingCandidateRecordModel(Base):
    __tablename__ = "search_run_ranking_candidates"
    __table_args__ = (
        Index("ix_search_run_ranking_candidates_run_stage_rank", "run_id", "stage_number", "rank_position"),
        Index("ix_search_run_ranking_candidates_repository", "repository_id"),
    )

    run_id: Mapped[str] = mapped_column(
        ForeignKey("search_runs.run_id", ondelete="CASCADE"),
        primary_key=True,
    )
    stage_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository_id: Mapped[str] = mapped_column(String, primary_key=True)
    repository_source: Mapped[str] = mapped_column(String, nullable=False)
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)
    final_score: Mapped[float] = mapped_column(nullable=False)
    candidate_facts_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    retrieval_facts_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    admission_facts_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    ranking_features_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    score_breakdown_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class SearchRunRankingLabelRecordModel(Base):
    __tablename__ = "search_run_ranking_labels"
    __table_args__ = (Index("ix_search_run_ranking_labels_run_stage", "run_id", "stage_number"),)

    run_id: Mapped[str] = mapped_column(
        ForeignKey("search_runs.run_id", ondelete="CASCADE"),
        primary_key=True,
    )
    repository_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    stage_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
