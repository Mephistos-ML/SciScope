"""SQLAlchemy records for durable monitoring execution state."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class RepositoryMonitoringCursorRecordModel(Base):
    __tablename__ = "repository_monitoring_cursors"
    repository_id: Mapped[str] = mapped_column(String, primary_key=True)
    checkpoint_key: Mapped[str] = mapped_column(String, primary_key=True)
    checkpoint_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MonitoringJobLeaseRecordModel(Base):
    __tablename__ = "monitoring_job_leases"
    job_name: Mapped[str] = mapped_column(String, primary_key=True)
    holder_id: Mapped[str] = mapped_column(String, nullable=False)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MonitoringRunRecordModel(Base):
    __tablename__ = "monitoring_runs"
    __table_args__ = (Index("ix_monitoring_runs_started_at", "started_at"),)
    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    scanned_repository_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_repository_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class RepositoryMonitoringCheckRecordModel(Base):
    __tablename__ = "repository_monitoring_checks"
    __table_args__ = (Index("ix_repository_monitoring_checks_repository_checked", "repository_id", "checked_at"),)
    repository_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
