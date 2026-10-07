"""Atomic admission and initial scheduling through the public search API."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

from fastapi import Response
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.api.app import app
from app.api.routes import explore
from app.config import AUTH_SESSION_COOKIE_NAME
from app.database.records.explore import ExploreSearchEventRecordModel
from app.database.records.search_runs import SearchRunOperationRecordModel, SearchRunRecordModel
from app.database.session import session_scope
from app.models.explore_access import ExploreActor, ExploreTier
from app.services.auth.service import create_authenticated_session
from app.services.search.access import policy
from app.services.search.explore import jobs
from app.services.security.turnstile import TurnstileVerificationResult
from app.storage.auth.users import create_user
from app.storage.search_runs import get_search_run
from tests.conftest import build_test_database_url, migrate_test_database
from tests.fixtures.search_runs import seed_search_run


@pytest.fixture
def database_url(tmp_path, monkeypatch):
    url = build_test_database_url(tmp_path / "initial-scheduling.sqlite3")
    migrate_test_database(url)
    monkeypatch.setattr(app.state, "database_url", url)
    monkeypatch.setattr(policy, "EXPLORE_PUBLIC_GUEST_SEARCH_ENABLED", True)
    monkeypatch.setattr(policy, "EXPLORE_GUEST_DAILY_LIMIT", 100)
    monkeypatch.setattr(policy, "EXPLORE_USER_DAILY_LIMIT", 100)
    monkeypatch.setattr(policy, "EXPLORE_GLOBAL_DAILY_LIMIT", 100)
    monkeypatch.setattr(policy, "EXPLORE_GUEST_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(policy, "EXPLORE_USER_COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(policy, "SEARCH_QUOTA_BYPASS_USER_EMAILS", ())
    return url


def _session_token(actor_kind, database_url, monkeypatch):
    if actor_kind == "guest":
        return None
    user = create_user(email="owner@example.com", display_name="Owner", database_url=database_url)
    if actor_kind == "bypass":
        monkeypatch.setattr(policy, "SEARCH_QUOTA_BYPASS_USER_EMAILS", (user.email,))
    return create_authenticated_session(user.user_id, Response(), database_url=database_url)


def _counts(database_url):
    with session_scope(database_url) as session:
        return {
            name: session.scalar(select(func.count()).select_from(model))
            for name, model in (
                ("runs", SearchRunRecordModel),
                ("operations", SearchRunOperationRecordModel),
                ("events", ExploreSearchEventRecordModel),
            )
        }


def _post_search(client):
    return client.post("/api/explore/search-runs", json={"topicDescription": "Scientific software"})


@pytest.mark.parametrize("actor_kind", ["guest", "user", "bypass"])
def test_initial_search_commits_matching_admission_run_and_operation(database_url, monkeypatch, actor_kind):
    token = _session_token(actor_kind, database_url, monkeypatch)
    with TestClient(app) as client:
        if token:
            client.cookies.set(AUTH_SESSION_COOKIE_NAME, token)
        response = _post_search(client)
    assert response.status_code == 202
    created = response.json()
    assert created["status"] == "queued"
    assert ("guestAccessToken" in created) == (actor_kind == "guest")
    run = get_search_run(created["runId"], database_url=database_url)
    with session_scope(database_url) as session:
        admission = session.scalars(select(ExploreSearchEventRecordModel)).one()
        operation = session.scalars(select(SearchRunOperationRecordModel)).one()
        assert admission.user_id == run.owner_user_id
        assert admission.topic_hash == run.topic_hash
        assert admission.outcome == ("allowed_internal" if actor_kind == "bypass" else "allowed")
        assert operation.run_id == run.run_id
        assert operation.kind == "initial"
        assert operation.status == run.status == "queued"
    assert _counts(database_url) == {"runs": 1, "operations": 1, "events": 1}


@pytest.mark.parametrize("actor_kind", ["guest", "user", "bypass"])
@pytest.mark.parametrize("failure_stage", ["run_insert", "operation_insert", "commit"])
def test_failed_initial_scheduling_rolls_back_every_write_and_allows_retry(
    database_url, monkeypatch, actor_kind, failure_stage,
):
    token = _session_token(actor_kind, database_url, monkeypatch)
    existing = seed_search_run(topic_description="Preserved existing run", database_url=database_url)
    original = get_search_run(existing["runId"], database_url=database_url)
    with session_scope(database_url) as session:
        existing_operation_id = session.scalar(select(SearchRunOperationRecordModel.operation_id))

    def fail_commit(session):
        if any(isinstance(record, SearchRunOperationRecordModel) for record in session.new):
            # Let every INSERT reach the database, then fail transaction finalization.
            session.flush()
            raise RuntimeError("Injected commit failure")

    with monkeypatch.context() as failure:
        if failure_stage == "commit":
            event.listen(Session, "before_commit", fail_commit)
        else:
            ids = iter([
                existing["runId"] if failure_stage == "run_insert" else uuid4().hex,
                existing_operation_id if failure_stage == "operation_insert" else uuid4().hex,
            ])
            failure.setattr(jobs, "uuid4", lambda: SimpleNamespace(hex=next(ids)))
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                if token:
                    client.cookies.set(AUTH_SESSION_COOKIE_NAME, token)
                response = _post_search(client)
        finally:
            if failure_stage == "commit":
                event.remove(Session, "before_commit", fail_commit)
    assert response.status_code == 500
    assert _counts(database_url) == {"runs": 1, "operations": 1, "events": 0}
    assert get_search_run(existing["runId"], database_url=database_url) == original

    with TestClient(app) as client:
        if token:
            client.cookies.set(AUTH_SESSION_COOKIE_NAME, token)
        retry = _post_search(client)
    assert retry.status_code == 202
    assert retry.json()["runId"] != existing["runId"]
    assert _counts(database_url) == {"runs": 2, "operations": 2, "events": 1}


@pytest.mark.parametrize("limit", ["guest", "user", "global", "cooldown"])
def test_initial_denial_records_outcome_without_scheduling_work(database_url, monkeypatch, limit):
    token = _session_token("user" if limit == "user" else "guest", database_url, monkeypatch)
    with TestClient(app) as client:
        if token:
            client.cookies.set(AUTH_SESSION_COOKIE_NAME, token)
        first = _post_search(client)
        assert first.status_code == 202
        if limit == "guest":
            monkeypatch.setattr(policy, "EXPLORE_GUEST_DAILY_LIMIT", 1)
        elif limit == "user":
            monkeypatch.setattr(policy, "EXPLORE_USER_DAILY_LIMIT", 1)
        elif limit == "global":
            monkeypatch.setattr(policy, "EXPLORE_GLOBAL_DAILY_LIMIT", 1)
        else:
            monkeypatch.setattr(policy, "EXPLORE_GUEST_COOLDOWN_SECONDS", 60)
        denied = _post_search(client)
    assert denied.status_code == (503 if limit == "global" else 429)
    if "retryAfterSeconds" in denied.json():
        assert denied.headers["Retry-After"] == str(denied.json()["retryAfterSeconds"])
    assert "runId" not in denied.json()
    assert "guestAccessToken" not in denied.json()
    assert _counts(database_url) == {"runs": 1, "operations": 1, "events": 2}
    with session_scope(database_url) as session:
        outcomes = session.scalars(select(ExploreSearchEventRecordModel.outcome)).all()
    expected = "blocked_capacity" if limit == "global" else "blocked_cooldown" if limit == "cooldown" else "blocked_quota"
    assert sorted(outcomes) == sorted(["allowed", expected])


@pytest.mark.parametrize("proof", [None, "invalid", "valid"])
def test_initial_turnstile_verification_precedes_transaction_and_scheduling(database_url, monkeypatch, proof):
    from app.database.session import get_engine

    monkeypatch.setattr(policy, "TURNSTILE_ENABLED", True)
    monkeypatch.setattr(explore, "resolve_explore_actor", lambda *args, **kwargs: ExploreActor(
        ExploreTier.SUSPICIOUS, "guest_ip", "suspicious-guest",
    ))
    observed = []

    def record_lock(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE search_access_lock"):
            observed.append("lock")

    def verify(token, **kwargs):
        assert "lock" not in observed, "External verification must run before locking admission"
        observed.append("verification")
        return TurnstileVerificationResult(success=token == "valid")

    monkeypatch.setattr(explore, "verify_turnstile_token", verify)
    engine = get_engine(database_url)
    event.listen(engine, "before_cursor_execute", record_lock)
    try:
        with TestClient(app) as client:
            response = client.post("/api/explore/search-runs", json={
                "topicDescription": "Scientific software", "turnstileToken": proof,
            })
    finally:
        event.remove(engine, "before_cursor_execute", record_lock)
    assert response.status_code == (202 if proof == "valid" else 403)
    assert observed == (["lock"] if proof is None else ["verification"] if proof == "invalid" else ["verification", "lock"])
    scheduled = 1 if proof == "valid" else 0
    assert _counts(database_url) == {"runs": scheduled, "operations": scheduled, "events": 1}


@pytest.mark.parametrize("limit", ["guest", "user", "global", "bypass"])
def test_concurrent_initial_requests_respect_last_slot_and_schedule_only_admitted_work(
    database_url, monkeypatch, limit,
):
    token = _session_token("bypass" if limit == "bypass" else "user" if limit == "user" else "guest",
                           database_url, monkeypatch)
    monkeypatch.setattr(policy, "EXPLORE_GUEST_DAILY_LIMIT", 1 if limit == "guest" else 100)
    monkeypatch.setattr(policy, "EXPLORE_USER_DAILY_LIMIT", 1 if limit in {"user", "bypass"} else 100)
    monkeypatch.setattr(policy, "EXPLORE_GLOBAL_DAILY_LIMIT", 1 if limit in {"global", "bypass"} else 100)
    barrier = Barrier(6, timeout=10)
    prepare = explore._prepare_explore_search_request

    def prepare_together(*args, **kwargs):
        admission = prepare(*args, **kwargs)
        barrier.wait()
        return admission

    monkeypatch.setattr(explore, "_prepare_explore_search_request", prepare_together)

    def create(index):
        with TestClient(app) as client:
            if token:
                client.cookies.set(AUTH_SESSION_COOKIE_NAME, token)
            return client.post("/api/explore/search-runs", json={"topicDescription": f"Topic {index}"},
                               headers={"X-Forwarded-For": f"198.51.100.{index + 1}"} if limit == "global" else {})

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(create, range(6)))
    admitted = 6 if limit == "bypass" else 1
    denied_status = 503 if limit == "global" else 429
    assert sorted(response.status_code for response in responses) == sorted(
        [202] * admitted + [denied_status] * (6 - admitted),
    )
    assert _counts(database_url) == {"runs": admitted, "operations": admitted, "events": 6}
    with session_scope(database_url) as session:
        outcomes = session.scalars(select(ExploreSearchEventRecordModel.outcome)).all()
        run_ids = set(session.scalars(select(SearchRunRecordModel.run_id)).all())
        operation_run_ids = set(session.scalars(select(SearchRunOperationRecordModel.run_id)).all())
    assert run_ids == operation_run_ids == {response.json()["runId"] for response in responses if response.status_code == 202}
    assert outcomes.count("allowed_internal" if limit == "bypass" else "allowed") == admitted
