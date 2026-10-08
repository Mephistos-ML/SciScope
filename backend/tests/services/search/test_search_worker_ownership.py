"""Recovery and cancellation at worker and application IO boundaries."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import uuid4

import pytest

from app.composition.repositories import build_repository_adapters
from app.composition.search import build_explore_dependencies

from app.database.records.search_runs import SearchRunRecordModel
from app.database.session import session_scope
from app.jobs import process_search_runs as worker
from app.models.ai import AiSearchPlan
from app.models.search_run import SearchRunOperation, SearchStageReport
from app.services.search.explore import jobs
from app.services.search.explore.execution import ExploreSearchExecution, serialize_execution
from app.services.search.retrieval.models import RetrievedCandidates
from app.storage import search_runs as storage
from tests.fixtures.database import build_test_database_url, migrate_test_database
from tests.fixtures.search_runs import seed_search_run


@pytest.fixture
def work(tmp_path, monkeypatch):
    url = build_test_database_url(tmp_path / "worker-ownership.sqlite3")
    migrate_test_database(url)
    clock = [datetime(2026, 10, 7, tzinfo=UTC)]
    monkeypatch.setattr(storage, "_database_now", lambda session: clock[0])
    created = seed_search_run(topic_description="Recovery regression", database_url=url)
    return url, clock, created["runId"]


def execution(queries):
    return ExploreSearchExecution(AiSearchPlan("ready", ("first", "second")), queries, RetrievedCandidates((), (), 0))


def report(query):
    return SearchStageReport((query,), 0, 0, 0, {}, (), ())


def claim(url):
    return storage.claim_next_search_run_operation(holder_id="same-worker", lease_seconds=60, database_url=url)


def test_callbacks_do_not_advance_durable_progress_before_commit(work, monkeypatch):
    url, _, run_id = work
    operation = claim(url)

    def run(**kwargs):
        kwargs["execution_callback"](execution(("first",)))
        kwargs["stage_report_callback"](report("first"))
        stored = storage.get_search_run(run_id, database_url=url)
        assert stored.execution_state is None
        assert storage.count_search_run_stages(run_id, database_url=url) == 0
        return {"items": [], "canExpand": True}

    monkeypatch.setattr(jobs, "run_explore_search", run)
    jobs.execute_search_run_operation(
        operation,
        ensure_lease=lambda: None,
        database_url=url,
        dependencies=build_explore_dependencies(repositories=build_repository_adapters()),
    )
    stored = storage.get_search_run(run_id, database_url=url)
    assert stored.status == "completed"
    assert stored.execution_state == serialize_execution(execution(("first",)))
    assert storage.count_search_run_stages(run_id, database_url=url) == 1


def test_crashed_expansion_replays_same_query_and_stage(work, monkeypatch):
    url, _, run_id = work
    initial = claim(url)
    storage.finish_search_run_operation(
        initial, status="completed", execution_state=serialize_execution(execution(("first",))),
        response_payload={"items": ["previous"]}, stage_report=report("first"), database_url=url,
    )
    with session_scope(url) as session:
        run = session.get(SearchRunRecordModel, run_id)
        run.status = "running"
        run.completed_at = None
        storage.write_search_run_operation(session, SearchRunOperation(
            uuid4().hex, run_id, "expansion", "queued", datetime.now(UTC),
        ))
    first_attempt = claim(url)
    attempts = []

    def expand(**kwargs):
        attempts.append(kwargs["execution"].pending_queries[0])
        kwargs["execution_callback"](execution(("first", "second")))
        kwargs["stage_report_callback"](report("second"))
        if len(attempts) == 1:
            raise KeyboardInterrupt("Simulated process crash")
        return {"items": ["expanded"], "canExpand": False}

    monkeypatch.setattr(jobs, "expand_explore_search", expand)
    with pytest.raises(KeyboardInterrupt):
        jobs.execute_search_run_operation(
            first_attempt,
            ensure_lease=lambda: None,
            database_url=url,
            dependencies=build_explore_dependencies(repositories=build_repository_adapters()),
        )
    baseline = storage.get_search_run(run_id, database_url=url)
    assert baseline.execution_state == serialize_execution(execution(("first",)))
    assert baseline.response_payload == {"items": ["previous"]}
    assert storage.count_search_run_stages(run_id, database_url=url) == 1
    storage.release_search_run_operation_lease(first_attempt, database_url=url)
    retry = claim(url)
    jobs.execute_search_run_operation(
        retry,
        ensure_lease=lambda: None,
        database_url=url,
        dependencies=build_explore_dependencies(repositories=build_repository_adapters()),
    )
    assert attempts == ["second", "second"]
    assert storage.count_search_run_stages(run_id, database_url=url) == 2
    assert storage.get_search_run_stage(run_id, 2, database_url=url).operation_id == retry.operation_id
    assert storage.get_search_run(run_id, database_url=url).response_payload == {"items": ["expanded"], "canExpand": False}


def test_delayed_old_worker_cannot_overwrite_completed_takeover(work, monkeypatch):
    url, clock, run_id = work
    old = claim(url)
    entered = Event()
    resumed = Event()
    calls = []

    def run(**kwargs):
        calls.append(len(calls))
        if len(calls) == 1:
            entered.set()
            assert resumed.wait(10)
            payload = {"items": ["old"]}
        else:
            payload = {"items": ["new"]}
        kwargs["execution_callback"](execution(("first",)))
        kwargs["stage_report_callback"](report("first"))
        return payload

    monkeypatch.setattr(jobs, "run_explore_search", run)
    with ThreadPoolExecutor(max_workers=1) as executor:
        delayed = executor.submit(
            jobs.execute_search_run_operation,
            old,
            ensure_lease=lambda: None,
            database_url=url,
            dependencies=build_explore_dependencies(repositories=build_repository_adapters()),
        )
        try:
            assert entered.wait(10)
            clock[0] += timedelta(seconds=60)
            replacement = claim(url)
            jobs.execute_search_run_operation(
                replacement,
                ensure_lease=lambda: None,
                database_url=url,
                dependencies=build_explore_dependencies(repositories=build_repository_adapters()),
            )
        finally:
            resumed.set()
        with pytest.raises(storage.SearchRunLeaseLostError):
            delayed.result(timeout=10)
    assert storage.get_search_run(run_id, database_url=url).response_payload == {"items": ["new"]}
    assert storage.count_search_run_stages(run_id, database_url=url) == 1


@pytest.mark.parametrize("failure", ["lost", "database_error"])
def test_failed_heartbeat_signals_cancellation(work, monkeypatch, failure):
    url, _, _ = work
    operation = claim(url)
    lost = Event()

    class StopAfterOneRenewal(Event):
        calls = 0

        def wait(self, timeout=None):
            self.calls += 1
            return self.calls > 1

    def renew(*args, **kwargs):
        if failure == "database_error":
            raise RuntimeError("Database unavailable")
        return False

    monkeypatch.setattr(worker, "renew_search_run_operation_lease", renew)
    worker._renew_lease_until_finished(
        operation=operation, lease_lost=lost, database_url=url, lease_seconds=60, stop=StopAfterOneRenewal(),
    )
    assert lost.is_set()


def test_worker_discards_cancelled_attempt_without_marking_failed(work, monkeypatch):
    url, _, run_id = work

    def heartbeat(**kwargs):
        kwargs["lease_lost"].set()

    def external_search(**kwargs):
        pytest.fail("Cancelled attempt must not start external work")

    monkeypatch.setattr(worker, "_renew_lease_until_finished", heartbeat)
    monkeypatch.setattr(jobs, "run_explore_search", external_search)
    assert worker.process_next_search_run_operation(
        worker_id="worker",
        database_url=url,
        dependencies=build_explore_dependencies(repositories=build_repository_adapters()),
    )
    assert storage.get_search_run(run_id, database_url=url).status == "queued"
    retry = claim(url)
    assert retry is not None and retry.lease_token is not None


@pytest.mark.parametrize("change,code", [
    ("missing", "execution_state_missing"),
    ("unversioned", "execution_state_invalid"),
    ("unsupported", "execution_state_unsupported"),
    ("corrupt", "execution_state_invalid"),
])
def test_worker_reports_invalid_replay_state_without_external_work_or_data_loss(work, monkeypatch, change, code):
    url, _, run_id = work
    initial = claim(url)
    storage.finish_search_run_operation(
        initial, status="completed", execution_state=serialize_execution(execution(("first",))),
        response_payload={"items": ["previous"]}, stage_report=report("first"), database_url=url,
    )
    with session_scope(url) as session:
        run = session.get(SearchRunRecordModel, run_id)
        state = dict(run.execution_state_json)
        if change == "missing":
            state = None
        elif change == "unversioned":
            del state["schemaVersion"]
        elif change == "unsupported":
            state["schemaVersion"] = 99
        else:
            state["executedQueries"] = ["second"]
        run.execution_state_json = state
        run.status = "running"
        storage.write_search_run_operation(session, SearchRunOperation(
            uuid4().hex, run_id, "expansion", "queued", datetime.now(UTC),
        ))

    def expand(**kwargs):
        pytest.fail("Invalid state must not trigger provider IO")

    monkeypatch.setattr(jobs, "expand_explore_search", expand)
    operation = claim(url)
    jobs.execute_search_run_operation(
        operation,
        ensure_lease=lambda: None,
        database_url=url,
        dependencies=build_explore_dependencies(repositories=build_repository_adapters()),
    )
    run = storage.get_search_run(run_id, database_url=url)
    assert run.status == "failed" and run.error_code == code
    assert run.response_payload == {"items": ["previous"]}
    assert run.execution_state == state
    assert storage.count_search_run_stages(run_id, database_url=url) == 1
    with session_scope(url) as session:
        from app.database.records.search_runs import SearchRunOperationRecordModel
        record = session.get(SearchRunOperationRecordModel, operation.operation_id)
        assert record.status == "failed" and record.error_code == code


def test_invalid_generated_progress_is_failed_without_publishing_it(work, monkeypatch):
    url, _, run_id = work

    def run(**kwargs):
        invalid = replace(execution(("first",)), executed_queries=("second",))
        kwargs["execution_callback"](invalid)
        pytest.fail("Invalid progress must stop execution")

    monkeypatch.setattr(jobs, "run_explore_search", run)
    operation = claim(url)
    jobs.execute_search_run_operation(
        operation,
        ensure_lease=lambda: None,
        database_url=url,
        dependencies=build_explore_dependencies(repositories=build_repository_adapters()),
    )
    stored = storage.get_search_run(run_id, database_url=url)
    assert stored.status == "failed" and stored.error_code == "execution_state_invalid"
    assert stored.execution_state is None
    assert stored.response_payload is None
    assert storage.count_search_run_stages(run_id, database_url=url) == 0


def test_required_persistence_outage_preserves_work_for_retry(work, monkeypatch):
    from app.models.persistence import PersistenceUnavailableError
    url, _, run_id = work
    operation = claim(url)
    def unavailable(**kwargs):
        raise PersistenceUnavailableError("Persistence is temporarily unavailable.")
    monkeypatch.setattr(jobs, "run_explore_search", unavailable)
    with pytest.raises(PersistenceUnavailableError):
        jobs.execute_search_run_operation(operation, ensure_lease=lambda: None, database_url=url, dependencies=build_explore_dependencies(repositories=build_repository_adapters()))
    stored = storage.get_search_run(run_id, database_url=url)
    assert stored.status == "running"
    assert stored.error_code is None
    assert stored.execution_state is None
    assert storage.count_search_run_stages(run_id, database_url=url) == 0
    monkeypatch.setattr(jobs, "run_explore_search", lambda **kwargs: {"items": []})
    jobs.execute_search_run_operation(operation, ensure_lease=lambda: None, database_url=url, dependencies=build_explore_dependencies(repositories=build_repository_adapters()))
    assert storage.get_search_run(run_id, database_url=url).status == "completed"
