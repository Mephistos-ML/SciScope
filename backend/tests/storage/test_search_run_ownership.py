"""Lease fencing and atomic recovery against the real persistence adapter."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.database.records.search_runs import SearchRunOperationRecordModel
from app.database.session import session_scope
from app.storage import search_runs as storage
from tests.conftest import build_test_database_url, migrate_test_database
from tests.fixtures.search_runs import build_stage_report, seed_search_run


@pytest.fixture
def work(tmp_path, monkeypatch):
    url = build_test_database_url(tmp_path / "ownership.sqlite3")
    migrate_test_database(url)
    clock = [datetime(2026, 10, 7, tzinfo=UTC)]
    monkeypatch.setattr(storage, "_database_now", lambda session: clock[0])
    created = seed_search_run(topic_description="Lease regression", database_url=url)
    operation = storage.claim_next_search_run_operation(holder_id="worker", lease_seconds=60, database_url=url)
    return url, clock, created["runId"], operation


def operation_record(operation, url):
    with session_scope(url) as session:
        return session.get(SearchRunOperationRecordModel, operation.operation_id)


@pytest.mark.parametrize("holder", ["worker", "replacement"])
@pytest.mark.parametrize("write", ["start", "success", "partial", "failure"])
def test_superseded_claim_cannot_write_or_release_replacement(work, holder, write):
    url, clock, run_id, old = work
    storage.start_search_run_operation(old, database_url=url)
    clock[0] += timedelta(seconds=60)
    replacement = storage.claim_next_search_run_operation(holder_id=holder, lease_seconds=60, database_url=url)
    assert replacement.lease_token != old.lease_token
    assert not storage.renew_search_run_operation_lease(old, lease_seconds=60, database_url=url)
    with pytest.raises(storage.SearchRunLeaseLostError):
        if write == "start":
            storage.start_search_run_operation(old, database_url=url)
        else:
            storage.finish_search_run_operation(
                old, status={"success": "completed", "partial": "completed_partial", "failure": "failed"}[write],
                response_payload={"items": ["stale"]}, execution_state={"queries": ["stale"]},
                stage_report=build_stage_report(), error_message="stale failure", database_url=url,
            )
    storage.release_search_run_operation_lease(old, database_url=url)
    assert operation_record(old, url).lease_token == replacement.lease_token
    assert storage.get_search_run(run_id, database_url=url).status == "running"
    assert storage.count_search_run_stages(run_id, database_url=url) == 0
    storage.finish_search_run_operation(
        replacement, status="completed", response_payload={"items": ["current"]},
        execution_state={"queries": ["current"]}, stage_report=build_stage_report(), database_url=url,
    )
    result = storage.get_search_run(run_id, database_url=url)
    assert result.response_payload == {"items": ["current"]}
    assert result.execution_state == {"queries": ["current"]}
    assert storage.count_search_run_stages(run_id, database_url=url) == 1
    assert storage.count_search_run_provider_outcomes(run_id, database_url=url) == 1
    assert storage.count_search_run_ranking_candidates(run_id, database_url=url) == 1
    storage.release_search_run_operation_lease(replacement, database_url=url)
    assert operation_record(old, url).lease_token is None
    assert storage.claim_next_search_run_operation(holder_id="third", lease_seconds=60, database_url=url) is None


def test_expired_owner_cannot_renew_or_finish_even_without_takeover(work):
    url, clock, run_id, operation = work
    clock[0] += timedelta(seconds=60)
    assert not storage.renew_search_run_operation_lease(operation, lease_seconds=60, database_url=url)
    with pytest.raises(storage.SearchRunLeaseLostError):
        storage.finish_search_run_operation(operation, status="failed", database_url=url)
    assert storage.get_search_run(run_id, database_url=url).status == "queued"
    assert operation_record(operation, url).status == "running"


@pytest.mark.parametrize("failure", ["flush_error", "expiry", "commit_error"])
def test_completion_rolls_back_all_facts_and_lifecycle(work, failure):
    url, clock, run_id, operation = work
    storage.start_search_run_operation(operation, database_url=url)

    def interrupt(session, *args):
        if not any(isinstance(record, SearchRunOperationRecordModel) and record.status == "completed"
                   for record in session.identity_map.values()):
            return
        if failure == "expiry":
            clock[0] += timedelta(seconds=60)
        else:
            raise RuntimeError("Injected persistence failure")

    hook = "before_commit" if failure == "commit_error" else "after_flush"
    event.listen(Session, hook, interrupt)
    try:
        with pytest.raises(storage.SearchRunLeaseLostError if failure == "expiry" else RuntimeError):
            storage.finish_search_run_operation(
                operation, status="completed", response_payload={"items": ["uncommitted"]},
                execution_state={"progress": 1}, stage_report=build_stage_report(), database_url=url,
            )
    finally:
        event.remove(Session, hook, interrupt)
    run = storage.get_search_run(run_id, database_url=url)
    assert run.status == "running"
    assert run.response_payload is None and run.execution_state is None
    assert run.completed_at is None
    assert operation_record(operation, url).status == "running"
    assert storage.count_search_run_stages(run_id, database_url=url) == 0
    assert storage.count_search_run_provider_outcomes(run_id, database_url=url) == 0
    assert storage.count_search_run_ranking_candidates(run_id, database_url=url) == 0
    storage.release_search_run_operation_lease(operation, database_url=url)
    retry = storage.claim_next_search_run_operation(holder_id="retry", lease_seconds=60, database_url=url)
    storage.finish_search_run_operation(retry, status="completed", stage_report=build_stage_report(), database_url=url)
    assert storage.get_search_run_stage(run_id, 1, database_url=url) is not None
    assert storage.count_search_run_stages(run_id, database_url=url) == 1


def test_racing_claims_have_only_one_owner(work):
    url, clock, run_id, operation = work
    clock[0] += timedelta(seconds=60)
    ready = Event()

    def claim(index):
        ready.wait(5)
        return storage.claim_next_search_run_operation(holder_id=f"worker-{index}", lease_seconds=60, database_url=url)

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(claim, index) for index in range(6)]
        ready.set()
        claims = [future.result(timeout=10) for future in futures]
    winners = [claim for claim in claims if claim is not None]
    assert len(winners) == 1
    assert winners[0].lease_token != operation.lease_token
    assert operation_record(operation, url).lease_token == winners[0].lease_token


def test_database_clock_is_aware_and_tracks_wall_time(work, monkeypatch):
    url, _, _, _ = work
    monkeypatch.undo()
    before = datetime.now(UTC) - timedelta(milliseconds=2)
    with session_scope(url) as session:
        actual = storage._database_now(session)
    assert before <= actual <= datetime.now(UTC)


@pytest.mark.parametrize("duration", [0, -1])
def test_nonpositive_lease_duration_is_rejected(work, duration):
    url, _, _, operation = work
    with pytest.raises(ValueError):
        storage.claim_next_search_run_operation(holder_id="invalid", lease_seconds=duration, database_url=url)
    with pytest.raises(ValueError):
        storage.renew_search_run_operation_lease(operation, lease_seconds=duration, database_url=url)


def test_lease_cannot_expire_between_validation_and_renewal(work, monkeypatch):
    url, clock, _, operation = work
    readings = iter((clock[0], clock[0] + timedelta(seconds=60)))
    monkeypatch.setattr(storage, "_database_now", lambda session: next(readings))
    assert not storage.renew_search_run_operation_lease(operation, lease_seconds=60, database_url=url)
    assert operation_record(operation, url).lease_expires_at.replace(tzinfo=UTC) == clock[0] + timedelta(seconds=60)
