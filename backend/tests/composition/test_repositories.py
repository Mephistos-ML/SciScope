"""Repository entrypoints bind deployment configuration without adapter globals."""

from io import BytesIO
import json

import pytest

from app import config
from app.composition.repositories import build_repository_adapters
from app.composition.search import build_explore_dependencies
from app.integrations.repositories.gitlab import client


def test_configured_gitlab_host_and_token_remain_bound_for_profile_lookup(monkeypatch):
    monkeypatch.setattr(config, "GITLAB_BASE_URL", "https://first.example/gitlab")
    monkeypatch.setattr(config, "GITLAB_AUTH_MODE", "service_account")
    monkeypatch.setattr(config, "GITLAB_SERVICE_ACCOUNT_TOKEN", "first-secret")
    first = build_repository_adapters()
    monkeypatch.setattr(config, "GITLAB_BASE_URL", "https://second.example")
    monkeypatch.setattr(config, "GITLAB_SERVICE_ACCOUNT_TOKEN", "second-secret")
    second = build_repository_adapters()
    requests = []
    def fetch(request, timeout):
        requests.append((request.full_url, request.get_header("Private-token")))
        base = "https://first.example/gitlab" if "first.example" in request.full_url else "https://second.example"
        payload = [] if "/search?" in request.full_url else {"Python": 100} if request.full_url.endswith("/languages") else {
            "id": 123, "path_with_namespace": "science/tool", "web_url": base + "/science/tool",
        }
        return BytesIO(json.dumps(payload).encode())
    monkeypatch.setattr(client, "urlopen", fetch)
    assert first.load_repository_profile("gitlab:repo:123").url == "https://first.example/gitlab/science/tool"
    assert second.load_repository_profile("gitlab:repo:123").url == "https://second.example/science/tool"
    assert requests == [
        ("https://first.example/gitlab/api/v4/projects/123", "first-secret"),
        ("https://first.example/gitlab/api/v4/projects/123/languages", "first-secret"),
        ("https://second.example/api/v4/projects/123", "second-secret"),
        ("https://second.example/api/v4/projects/123/languages", "second-secret"),
    ]
    lane = next(lane for lane in build_explore_dependencies(repositories=first).lanes
                if lane.source == "gitlab" and lane.channel == "repository_search")
    assert lane.discover(("science",)) == []
    assert requests[-1][0].startswith("https://first.example/gitlab/api/v4/search?")
    assert requests[-1][1] == "first-secret"
    profile = first.load_repository_profile("gitlab:repo:123")
    assert first.monitors["gitlab"].refresh_repository_profile(profile).url == profile.url
    assert requests[-1] == ("https://first.example/gitlab/api/v4/projects/123", "first-secret")
    assert "first-secret" not in repr(first) and "second-secret" not in repr(second)


@pytest.mark.parametrize("repository_id", ["unknown:repo:123", "gitlab:repo:owner/tool",
                                         "gitlab:repo:0", "gitlab:repo:-1", "gitlab:repo:１２３"])
def test_invalid_repository_identity_is_rejected_before_provider_io(repository_id):
    with pytest.raises(ValueError):
        build_repository_adapters().load_repository_profile(repository_id)
