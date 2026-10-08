"""Provider-native profile lookup, identity validation and complete field mapping."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.integrations.repositories.common.models import JsonResponse
from app.integrations.repositories.common.source_status import RepositorySourceError
from app.integrations.repositories.github import repository as github
from app.integrations.repositories.gitlab import repository as gitlab
from tests.fixtures.repository_clients import make_repository_client


def _payload(source, provider_id=123):
    if source == "github":
        return {
            "id": provider_id, "full_name": "science/tool", "html_url": "https://github.com/science/tool",
            "owner": {"login": "science"}, "description": "Simulation", "language": "Python",
            "stargazers_count": 42, "topics": ["simulation"], "updated_at": "2026-10-01T00:00:00Z",
        }
    return {
        "id": provider_id, "path_with_namespace": "science/tool", "web_url": "https://gitlab.com/science/tool",
        "description": "Simulation", "star_count": 42, "topics": ["simulation"],
        "last_activity_at": "2026-10-01T00:00:00Z",
    }


@pytest.mark.parametrize("source,module", [("github", github), ("gitlab", gitlab)])
def test_lookup_uses_provider_id_and_maps_profile(source, module, monkeypatch):
    requests = []
    def fetch(url):
        requests.append(url)
        return JsonResponse({"Python": 90.0, "Shell": 10.0} if url.endswith("/languages") else _payload(source), url)
    client = make_repository_client(source)
    monkeypatch.setattr(client, "fetch_json", fetch)
    profile = module.load_repository_profile("123", client=client)
    assert requests[0].endswith("/repositories/123" if source == "github" else "/projects/123")
    assert profile.provider_repository_id == "123"
    assert profile.repository_id == f"{source}:repo:123"
    assert profile.full_name == "science/tool"
    assert profile.owner_login == "science"
    assert profile.description == "Simulation"
    assert profile.stars == 42
    assert profile.topics == ("simulation",)
    assert profile.language == "Python"
    assert profile.provider_updated_at == datetime(2026, 10, 1, tzinfo=UTC)


@pytest.mark.parametrize("source,module", [("github", github), ("gitlab", gitlab)])
def test_mismatched_provider_id_is_rejected(source, module, monkeypatch):
    client = make_repository_client(source)
    monkeypatch.setattr(client, "fetch_json", lambda url: JsonResponse(_payload(source, 456), url))
    with pytest.raises(RepositorySourceError, match="invalid repository profile"):
        module.load_repository_profile("123", client=client)


@pytest.mark.parametrize("source,module", [("github", github), ("gitlab", gitlab)])
@pytest.mark.parametrize("invalid", [None, [], {}, {"id": 123}, {"id": "owner/tool"}])
def test_invalid_payloads_are_classified_as_source_errors(source, module, invalid, monkeypatch):
    client = make_repository_client(source)
    monkeypatch.setattr(client, "fetch_json", lambda url: JsonResponse(invalid, url))
    with pytest.raises(RepositorySourceError):
        module.load_repository_profile("123", client=client)


@pytest.mark.parametrize("source,module", [("github", github), ("gitlab", gitlab)])
def test_profile_url_must_belong_to_repository_host(source, module, monkeypatch):
    payload = _payload(source)
    payload["html_url" if source == "github" else "web_url"] = "https://example.com/science/tool"
    client = make_repository_client(source)
    monkeypatch.setattr(client, "fetch_json", lambda url: JsonResponse(payload, url))
    with pytest.raises(RepositorySourceError):
        module.load_repository_profile("123", client=client)


@pytest.mark.parametrize("source,module", [("github", github), ("gitlab", gitlab)])
def test_invalid_json_is_a_provider_error(source, module, monkeypatch):
    from json import JSONDecodeError
    def fetch(url):
        raise JSONDecodeError("Invalid provider JSON", "broken", 0)
    client = make_repository_client(source)
    monkeypatch.setattr(client, "fetch_json", fetch)
    with pytest.raises(RepositorySourceError):
        module.load_repository_profile("123", client=client)
