"""Bind one process's repository adapters and their credential/cache lifetimes."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from types import MappingProxyType

from app import config
from app.models.repository import Repository, parse_repository_id
from app.services.monitoring.capabilities import RepositoryMonitor
from app.integrations.repositories.github.auth import GitHubAppAuth
from app.integrations.repositories.github.client import GitHubClient
from app.integrations.repositories.github.monitor import GitHubRepositoryMonitor
from app.integrations.repositories.github.repository import load_repository_profile as github_profile
from app.integrations.repositories.gitlab.auth import build_auth_headers
from app.integrations.repositories.gitlab.client import GitLabClient
from app.integrations.repositories.gitlab.monitor import GitLabRepositoryMonitor
from app.integrations.repositories.gitlab.repository import load_repository_profile as gitlab_profile


@dataclass(frozen=True)
class RepositoryAdapters:
    github: GitHubClient
    gitlab: GitLabClient
    monitors: Mapping[str, RepositoryMonitor]
    profile_loaders: Mapping[str, Callable[[str], Repository]]

    def load_repository_profile(self, repository_id: str) -> Repository:
        source = repository_id.partition(":repo:")[0]
        loader = self.profile_loaders.get(source)
        if loader is None:
            raise ValueError("Repository source does not support profile lookup.")
        provider_id = parse_repository_id(repository_id, source=source)
        if not provider_id.isascii() or not provider_id.isdecimal() or int(provider_id) <= 0:
            raise ValueError("Repository ID must contain a positive numeric provider ID.")
        return loader(provider_id)


def build_repository_adapters() -> RepositoryAdapters:
    auth = GitHubAppAuth(
        mode=config.GITHUB_AUTH_MODE, app_id=config.GITHUB_APP_ID,
        installation_id=config.GITHUB_APP_INSTALLATION_ID, private_key=config.GITHUB_APP_PRIVATE_KEY,
    )
    github = GitHubClient(auth.build_auth_headers)
    gitlab = GitLabClient(config.GITLAB_BASE_URL, partial(
        build_auth_headers, mode=config.GITLAB_AUTH_MODE, token=config.GITLAB_SERVICE_ACCOUNT_TOKEN,
    ))
    return RepositoryAdapters(
        github, gitlab,
        MappingProxyType({"github": GitHubRepositoryMonitor(github), "gitlab": GitLabRepositoryMonitor(gitlab)}),
        MappingProxyType({"github": partial(github_profile, client=github), "gitlab": partial(gitlab_profile, client=gitlab)}),
    )
