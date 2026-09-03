"""SQLAlchemy records for the internal ranking-label dataset."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database.base import Base


class RankingDatasetRunRecordModel(Base):
    __tablename__ = "ranking_dataset_runs"
    __table_args__ = (Index("ix_ranking_dataset_runs_user_created_at", "user_id", "created_at"),)

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    search_job_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    topic_description: Mapped[str] = mapped_column(Text, nullable=False)
    generated_queries_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    ranking_policy_version: Mapped[str] = mapped_column(String, nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RankingDatasetExampleRecordModel(Base):
    __tablename__ = "ranking_dataset_examples"
    __table_args__ = (Index("ix_ranking_dataset_examples_run_rank", "run_id", "rank_position"),)

    run_id: Mapped[str] = mapped_column(ForeignKey("ranking_dataset_runs.run_id", ondelete="CASCADE"), primary_key=True)
    repository_id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)
    ranking_score: Mapped[float] = mapped_column(nullable=False)
    candidate_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    features_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    manual_label: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
