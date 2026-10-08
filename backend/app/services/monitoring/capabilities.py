"""Provider capability required by repository monitoring orchestration."""

from datetime import datetime
from typing import Protocol

from app.models.monitoring import RepositoryActivity
from app.models.repository import Repository


class RepositoryMonitor(Protocol):
    """Read activity and refresh canonical profiles for the monitoring use case."""

    def load_repository_activity(
        self,
        repository: Repository,
        *,
        release_started_after: datetime | None,
        commit_started_after: datetime | None,
        commit_after_sha: str | None = None,
    ) -> RepositoryActivity: ...

    def refresh_repository_profile(self, repository: Repository) -> Repository: ...
