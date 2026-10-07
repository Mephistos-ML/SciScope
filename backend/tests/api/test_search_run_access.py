"""Owner and guest-capability access to durable Explore runs."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest
from fastapi import Response
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.app import app
from app.config import AUTH_SESSION_COOKIE_NAME, CORS_ORIGINS
from app.database.records.search_runs import SearchRunOperationRecordModel
from app.database.session import session_scope
from app.models.ai import AiSearchPlan
from app.services.auth.service import create_authenticated_session
from app.services.search.explore.execution import ExploreSearchExecution, serialize_execution
from app.services.search.explore.jobs import create_explore_search_run
from app.services.search.retrieval.models import RetrievedCandidates
from app.storage.auth.users import create_user
from app.storage.search_runs import create_search_run, get_search_run, get_search_run_report, update_search_run
from tests.conftest import build_test_database_url, migrate_test_database


@pytest.fixture
def database_url(tmp_path, monkeypatch):
    url = build_test_database_url(tmp_path / "run-access.sqlite3")
    migrate_test_database(url)
    monkeypatch.setattr(app.state, "database_url", url)
    return url


@pytest.fixture
def users(database_url):
    return {
        name: create_user(email=f"{name}@example.com", display_name=name, database_url=database_url)
        for name in ("owner", "other")
    }


def _sign_in(client, user, database_url):
    token = create_authenticated_session(user.user_id, Response(), database_url=database_url)
    client.cookies.set(AUTH_SESSION_COOKIE_NAME, token)


def _completed_run(database_url, owner_user_id=None):
    created = create_explore_search_run(
        topic_description="Private research topic", owner_user_id=owner_user_id,
        database_url=database_url,
    )
    execution = ExploreSearchExecution(
        AiSearchPlan("ready", ("first", "second")), ("first",), RetrievedCandidates((), (), 1),
    )
    update_search_run(
        created["runId"], status="completed", execution_state=serialize_execution(execution),
        database_url=database_url,
    )
    return created


def _operation_count(run_id, database_url):
    with session_scope(database_url) as session:
        return session.scalar(select(func.count()).select_from(SearchRunOperationRecordModel).where(
            SearchRunOperationRecordModel.run_id == run_id,
        ))


@pytest.mark.parametrize("viewer", ["owner", "other", "anonymous"])
@pytest.mark.parametrize("method", ["get", "expand"])
def test_user_run_requires_owner(database_url, users, viewer, method):
    created = _completed_run(database_url, users["owner"].user_id)
    assert "guestAccessToken" not in created
    run_id = created["runId"]
    before_count = _operation_count(run_id, database_url)
    with TestClient(app) as client:
        if viewer != "anonymous":
            _sign_in(client, users[viewer], database_url)
        # A guest credential never grants access to an owned run.
        headers = {"X-Search-Run-Token": "unrelated-guest-token"}
        path = f"/api/explore/search-runs/{run_id}"
        response = client.get(path, headers=headers) if method == "get" else client.post(path + "/expand", headers=headers)
        if viewer == "owner":
            assert response.status_code == (200 if method == "get" else 202)
            assert response.json()["topicDescription"] == "Private research topic"
        else:
            unknown = client.get("/api/explore/search-runs/missing") if method == "get" else client.post("/api/explore/search-runs/missing/expand")
            assert response.status_code == unknown.status_code == 404
            assert response.json() == unknown.json()
            assert _operation_count(run_id, database_url) == before_count
            assert get_search_run(run_id, database_url=database_url).status == "completed"


@pytest.mark.parametrize("credential", ["correct", "missing", "wrong", "another_run"])
@pytest.mark.parametrize("method", ["get", "expand"])
def test_guest_run_requires_its_own_token(database_url, credential, method):
    created = _completed_run(database_url)
    token = created["guestAccessToken"]
    if credential == "another_run":
        token = create_explore_search_run(topic_description="Other topic", database_url=database_url)["guestAccessToken"]
    elif credential == "wrong":
        token = "incorrect-token"
    headers = {} if credential == "missing" else {"X-Search-Run-Token": token}
    run_id = created["runId"]
    before_count = _operation_count(run_id, database_url)
    with TestClient(app) as client:
        path = f"/api/explore/search-runs/{run_id}"
        response = client.get(path, headers=headers) if method == "get" else client.post(path + "/expand", headers=headers)
    if credential == "correct":
        assert response.status_code == (200 if method == "get" else 202)
        assert "guestAccessToken" not in response.json()
        assert "guest_access_token_hash" not in response.json()
    else:
        assert response.status_code == 404
        assert _operation_count(run_id, database_url) == before_count
        assert get_search_run(run_id, database_url=database_url).status == "completed"


@pytest.mark.parametrize("state", ["queued", "failed", "completed"])
def test_denied_expansion_does_not_expose_lifecycle_state(database_url, state):
    created = _completed_run(database_url)
    update_search_run(created["runId"], status=state, database_url=database_url)
    with TestClient(app) as client:
        response = client.post(f"/api/explore/search-runs/{created['runId']}/expand")
    assert response.status_code == 404
    assert response.json() == {"error": "Explore search run not found"}
    assert get_search_run(created["runId"], database_url=database_url).status == state


def test_token_is_issued_once_and_only_hash_is_persisted(database_url, caplog):
    with TestClient(app) as client:
        response = client.post("/api/explore/search-runs", json={"topicDescription": "Guest topic"})
        assert response.status_code == 202
        created = response.json()
        token = created["guestAccessToken"]
        snapshot = client.get(f"/api/explore/search-runs/{created['runId']}", headers={"X-Search-Run-Token": token})
    assert snapshot.status_code == 200
    assert "guestAccessToken" not in snapshot.json()
    stored = get_search_run(created["runId"], database_url=database_url)
    expected_hash = hashlib.sha256(token.encode()).hexdigest()
    assert stored.guest_access_token_hash == expected_hash
    assert stored.response_payload is None
    assert stored.execution_state is None
    report = json.dumps(get_search_run_report(created["runId"], database_url=database_url))
    assert token not in report and expected_hash not in report
    assert expected_hash not in repr(stored)
    assert token not in caplog.text


def test_owned_creation_does_not_issue_guest_token(database_url, users):
    with TestClient(app) as client:
        _sign_in(client, users["owner"], database_url)
        response = client.post("/api/explore/search-runs", json={"topicDescription": "Owned topic"})
    assert response.status_code == 202
    created = response.json()
    assert "guestAccessToken" not in created
    stored = get_search_run(created["runId"], database_url=database_url)
    assert stored.owner_user_id == users["owner"].user_id
    assert stored.guest_access_token_hash is None


@pytest.mark.parametrize("owned", [False, True])
def test_legacy_runs_without_guest_hash(database_url, users, owned):
    template = _completed_run(database_url, users["owner"].user_id if owned else None)
    stored = get_search_run(template["runId"], database_url=database_url)
    legacy = replace(stored, run_id="legacy-run", guest_access_token_hash=None)
    create_search_run(legacy, database_url=database_url)
    with TestClient(app) as client:
        _sign_in(client, users["owner"], database_url)
        headers = {"X-Search-Run-Token": template.get("guestAccessToken", "anything")}
        read = client.get("/api/explore/search-runs/legacy-run", headers=headers)
        expand = client.post("/api/explore/search-runs/legacy-run/expand", headers=headers)
    assert read.status_code == (200 if owned else 404)
    assert expand.status_code == (202 if owned else 404)


def test_guest_token_in_url_does_not_grant_access(database_url):
    created = _completed_run(database_url)
    with TestClient(app) as client:
        response = client.get(f"/api/explore/search-runs/{created['runId']}", params={"guestAccessToken": created["guestAccessToken"]})
    assert response.status_code == 404


def test_browser_preflight_allows_guest_token_header(database_url):
    with TestClient(app) as client:
        response = client.options("/api/explore/search-runs/run", headers={
            "Origin": CORS_ORIGINS[0], "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Search-Run-Token",
        })
    assert response.status_code == 200
    assert "x-search-run-token" in response.headers["access-control-allow-headers"].lower()
