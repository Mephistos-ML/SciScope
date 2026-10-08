"""Monitoring ownership is enforced by real PostgreSQL locks and transactions."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import event, select, update, text
from sqlalchemy.orm import Session

from app.database.session import database_now, get_engine, session_scope
from app.database.records.monitoring import (
    MonitoringJobLeaseRecordModel,
    MonitoringRunRecordModel,
    RepositoryMonitoringCheckRecordModel,
    RepositoryMonitoringCursorRecordModel,
)
from app.jobs import scan_subscriptions as job
from app.models.monitoring import (
    MonitoringRun,
    RepositoryActivity,
    RepositoryMonitoringCheck,
    MonitoringLeaseLostError,
)
from app.models.repository import Repository
from app.models.signal import Signal
from app.services.feed.service import build_feed_event
from app.storage.monitoring import state
from app.storage.auth.users import create_user
from app.storage.repositories.repositories import upsert_repositories, get_repository
from app.storage.subscriptions.subscriptions import create_subscription
from app.storage.subscriptions.watches import list_subscription_watches_for_user
from app.storage.feed.events import list_feed_events_for_user
from tests.fixtures.database import migrate_test_database
from tests.fixtures.postgres import wait_until_blocked

pytestmark = pytest.mark.postgres


def expire(lease, url):
    with session_scope(url) as session:
        session.execute(
            update(MonitoringJobLeaseRecordModel)
            .where(
                MonitoringJobLeaseRecordModel.job_name == lease.job_name,
            )
            .values(lease_expires_at=database_now(session) - timedelta(seconds=1))
        )


@pytest.fixture
def watched(postgres_url):
    create_user(
        user_id="owner",
        email="owner@example.test",
        display_name="Owner",
        database_url=postgres_url,
    )
    repository = Repository(
        "github:repo:123",
        "github",
        "science/tool",
        "https://github.com/science/tool",
        {},
    )
    upsert_repositories((repository,), database_url=postgres_url)
    create_subscription(
        user_id="owner",
        repository_id=repository.repository_id,
        selected_query=None,
        database_url=postgres_url,
    )
    watch = list_subscription_watches_for_user("owner", database_url=postgres_url)[0]
    signal = Signal(
        source="github",
        kind="release",
        item_id="release-1",
        title="New release",
        url="https://github.com/science/tool/releases/1",
        published_at=None,
        raw_text="Release",
    )
    return repository, build_feed_event(signal, watch), signal


def start(lease, url):
    run = MonitoringRun(lease.holder_id, datetime.now(UTC), None, "running", 0, 0, None)
    state.create_monitoring_run(run, lease=lease, database_url=url)
    return run


@pytest.mark.parametrize("holder", ["old", "replacement"])
def test_superseded_scan_cannot_publish_any_facts_or_release_replacement(
    postgres_url, watched, holder
):
    repository, feed_event, _ = watched
    old = state.acquire_monitoring_job_lease("scan", "old", database_url=postgres_url)
    run = start(old, postgres_url)
    expire(old, postgres_url)
    current = state.acquire_monitoring_job_lease(
        "scan", holder, database_url=postgres_url
    )
    assert current.token != old.token
    assert not state.renew_monitoring_job_lease(old, database_url=postgres_url)
    operations = (
        lambda: state.persist_repository_monitoring_result(
            repository.repository_id,
            (feed_event,),
            {"latest_main_commit_sha": "stale"},
            refreshed_repository=Repository(
                repository.repository_id, "github", "science/stale", repository.url, {}
            ),
            lease=old,
            database_url=postgres_url,
        ),
        lambda: state.record_repository_monitoring_check(
            RepositoryMonitoringCheck(
                repository.repository_id, datetime.now(UTC), "succeeded", None, None
            ),
            run_id=old.holder_id,
            lease=old,
            database_url=postgres_url,
        ),
        lambda: state.finish_monitoring_run(
            old.holder_id,
            status="succeeded",
            scanned_repository_count=1,
            failed_repository_count=0,
            error_summary=None,
            lease=old,
            database_url=postgres_url,
        ),
        lambda: state.create_monitoring_run(run, lease=old, database_url=postgres_url),
    )
    for operation in operations:
        with pytest.raises(MonitoringLeaseLostError):
            operation()
    state.release_monitoring_job_lease(old, database_url=postgres_url)
    with session_scope(postgres_url) as session:
        assert (
            session.get(MonitoringJobLeaseRecordModel, "scan").lease_token
            == current.token
        )
        assert session.get(MonitoringRunRecordModel, "old").status == "running"
        assert session.scalars(select(RepositoryMonitoringCheckRecordModel)).all() == []
    assert (
        get_repository(repository.repository_id, database_url=postgres_url).full_name
        == "science/tool"
    )
    assert (
        state.get_repository_monitoring_cursors(
            repository.repository_id, database_url=postgres_url
        )
        == {}
    )
    assert list_feed_events_for_user("owner", database_url=postgres_url) == []
    state.persist_repository_monitoring_result(
        repository.repository_id,
        (feed_event,),
        {"latest_main_commit_sha": "current"},
        lease=current,
        database_url=postgres_url,
    )
    assert (
        state.get_repository_monitoring_cursors(
            repository.repository_id, database_url=postgres_url
        )["latest_main_commit_sha"]
        == "current"
    )
    assert len(list_feed_events_for_user("owner", database_url=postgres_url)) == 1


def test_expiry_after_flush_rolls_back_feed_profile_and_checkpoint(
    postgres_url, watched
):
    repository, feed_event, _ = watched
    lease = state.acquire_monitoring_job_lease(
        "scan", "owner", database_url=postgres_url
    )

    def expire_during_flush(session, _context):
        if any(
            isinstance(record, RepositoryMonitoringCursorRecordModel)
            for record in session.new
        ):
            session.execute(
                update(MonitoringJobLeaseRecordModel)
                .where(
                    MonitoringJobLeaseRecordModel.job_name == "scan",
                )
                .values(lease_expires_at=database_now(session) - timedelta(seconds=1))
            )

    event.listen(Session, "after_flush", expire_during_flush)
    try:
        with pytest.raises(MonitoringLeaseLostError):
            state.persist_repository_monitoring_result(
                repository.repository_id,
                (feed_event,),
                {"head": "uncommitted"},
                refreshed_repository=Repository(
                    repository.repository_id,
                    "github",
                    "science/uncommitted",
                    repository.url,
                    {},
                ),
                lease=lease,
                database_url=postgres_url,
            )
    finally:
        event.remove(Session, "after_flush", expire_during_flush)
    assert list_feed_events_for_user("owner", database_url=postgres_url) == []
    assert (
        state.get_repository_monitoring_cursors(
            repository.repository_id, database_url=postgres_url
        )
        == {}
    )
    assert (
        get_repository(repository.repository_id, database_url=postgres_url).full_name
        == repository.full_name
    )


@pytest.mark.parametrize("action", ["finish", "renew"])
def test_expiry_is_checked_after_waiting_for_lease_lock(postgres_url, action):
    lease = state.acquire_monitoring_job_lease(
        "scan", "owner", database_url=postgres_url
    )
    start(lease, postgres_url)

    def write():
        if action == "renew":
            return state.renew_monitoring_job_lease(lease, database_url=postgres_url)
        state.finish_monitoring_run(
            "owner",
            status="succeeded",
            scanned_repository_count=0,
            failed_repository_count=0,
            error_summary=None,
            lease=lease,
            database_url=postgres_url,
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        with session_scope(postgres_url) as locking:
            record = locking.scalar(
                select(MonitoringJobLeaseRecordModel).with_for_update()
            )
            future = pool.submit(write)
            with get_engine(postgres_url).connect() as observer:
                wait_until_blocked(observer, "UPDATE monitoring_job_leases")
            record.lease_expires_at = database_now(locking) - timedelta(seconds=1)
        if action == "renew":
            assert future.result(timeout=10) is False
        else:
            with pytest.raises(MonitoringLeaseLostError):
                future.result(timeout=10)
    with session_scope(postgres_url) as session:
        assert session.get(MonitoringRunRecordModel, "owner").status == "running"


def test_release_cannot_delete_a_replacement_committed_during_lock_wait(postgres_url):
    old = state.acquire_monitoring_job_lease("scan", "owner", database_url=postgres_url)
    new_token = uuid4().hex
    with ThreadPoolExecutor(max_workers=1) as pool:
        with session_scope(postgres_url) as locking:
            record = locking.scalar(
                select(MonitoringJobLeaseRecordModel).with_for_update()
            )
            future = pool.submit(
                state.release_monitoring_job_lease, old, database_url=postgres_url
            )
            with get_engine(postgres_url).connect() as observer:
                wait_until_blocked(observer, "DELETE FROM monitoring_job_leases")
            record.lease_token = new_token
        future.result(timeout=10)
    with session_scope(postgres_url) as session:
        assert (
            session.get(MonitoringJobLeaseRecordModel, "scan").lease_token == new_token
        )


@pytest.mark.parametrize("existing", [False, True])
def test_parallel_acquisition_has_one_owner_with_fresh_token(postgres_url, existing):
    old = (
        state.acquire_monitoring_job_lease("scan", "worker", database_url=postgres_url)
        if existing
        else None
    )
    if old:
        expire(old, postgres_url)
    ready = Barrier(4)

    def acquire(_index):
        ready.wait(timeout=5)
        return state.acquire_monitoring_job_lease(
            "scan", "worker", database_url=postgres_url
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        winners = [lease for lease in pool.map(acquire, range(4)) if lease is not None]
    assert len(winners) == 1
    if old:
        assert winners[0].token != old.token


def test_upgrade_of_existing_monitoring_lease_establishes_new_fenced_claim(
    postgres_database_url,
):
    url = postgres_database_url
    migrate_test_database(url, "0015_planner_reasoning_effort")
    with session_scope(url) as session:
        session.execute(
            text(
                "INSERT INTO monitoring_job_leases (job_name, holder_id, lease_expires_at) VALUES ('scan', 'old', clock_timestamp() + interval '1 hour')"
            )
        )
    migrate_test_database(url)
    lease = state.acquire_monitoring_job_lease("scan", "new", database_url=url)
    assert lease is not None
    with session_scope(url) as session:
        assert (
            session.get(MonitoringJobLeaseRecordModel, "scan").lease_token
            == lease.token
        )


def test_heartbeat_renews_during_io_and_takeover_discards_old_results(
    postgres_url, watched, monkeypatch
):
    repository, _, signal = watched
    entered, release, renewed = Event(), Event(), Event()
    renew = job.renew_monitoring_job_lease
    observed = []

    def renewing(lease, **kwargs):
        result = renew(lease, **kwargs)
        if result:
            observed.append(lease)
            renewed.set()
        return result

    monkeypatch.setattr(job, "renew_monitoring_job_lease", renewing)

    class Monitor:
        def load_repository_activity(self, *args, **kwargs):
            entered.set()
            assert release.wait(10)
            return RepositoryActivity((signal,), True, True, "stale-head")

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            job.run_repository_monitoring_scan,
            resolve_monitor=lambda source: Monitor(),
            database_url=postgres_url,
            lease_seconds=3,
        )
        try:
            assert entered.wait(5)
            with session_scope(postgres_url) as session:
                before = session.get(
                    MonitoringJobLeaseRecordModel, job.JOB_NAME
                ).lease_expires_at
            assert renewed.wait(5)
            with session_scope(postgres_url) as session:
                assert (
                    session.get(
                        MonitoringJobLeaseRecordModel, job.JOB_NAME
                    ).lease_expires_at
                    > before
                )
            expire(observed[0], postgres_url)
            current = state.acquire_monitoring_job_lease(
                job.JOB_NAME, "replacement", database_url=postgres_url
            )
            assert current is not None
        finally:
            release.set()
        future.result(timeout=10)
    assert list_feed_events_for_user("owner", database_url=postgres_url) == []
    assert (
        state.get_repository_monitoring_cursors(
            repository.repository_id, database_url=postgres_url
        )
        == {}
    )
    with session_scope(postgres_url) as session:
        assert (
            session.get(MonitoringJobLeaseRecordModel, job.JOB_NAME).lease_token
            == current.token
        )
        assert session.scalars(select(RepositoryMonitoringCheckRecordModel)).all() == []


def test_renewal_cannot_resurrect_a_lease_expiring_between_clock_reads(
    postgres_url, monkeypatch
):
    lease = state.acquire_monitoring_job_lease(
        "scan", "owner", database_url=postgres_url
    )
    with session_scope(postgres_url) as session:
        expires_at = session.get(MonitoringJobLeaseRecordModel, "scan").lease_expires_at
    readings = iter((expires_at - timedelta(seconds=1), expires_at))
    monkeypatch.setattr(state, "database_now", lambda session: next(readings))
    assert not state.renew_monitoring_job_lease(lease, database_url=postgres_url)
    with session_scope(postgres_url) as session:
        assert (
            session.get(MonitoringJobLeaseRecordModel, "scan").lease_expires_at
            == expires_at
        )
