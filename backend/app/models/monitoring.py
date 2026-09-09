"""Durable monitoring job facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MonitoringRun:
    run_id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    scanned_repository_count: int
    failed_repository_count: int
    error_summary: str | None


@dataclass(frozen=True)
class RepositoryMonitoringCheck:
    repository_id: str
    checked_at: datetime
    status: str
    error_code: str | None
    error_message: str | None
