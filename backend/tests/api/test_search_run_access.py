"""Owner and guest-capability access to durable Explore runs."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.app import app
from app.config import AUTH_SESSION_COOKIE_NAME, CORS_ORIGINS
from app.database.records.search_runs import SearchRunOperationRecordModel, SearchRunRecordModel
from app.database.session import session_scope
from app.models.ai import AiSearchPlan
from app.services.auth.service import create_authenticated_session
from app.services.search.explore.execution import ExploreSearchExecution, serialize_execution
from app.services.search.retrieval.models import RetrievedCandidates
from app.storage.auth.users import create_user
from app.storage.search_runs import write_search_run, get_search_run, get_search_run_report
from tests.conftest import build_test_database_url, migrate_test_database
from tests.fixtures.search_runs import seed_search_run, set_search_run_state


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
    token = create_authenticated_session(user.user_id, database_url=database_url, ttl_seconds=3600)
    client.cookies.set(AUTH_SESSION_COOKIE_NAME, token)


def _completed_run(database_url, owner_user_id=None):
    created = seed_search_run(
        topic_description="Private research topic", owner_user_id=owner_user_id,
        database_url=database_url,
    )
    execution = ExploreSearchExecution(
        AiSearchPlan("ready", ("first", "second")), ("first",), RetrievedCandidates((), (), 1),
    )
    set_search_run_state(
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
        token = seed_search_run(topic_description="Other topic", database_url=database_url)["guestAccessToken"]
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
    set_search_run_state(created["runId"], status=state, database_url=database_url)
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
    with session_scope(database_url) as session:
        write_search_run(session, legacy)
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


@pytest.mark.parametrize("limit", ["guest", "user", "global", "cooldown"])
def test_expansion_enforces_existing_limits(database_url, users, monkeypatch, limit):
    from app.services.search.access import policy, service
    from app.models.explore_access import ExploreLimitCode

    user = users["owner"] if limit == "user" else None
    created = _completed_run(database_url, user.user_id if user else None)
    with TestClient(app) as client:
        if user:
            _sign_in(client, user, database_url)
        actor = service.resolve_explore_actor(
            user, client_ip="testclient", database_url=database_url,
        )
        service.record_allowed_explore_attempt(actor, topic_hash="old", database_url=database_url)
        monkeypatch.setattr(policy, "EXPLORE_GUEST_COOLDOWN_SECONDS", 0 if limit != "cooldown" else 60)
        monkeypatch.setattr(policy, "EXPLORE_GUEST_DAILY_LIMIT", 1 if limit == "guest" else 100)
        monkeypatch.setattr(policy, "EXPLORE_USER_DAILY_LIMIT", 1)
        monkeypatch.setattr(policy, "EXPLORE_USER_COOLDOWN_SECONDS", 0)
        monkeypatch.setattr(policy, "EXPLORE_GLOBAL_DAILY_LIMIT", 1 if limit == "global" else 100)
        response = client.post(f"/api/explore/search-runs/{created['runId']}/expand",
                               headers={"X-Search-Run-Token": created["guestAccessToken"]} if not user else {})
    assert response.status_code == (503 if limit == "global" else 429)
    expected = {"guest": ExploreLimitCode.GUEST_QUOTA_EXCEEDED,
                "user": ExploreLimitCode.USER_QUOTA_EXCEEDED,
                "global": ExploreLimitCode.GLOBAL_CAPACITY_REACHED,
                "cooldown": ExploreLimitCode.GUEST_COOLDOWN}
    assert response.json()["code"] == expected[limit]
    if "retryAfterSeconds" in response.json():
        assert response.headers["Retry-After"] == str(response.json()["retryAfterSeconds"])
    assert "signInSuggested" in response.json()
    assert "turnstileRequired" in response.json()
    from app.database.records.explore import ExploreSearchEventRecordModel
    with session_scope(database_url) as session:
        outcomes = session.scalars(select(ExploreSearchEventRecordModel.outcome)).all()
    assert sorted(outcomes) == ["allowed", "blocked_capacity" if limit == "global" else
                                "blocked_cooldown" if limit == "cooldown" else "blocked_quota"]
    assert _operation_count(created["runId"], database_url) == 1
    assert get_search_run(created["runId"], database_url=database_url).status == "completed"


@pytest.mark.parametrize("token", [None, "invalid", "valid"])
def test_expansion_requires_and_verifies_turnstile(database_url, monkeypatch, token):
    from app.models.explore_access import ExploreActor, ExploreTier
    from app.services.search.access import policy
    from app.models.security import TurnstileVerificationResult

    monkeypatch.setattr(policy, "TURNSTILE_ENABLED", True)
    monkeypatch.setattr("app.services.search.access.service.resolve_explore_actor", lambda *args, **kwargs: ExploreActor(
        ExploreTier.SUSPICIOUS, "guest_ip", "suspicious-ip"))
    verified = []
    def verify(value, **kwargs):
        verified.append(value)
        return TurnstileVerificationResult(success=value == "valid")
    monkeypatch.setattr(app.state, "verify_turnstile_token", verify)
    created = _completed_run(database_url)
    with TestClient(app) as client:
        response = client.post(f"/api/explore/search-runs/{created['runId']}/expand",
                               headers={"X-Search-Run-Token": created["guestAccessToken"]},
                               json={"turnstileToken": token})
    assert response.status_code == (202 if token == "valid" else 403)
    assert verified == ([] if token is None else [token])
    assert _operation_count(created["runId"], database_url) == (2 if token == "valid" else 1)
    if token != "valid":
        assert response.json()["turnstileRequired"] is True


def test_inaccessible_expansion_does_not_check_turnstile_or_reserve_quota(database_url, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Admission ran before ownership check")
    monkeypatch.setattr("app.services.search.access.service.resolve_explore_actor", unexpected)
    from app.services.search.explore import jobs
    monkeypatch.setattr(jobs, "record_explore_admission", unexpected)
    created = _completed_run(database_url)
    with TestClient(app) as client:
        response = client.post(f"/api/explore/search-runs/{created['runId']}/expand", json={"turnstileToken": "secret"})
    assert response.status_code == 404


def test_unexpandable_run_does_not_consume_quota(database_url, monkeypatch):
    from app.api.routes import explore
    created = seed_search_run(topic_description="topic", owner_user_id=None, database_url=database_url)
    monkeypatch.setattr(explore, "_prepare_explore_search_request",
                        lambda *args, **kwargs: pytest.fail("Admission ran for invalid expansion"))
    from app.services.search.explore import jobs
    monkeypatch.setattr(jobs, "record_explore_admission",
                        lambda *args, **kwargs: pytest.fail("Reserved for invalid expansion"))
    with TestClient(app) as client:
        response = client.post(f"/api/explore/search-runs/{created['runId']}/expand",
                               headers={"X-Search-Run-Token": created["guestAccessToken"]})
    assert response.status_code == 409
    assert _operation_count(created["runId"], database_url) == 1


@pytest.mark.parametrize("actor_kind", ["guest", "owner", "bypass"])
def test_repeated_expansions_schedule_once_and_charge_once(database_url, users, monkeypatch, actor_kind):
    from app.database.records.explore import ExploreSearchEventRecordModel
    from app.services.search.access import policy

    user = users["owner"] if actor_kind != "guest" else None
    created = _completed_run(database_url, user.user_id if user else None)
    session_token = create_authenticated_session(user.user_id, database_url=database_url, ttl_seconds=3600) if user else None
    monkeypatch.setattr(policy, "EXPLORE_GUEST_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(policy, "EXPLORE_USER_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(policy, "SEARCH_QUOTA_BYPASS_USER_EMAILS", (user.email,) if actor_kind == "bypass" else ())
    def expand(_):
        with TestClient(app) as client:
            if session_token:
                client.cookies.set(AUTH_SESSION_COOKIE_NAME, session_token)
            headers = {"X-Search-Run-Token": created["guestAccessToken"]} if not user else {}
            return client.post(f"/api/explore/search-runs/{created['runId']}/expand", headers=headers)
    responses = [expand(index) for index in range(6)]
    assert sorted(response.status_code for response in responses) == [202, 409, 409, 409, 409, 409]
    assert _operation_count(created["runId"], database_url) == 2
    assert get_search_run(created["runId"], database_url=database_url).status == "running"
    with session_scope(database_url) as session:
        outcomes = session.scalars(select(ExploreSearchEventRecordModel.outcome)).all()
    assert outcomes == ["allowed_internal" if actor_kind == "bypass" else "allowed"]


@pytest.mark.parametrize("status", ["completed", "completed_partial"])
def test_expansion_commit_failure_rolls_back_quota_operation_and_run(database_url, monkeypatch, status):
    from types import SimpleNamespace
    from app.database.records.explore import ExploreSearchEventRecordModel
    from app.services.search.explore import jobs

    created = _completed_run(database_url)
    set_search_run_state(created["runId"], status=status, partial=status == "completed_partial",
                      response_payload={"items": [{"itemId": "preserved"}]}, database_url=database_url)
    original = get_search_run(created["runId"], database_url=database_url)
    with session_scope(database_url) as session:
        existing_operation_id = session.scalar(select(SearchRunOperationRecordModel.operation_id))
    with monkeypatch.context() as failure:
        failure.setattr(jobs, "uuid4", lambda: SimpleNamespace(hex=existing_operation_id))
        with TestClient(app) as client:
            response = client.post(f"/api/explore/search-runs/{created['runId']}/expand",
                                   headers={"X-Search-Run-Token": created["guestAccessToken"]})
            assert response.status_code == 409
            assert response.json()["code"] == "persistence_conflict"
    assert get_search_run(created["runId"], database_url=database_url) == original
    assert _operation_count(created["runId"], database_url) == 1
    with session_scope(database_url) as session:
        assert session.scalar(select(func.count()).select_from(ExploreSearchEventRecordModel)) == 0
    with TestClient(app) as client:
        retry = client.post(f"/api/explore/search-runs/{created['runId']}/expand",
                            headers={"X-Search-Run-Token": created["guestAccessToken"]})
    assert retry.status_code == 202
    assert _operation_count(created["runId"], database_url) == 2
    with session_scope(database_url) as session:
        assert session.scalar(select(func.count()).select_from(ExploreSearchEventRecordModel)) == 1


@pytest.mark.parametrize("change", ["owner", "status", "plan"])
def test_expansion_rechecks_run_after_external_verification(database_url, users, monkeypatch, change):
    from app.api.routes import explore
    from app.database.records.explore import ExploreSearchEventRecordModel
    from app.database.records.search_runs import SearchRunRecordModel
    from sqlalchemy import update

    created = _completed_run(database_url, users["owner"].user_id)
    prepare = explore._prepare_explore_search_request
    def change_during_verification(*args, **kwargs):
        admission = prepare(*args, **kwargs)
        values = {"owner_user_id": users["other"].user_id} if change == "owner" else (
            {"status": "running"} if change == "status" else {"execution_state_json": None}
        )
        with session_scope(database_url) as session:
            session.execute(update(SearchRunRecordModel).where(
                SearchRunRecordModel.run_id == created["runId"],
            ).values(**values))
        return admission
    monkeypatch.setattr(explore, "_prepare_explore_search_request", change_during_verification)
    with TestClient(app) as client:
        _sign_in(client, users["owner"], database_url)
        response = client.post(f"/api/explore/search-runs/{created['runId']}/expand")
    assert response.status_code == (404 if change == "owner" else 409)
    assert _operation_count(created["runId"], database_url) == 1
    with session_scope(database_url) as session:
        assert session.scalar(select(func.count()).select_from(ExploreSearchEventRecordModel)) == 0


@pytest.mark.parametrize("change,message", [
    ("missing", "unavailable"),
    ("unversioned", "invalid"),
    ("unsupported", "unsupported"),
    ("corrupt", "invalid"),
])
def test_invalid_execution_blocks_expansion_before_admission(database_url, users, change, message, monkeypatch):
    from app.database.records.explore import ExploreSearchEventRecordModel
    from app.api.routes import explore

    created = _completed_run(database_url, users["owner"].user_id)
    run = get_search_run(created["runId"], database_url=database_url)
    state = dict(run.execution_state)
    if change == "missing":
        state = None
    elif change == "unversioned":
        del state["schemaVersion"]
    elif change == "unsupported":
        state["schemaVersion"] = 99
    else:
        state["executedQueries"] = ["second"]
    with session_scope(database_url) as session:
        record = session.get(SearchRunRecordModel, created["runId"])
        record.execution_state_json = state

    def prepare(*args, **kwargs):
        pytest.fail("Invalid replay state must be rejected before access admission or external verification")

    monkeypatch.setattr(explore, "_prepare_explore_search_request", prepare)
    with TestClient(app) as client:
        _sign_in(client, users["owner"], database_url)
        response = client.post(f"/api/explore/search-runs/{created['runId']}/expand")
    assert response.status_code == 409
    assert message in response.json()["error"]
    assert _operation_count(created["runId"], database_url) == 1
    assert get_search_run(created["runId"], database_url=database_url).execution_state == state
    with session_scope(database_url) as session:
        assert session.scalar(select(func.count()).select_from(ExploreSearchEventRecordModel)) == 0
