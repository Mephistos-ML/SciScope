"""Repository activity, durable monitoring facts and checkpoint identities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.models.signal import Signal

REPOSITORY_MAIN_COMMIT_SHA_CHECKPOINT_KEY = "latest_main_commit_sha"
REPOSITORY_RELEASE_CHECKPOINT_KEY = "latest_release_published_at"
REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY = "latest_main_commit_published_at"
MAX_RELEASE_COMMIT_DETAILS = 500

ReleaseCommitStatus = Literal["complete", "partial", "unavailable"]


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


@dataclass(frozen=True)
class ReleaseCommitDetails:
    """Provider-confirmed commits in a pinned, ancestral release comparison."""

    status: ReleaseCommitStatus = "unavailable"
    commits: tuple[Signal, ...] = ()
    base_sha: str | None = None
    head_sha: str | None = None
    total_count: int | None = None

    def __post_init__(self) -> None:
        if self.status not in {"complete", "partial", "unavailable"}:
            raise ValueError("Unsupported release commit coverage.")
        if self.status == "unavailable" and self.commits:
            raise ValueError("Unavailable comparisons cannot assert commit membership.")
        if self.status != "unavailable" and not (self.base_sha and self.head_sha):
            raise ValueError("Confirmed comparisons require pinned endpoints.")
        if len(self.commits) > MAX_RELEASE_COMMIT_DETAILS:
            raise ValueError("Release comparison exceeds the commit budget.")
        if any(commit.kind != "commit" for commit in self.commits) or len(
            {c.item_id for c in self.commits}
        ) != len(self.commits):
            raise ValueError("Release details require distinct commit facts.")
        if self.total_count is not None and (
            self.total_count < len(self.commits) or self.total_count < 0
        ):
            raise ValueError(
                "Comparison count cannot be smaller than confirmed commits."
            )
        if self.status == "complete" and self.total_count != len(self.commits):
            raise ValueError("Complete coverage requires the exact commit count.")
