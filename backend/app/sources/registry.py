"""Registry of source adapters that support repository monitoring."""

from __future__ import annotations

from collections.abc import Callable

from app.models.repository import Repository, parse_repository_id
from app.sources import github, gitlab
from app.sources.common import RepositoryMonitor
from app.sources.github.repository import load_repository_profile as load_github_profile
from app.sources.gitlab.repository import load_repository_profile as load_gitlab_profile

_REPOSITORY_MONITORS: dict[str, RepositoryMonitor] = {
    "github": github,
    "gitlab": gitlab,
}

_REPOSITORY_PROFILE_LOADERS: dict[str, Callable[[str], Repository]] = {
    "github": load_github_profile,
    "gitlab": load_gitlab_profile,
}


def load_repository_profile(repository_id: str) -> Repository:
    """Dispatch a canonical ID to its registered profile adapter."""
    source = repository_id.partition(":repo:")[0]
    loader = _REPOSITORY_PROFILE_LOADERS.get(source)
    if loader is None:
        raise ValueError("Repository source does not support profile lookup.")
    provider_id = parse_repository_id(repository_id, source=source)
    if not provider_id.isascii() or not provider_id.isdecimal() or int(provider_id) <= 0:
        raise ValueError("Repository ID must contain a positive numeric provider ID.")
    return loader(provider_id)


def get_repository_monitor(source: str) -> RepositoryMonitor | None:
    """Return the monitoring adapter registered for one repository source."""

    return _REPOSITORY_MONITORS.get(source)
