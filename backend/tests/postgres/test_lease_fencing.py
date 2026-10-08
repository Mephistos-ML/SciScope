"""Expired PostgreSQL owners cannot publish results or release a newer claim."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event

import pytest
from sqlalchemy import select, text, update

from app.database.records.search_runs import SearchRunOperationRecordModel
from app.database.session import get_engine, session_scope
from app.storage import search_runs
from tests.fixtures.search_runs import build_stage_report, seed_search_run
from tests.fixtures.postgres import wait_until_blocked

pytestmark = pytest.mark.postgres


def expire(operation, url):
    with session_scope(url) as session:
        session.execute(update(SearchRunOperationRecordModel).where(
            SearchRunOperationRecordModel.operation_id == operation.operation_id,
        ).values(lease_expires_at=search_runs._database_now(session) - timedelta(seconds=1)))


def operation_record(operation, url):
    with session_scope(url) as session:
        return session.get(SearchRunOperationRecordModel, operation.operation_id)


@pytest.mark.parametrize("holder", ["same-worker", "replacement"])
def test_superseded_owner_cannot_mutate_any_authoritative_result(postgres_url, holder):
    run_id = seed_search_run(topic_description="Lease fencing", database_url=postgres_url)["runId"]
    old = search_runs.claim_next_search_run_operation(holder_id="same-worker", lease_seconds=60, database_url=postgres_url)
    search_runs.start_search_run_operation(old, database_url=postgres_url)
    expire(old, postgres_url)
    current = search_runs.claim_next_search_run_operation(holder_id=holder, lease_seconds=60, database_url=postgres_url)
    assert old.lease_token != current.lease_token
    assert not search_runs.renew_search_run_operation_lease(old, lease_seconds=60, database_url=postgres_url)
    with pytest.raises(search_runs.SearchRunLeaseLostError):
        search_runs.start_search_run_operation(old, database_url=postgres_url)
    for status in ("completed", "completed_partial", "failed"):
        with pytest.raises(search_runs.SearchRunLeaseLostError):
            search_runs.finish_search_run_operation(old, status=status, response_payload={"items": ["stale"]},
                execution_state={"stale": True}, stage_report=build_stage_report(), database_url=postgres_url)
    search_runs.release_search_run_operation_lease(old, database_url=postgres_url)
    assert operation_record(old, postgres_url).lease_token == current.lease_token
    assert search_runs.count_search_run_stages(run_id, database_url=postgres_url) == 0
    search_runs.finish_search_run_operation(current, status="completed", response_payload={"items": ["current"]},
        execution_state={"progress": "current"}, stage_report=build_stage_report(), database_url=postgres_url)
    assert search_runs.get_search_run(run_id, database_url=postgres_url).response_payload == {"items": ["current"]}
    assert search_runs.count_search_run_stages(run_id, database_url=postgres_url) == 1
    assert search_runs.count_search_run_provider_outcomes(run_id, database_url=postgres_url) == 1
    assert search_runs.count_search_run_ranking_candidates(run_id, database_url=postgres_url) == 1


def test_expired_owner_is_rejected_after_waiting_for_operation_lock(postgres_url):
    run_id = seed_search_run(topic_description="Lock wait", database_url=postgres_url)["runId"]
    old = search_runs.claim_next_search_run_operation(holder_id="old", lease_seconds=60, database_url=postgres_url)
    search_runs.start_search_run_operation(old, database_url=postgres_url)
    entered = Event()
    def finish():
        entered.set()
        search_runs.finish_search_run_operation(old, status="completed", response_payload={"items": ["stale"]},
            stage_report=build_stage_report(), database_url=postgres_url)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with session_scope(postgres_url) as locking:
            record = locking.scalar(select(SearchRunOperationRecordModel).where(
                SearchRunOperationRecordModel.operation_id == old.operation_id,
            ).with_for_update())
            future = pool.submit(finish)
            assert entered.wait(5)
            with get_engine(postgres_url).connect() as observer:
                wait_until_blocked(observer, "UPDATE search_run_operations")
            # PostgreSQL releases the lock with the updated expired lease visible.
            record.lease_expires_at = search_runs._database_now(locking) - timedelta(seconds=1)
        with pytest.raises(search_runs.SearchRunLeaseLostError):
            future.result(timeout=10)
    assert search_runs.get_search_run(run_id, database_url=postgres_url).status == "running"
    assert search_runs.count_search_run_stages(run_id, database_url=postgres_url) == 0
    assert search_runs.count_search_run_provider_outcomes(run_id, database_url=postgres_url) == 0
    assert search_runs.count_search_run_ranking_candidates(run_id, database_url=postgres_url) == 0


def test_real_flush_constraint_error_rolls_back_result_report_and_lifecycle(postgres_url):
    from app.models.persistence import PersistenceConflictError
    from dataclasses import replace
    run_id = seed_search_run(topic_description="Atomic finish", database_url=postgres_url)["runId"]
    operation = search_runs.claim_next_search_run_operation(holder_id="worker", lease_seconds=60, database_url=postgres_url)
    search_runs.start_search_run_operation(operation, database_url=postgres_url)
    report = build_stage_report()
    duplicate = replace(report, ranking_candidates=(*report.ranking_candidates, *report.ranking_candidates))
    with pytest.raises(PersistenceConflictError) as failure:
        search_runs.finish_search_run_operation(operation, status="completed", response_payload={"items": ["uncommitted"]},
            execution_state={"uncommitted": True}, stage_report=duplicate, database_url=postgres_url)
    assert failure.value.__cause__.orig.sqlstate == "23505"
    run = search_runs.get_search_run(run_id, database_url=postgres_url)
    assert run.status == "running" and run.response_payload is None and run.execution_state is None
    assert operation_record(operation, postgres_url).status == "running"
    assert search_runs.count_search_run_stages(run_id, database_url=postgres_url) == 0
    assert search_runs.count_search_run_provider_outcomes(run_id, database_url=postgres_url) == 0
    assert search_runs.count_search_run_ranking_candidates(run_id, database_url=postgres_url) == 0
    search_runs.finish_search_run_operation(operation, status="completed", stage_report=report, database_url=postgres_url)
    assert search_runs.count_search_run_stages(run_id, database_url=postgres_url) == 1


def test_lease_clock_advances_inside_the_same_transaction(postgres_url):
    with session_scope(postgres_url) as session:
        transaction_time = session.scalar(text("SELECT CURRENT_TIMESTAMP"))
        before = search_runs._database_now(session)
        session.execute(text("SELECT pg_sleep(0.02)"))
        after = search_runs._database_now(session)
        assert after > before >= transaction_time
