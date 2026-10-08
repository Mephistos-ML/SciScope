"""Explicit provider IO doubles; unexpected network access fails immediately."""

from types import SimpleNamespace
from app.integrations.repositories.github.monitor import GitHubRepositoryMonitor
from app.integrations.repositories.gitlab.monitor import GitLabRepositoryMonitor


def make_repository_client(source):
    def unexpected(*args, **kwargs):
        raise AssertionError("Unexpected provider IO")
    base_url = f"https://{source}.com"
    return SimpleNamespace(base_url=base_url,
                           api_base="https://api.github.com" if source == "github" else base_url + "/api/v4",
                           fetch_json=unexpected)


def make_repository_monitor(source):
    monitor = GitHubRepositoryMonitor if source == "github" else GitLabRepositoryMonitor
    return monitor(make_repository_client(source))
