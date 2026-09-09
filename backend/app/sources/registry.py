"""Registry of source adapters that support repository monitoring."""

from __future__ import annotations

from app.sources import github, gitlab
from app.sources.common import RepositoryMonitor

_REPOSITORY_MONITORS: dict[str, RepositoryMonitor] = {
    "github": github,
    "gitlab": gitlab,
}


def get_repository_monitor(source: str) -> RepositoryMonitor | None:
    """Return the monitoring adapter registered for one repository source."""

    return _REPOSITORY_MONITORS.get(source)
