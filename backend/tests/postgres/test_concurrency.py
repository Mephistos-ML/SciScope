"""Admission and queue invariants across independent PostgreSQL connections."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import json
from threading import Barrier, Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update

from app.composition.repositories import build_repository_adapters
from app.composition.search import build_explore_dependencies
from app.database.records.explore import ExploreSearchEventRecordModel
from app.database.records.search_runs import SearchRunOperationRecordModel, SearchRunRecordModel
from app.database.session import get_engine, session_scope
from app.models.explore_access import ExploreActor, ExploreAdmission, ExploreTier
from app.models.persistence import PersistenceConflictError
from app.services.search.access import policy
from app.services.search.access.errors import ExploreAccessDeniedError
from app.services.search.explore import jobs
from app.storage import search_runs
from app.storage.search_admission import explore_admission_transaction
from app.storage.subscriptions.subscriptions import create_subscription, list_subscriptions_for_user
from app.storage.auth.users import create_user
from app.storage.repositories.repositories import upsert_repositories
from app.models.repository import Repository
from tests.fixtures.search_runs import seed_search_run, set_search_run_state
from app.services.search.explore.execution import deserialize_execution
from tests.fixtures.database import BACKEND_ROOT
from tests.fixtures.postgres import wait_until_blocked

pytestmark = pytest.mark.postgres


@pytest.fixture
def dependencies():
    return build_explore_dependencies(repositories=build_repository_adapters())


@pytest.fixture(autouse=True)
def unrestricted_policy(monkeypatch):
    for name, value in {
        "EXPLORE_PUBLIC_GUEST_SEARCH_ENABLED": True, "TURNSTILE_ENABLED": False,
        "EXPLORE_GUEST_DAILY_LIMIT": 100, "EXPLORE_USER_DAILY_LIMIT": 100,
        "EXPLORE_GLOBAL_DAILY_LIMIT": 100, "EXPLORE_GUEST_COOLDOWN_SECONDS": 0,
        "EXPLORE_USER_COOLDOWN_SECONDS": 0,
    }.items():
        monkeypatch.setattr(policy, name, value)


def counts(url):
    with session_scope(url) as session:
        return {name: session.scalar(select(func.count()).select_from(model))
                for name, model in (("runs", SearchRunRecordModel),
                                    ("operations", SearchRunOperationRecordModel),
                                    ("events", ExploreSearchEventRecordModel))}


@pytest.mark.parametrize("limit", ["actor", "global", "cooldown", "bypass"])
def test_concurrent_admission_schedules_only_committed_last_slot(postgres_url, dependencies, monkeypatch, limit):
    if limit in {"actor", "bypass"}:
        monkeypatch.setattr(policy, "EXPLORE_GUEST_DAILY_LIMIT", 1)
    if limit in {"global", "bypass"}:
        monkeypatch.setattr(policy, "EXPLORE_GLOBAL_DAILY_LIMIT", 1)
    if limit == "cooldown":
        monkeypatch.setattr(policy, "EXPLORE_GUEST_COOLDOWN_SECONDS", 60)
    ready = Barrier(6)
    def create(index):
        actor = ExploreActor(ExploreTier.GUEST, "guest_ip", f"guest-{index}" if limit == "global" else "same-guest")
        ready.wait(timeout=10)
        try:
            return jobs.create_explore_search_run(
                topic_description=f"Research {index}", admission=ExploreAdmission(actor, bypass_quota=limit == "bypass"),
                dependencies=dependencies, database_url=postgres_url,
            )
        except ExploreAccessDeniedError as exc:
            return exc.decision
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(create, range(6)))
    winners = [result for result in results if isinstance(result, dict)]
    allowed_count = 6 if limit == "bypass" else 1
    assert len(winners) == allowed_count
    assert counts(postgres_url) == {"runs": allowed_count, "operations": allowed_count, "events": 6}
    with session_scope(postgres_url) as session:
        runs = set(session.scalars(select(SearchRunRecordModel.run_id)))
        operations = set(session.scalars(select(SearchRunOperationRecordModel.run_id)))
        outcomes = list(session.scalars(select(ExploreSearchEventRecordModel.outcome)))
    assert runs == operations == {winner["runId"] for winner in winners}
    assert outcomes.count("allowed_internal" if limit == "bypass" else "allowed") == allowed_count


def test_admission_reads_usage_after_a_real_row_lock_wait(postgres_url, dependencies, monkeypatch):
    monkeypatch.setattr(policy, "EXPLORE_GUEST_DAILY_LIMIT", 1)
    actor = ExploreActor(ExploreTier.GUEST, "guest_ip", "waiting-guest")
    entered = Event()
    def queued():
        entered.set()
        return jobs.create_explore_search_run(topic_description="Waiting request", admission=ExploreAdmission(actor),
                                             dependencies=dependencies, database_url=postgres_url)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with explore_admission_transaction(database_url=postgres_url) as store:
            # Commit a preceding allowed event while the contender waits on the lock.
            store.record_event(user_id=None, subject_type="guest_ip", subject_key="waiting-guest",
                               ip_hash=None, topic_hash="earlier", outcome="allowed", created_at=datetime.now(UTC))
            future = pool.submit(queued)
            assert entered.wait(5)
            with get_engine(postgres_url).connect() as observer:
                # The statement is already waiting at the PostgreSQL lock boundary.
                wait_until_blocked(observer, "UPDATE search_access_lock")
        with pytest.raises(ExploreAccessDeniedError):
            future.result(timeout=10)
    assert counts(postgres_url) == {"runs": 0, "operations": 0, "events": 2}


@pytest.mark.parametrize("failure", ["run", "operation"])
def test_constraint_failure_rolls_back_admission_and_scheduling(postgres_url, dependencies, monkeypatch, failure):
    existing = seed_search_run(topic_description="Preserved", database_url=postgres_url)
    with session_scope(postgres_url) as session:
        operation_id = session.scalar(select(SearchRunOperationRecordModel.operation_id))
    ids = iter([existing["runId"] if failure == "run" else uuid4().hex,
                operation_id if failure == "operation" else uuid4().hex])
    with monkeypatch.context() as patched:
        patched.setattr(jobs, "uuid4", lambda: SimpleNamespace(hex=next(ids)))
        with pytest.raises(PersistenceConflictError):
            jobs.create_explore_search_run(topic_description="Rolled back", dependencies=dependencies,
                admission=ExploreAdmission(ExploreActor(ExploreTier.GUEST, "guest_ip", "guest")), database_url=postgres_url)
    assert counts(postgres_url) == {"runs": 1, "operations": 1, "events": 0}
    jobs.create_explore_search_run(topic_description="Retry", dependencies=dependencies,
        admission=ExploreAdmission(ExploreActor(ExploreTier.GUEST, "guest_ip", "guest")), database_url=postgres_url)
    assert counts(postgres_url) == {"runs": 2, "operations": 2, "events": 1}


def test_parallel_expansions_queue_exactly_one_operation(postgres_url):
    created = seed_search_run(topic_description="Expandable", database_url=postgres_url)
    run_id = created["runId"]
    state = json.loads((BACKEND_ROOT / "tests/fixtures/explore_execution_v1.json").read_text())
    # The fixture must have a genuine pending query; no fabricated run status alone.
    assert deserialize_execution(state).pending_queries
    set_search_run_state(run_id, status="completed", execution_state=state, database_url=postgres_url)
    with session_scope(postgres_url) as session:
        session.execute(update(SearchRunOperationRecordModel).values(status="completed"))
    ready = Barrier(4)
    def prepare(topic):
        ready.wait(timeout=10)
        return ExploreAdmission(ExploreActor(ExploreTier.GUEST, "guest_ip", "same-guest"), bypass_quota=True)
    def expand(_):
        try:
            return jobs.expand_explore_search_run(run_id, prepare_admission=prepare, viewer_user_id=None,
                guest_access_token=created["guestAccessToken"], database_url=postgres_url)
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(expand, range(4)))
    assert sum(result is not None for result in results) == 1
    assert counts(postgres_url) == {"runs": 1, "operations": 2, "events": 1}
    assert search_runs.get_search_run(run_id, database_url=postgres_url).execution_state == state


@pytest.mark.parametrize("state", ["queued", "expired"])
def test_parallel_workers_claim_work_without_duplicate_owners(postgres_url, state):
    count = 6 if state == "queued" else 1
    seeded = [seed_search_run(topic_description=f"Research {n}", database_url=postgres_url) for n in range(count)]
    old = None
    if state == "expired":
        old = search_runs.claim_next_search_run_operation(holder_id="old", lease_seconds=60, database_url=postgres_url)
        with session_scope(postgres_url) as session:
            session.execute(update(SearchRunOperationRecordModel).where(
                SearchRunOperationRecordModel.operation_id == old.operation_id,
            ).values(lease_expires_at=search_runs.database_now(session) - timedelta(seconds=1)))
    ready = Barrier(6)
    def claim(index):
        ready.wait(timeout=10)
        return search_runs.claim_next_search_run_operation(holder_id=f"worker-{index}", lease_seconds=60, database_url=postgres_url)
    with ThreadPoolExecutor(max_workers=6) as pool:
        claimed = [operation for operation in pool.map(claim, range(6)) if operation is not None]
    assert len(claimed) == count
    assert {operation.run_id for operation in claimed} == {run["runId"] for run in seeded}
    assert len({operation.lease_token for operation in claimed}) == count
    if old is not None:
        assert claimed[0].lease_token != old.lease_token
        with session_scope(postgres_url) as session:
            assert session.get(SearchRunOperationRecordModel, old.operation_id).lease_token == claimed[0].lease_token
    assert search_runs.claim_next_search_run_operation(holder_id="extra", lease_seconds=60, database_url=postgres_url) is None


def test_locked_queue_head_does_not_block_other_ready_work(postgres_url):
    first = seed_search_run(topic_description="Locked", database_url=postgres_url)
    second = seed_search_run(topic_description="Available", database_url=postgres_url)
    with session_scope(postgres_url) as locked:
        locked.scalar(select(SearchRunOperationRecordModel).where(
            SearchRunOperationRecordModel.run_id == first["runId"],
        ).with_for_update())
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(search_runs.claim_next_search_run_operation,
                holder_id="worker", lease_seconds=60, database_url=postgres_url)
            try:
                claimed = future.result(timeout=3)
                assert claimed.run_id == second["runId"]
            finally:
                # Always unblock a failing implementation before joining its thread.
                locked.rollback()
    next_claim = search_runs.claim_next_search_run_operation(holder_id="next", lease_seconds=60, database_url=postgres_url)
    assert next_claim.run_id == first["runId"]


def test_concurrent_watch_creation_converges_without_swallowing_other_unique_conflicts(postgres_url, monkeypatch):
    create_user(user_id="owner", email="owner@example.test", display_name="Owner", database_url=postgres_url)
    repository = Repository("github:repo:123", "github", "science/tool", "https://github.com/science/tool", {})
    upsert_repositories((repository,), database_url=postgres_url)
    ready = Barrier(4)
    def subscribe(query):
        ready.wait(timeout=10)
        return create_subscription(user_id="owner", repository_id=repository.repository_id,
                                   selected_query=query, database_url=postgres_url)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(subscribe, ("first", "second", "third", "fourth")))
    assert all(result == results[0] for result in results)
    assert list_subscriptions_for_user("owner", database_url=postgres_url) == [results[0]]
    import app.storage.subscriptions.subscriptions as subscriptions
    monkeypatch.setattr(subscriptions.uuid, "uuid4", lambda: SimpleNamespace(hex=results[0].subscription_id.removeprefix("sub_")))
    with pytest.raises(PersistenceConflictError) as failure:
        create_subscription(user_id="other-owner", repository_id=repository.repository_id,
                            selected_query=None, database_url=postgres_url)
    assert failure.value.__cause__.orig.sqlstate == "23505"
    assert list_subscriptions_for_user("owner", database_url=postgres_url) == [results[0]]
