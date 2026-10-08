"""Repository activity, durable monitoring facts and checkpoint identities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.models.signal import Signal

REPOSITORY_MAIN_COMMIT_SHA_CHECKPOINT_KEY = "latest_main_commit_sha"
REPOSITORY_RELEASE_CHECKPOINT_KEY = "latest_release_published_at"
REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY = "latest_main_commit_published_at"


@dataclass(frozen=True)
class RepositoryActivity:
    """Repository events returned by one provider scan."""

    signals: tuple[Signal, ...]
    releases_complete: bool
    commits_complete: bool
    commit_head_sha: str | None = None
    redirected: bool = False


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


@dataclass(frozen=True)
class MonitoringLease:
    job_name: str
    holder_id: str
    token: str = field(repr=False)


class MonitoringLeaseLostError(RuntimeError):
    """The scan no longer has authority to publish monitoring facts."""
