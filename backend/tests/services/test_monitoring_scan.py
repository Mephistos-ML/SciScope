"""Tests for the stateless repository monitoring scan use case."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from tests.conftest import build_test_database_url, migrate_test_database
from app.database.records.monitoring import (
    MonitoringRunRecordModel,
    RepositoryMonitoringCheckRecordModel,
)
from app.database.session import session_scope
from app.models.repository import Repository
from app.models.signal import Signal
from app.services.monitoring import scan
from app.sources.common import RepositoryActivity
from app.sources.common import RepositorySourceError
from app.storage import auth as auth_storage
from app.storage.feed import list_feed_events_for_user
from app.storage.monitoring.state import (
    acquire_monitoring_job_lease,
    get_repository_monitoring_cursors,
    release_monitoring_job_lease,
)
from app.storage.repositories import upsert_repositories
from app.storage.subscriptions import create_subscription
from app.storage.subscriptions import SubscriptionWatchRecord


def test_scan_backfills_new_repository_since_earliest_subscription(monkeypatch) -> None:
    repository = _repository()
    cursor_updates: list[tuple[str, dict[str, str]]] = []
    signal = _signal("release-1", datetime(2026, 8, 2, 12, tzinfo=UTC))
    events = []
    monitor = _Monitor(lambda *_args, **_kwargs: RepositoryActivity(signals=(signal,), releases_complete=True, commits_complete=True))
    _configure_scan(
        monkeypatch,
        subscriptions=(_watch("sub_one", repository),),
        events=events,
    )
    resolve_monitor = lambda _source: monitor
    monkeypatch.setattr(
        scan,
        "persist_repository_monitoring_result",
        lambda repository_id, new_events, values, **_kwargs: (
            events.extend(new_events), cursor_updates.append((repository_id, values))
        ),
    )

    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url="sqlite://")

    assert len(monitor.calls) == 1
    assert monitor.call_kwargs == [
        {
            "release_started_after": datetime(2026, 8, 1, 12, tzinfo=UTC),
            "commit_started_after": datetime(2026, 8, 1, 12, tzinfo=UTC),
            "commit_after_sha": None,
        }
    ]
    assert [event.subscription_id for event in events] == ["sub_one"]
    assert len(cursor_updates) == 1
    repository_id, values = cursor_updates[0]
    assert repository_id == repository.repository_id
    assert values == {
        scan.REPOSITORY_RELEASE_CHECKPOINT_KEY: signal.published_at.isoformat(),
        scan.REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY: "2026-08-01T12:00:00+00:00",
    }


def test_scan_loads_each_repository_once_and_fans_out_events(monkeypatch) -> None:
    repository = _repository()
    watches = (_watch("sub_one", repository), _watch("sub_two", repository))
    signal = _signal("release-1", datetime(2026, 9, 1, 12, tzinfo=UTC))
    monitor = _Monitor(lambda *_args, **_kwargs: RepositoryActivity(signals=(signal,), releases_complete=True, commits_complete=True))
    events = []
    finished_runs = []
    _configure_scan(
        monkeypatch,
        subscriptions=watches,
        cursors={
            repository.repository_id: {
                scan.REPOSITORY_RELEASE_CHECKPOINT_KEY: "2026-08-30T12:00:00+00:00",
                scan.REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY: "2026-08-30T12:00:00+00:00",
            }
        },
        events=events,
        finished_runs=finished_runs,
    )
    resolve_monitor = lambda _source: monitor

    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url="sqlite://")

    assert len(monitor.calls) == 1
    assert {event.subscription_id for event in events} == {"sub_one", "sub_two"}
    assert finished_runs[-1]["status"] == "succeeded"
    assert finished_runs[-1]["scanned_repository_count"] == 1
    assert finished_runs[-1]["failed_repository_count"] == 0


def test_scan_continues_after_one_repository_fails(monkeypatch) -> None:
    broken_repository = _repository("github:repo:broken", "example/broken")
    healthy_repository = _repository("github:repo:healthy", "example/healthy")
    healthy_signal = _signal("release-1", datetime(2026, 9, 1, 12, tzinfo=UTC))
    checks = []
    finished_runs = []
    _configure_scan(
        monkeypatch,
        subscriptions=(
            _watch("sub_broken", broken_repository),
            _watch("sub_healthy", healthy_repository),
        ),
        cursors={
            repository.repository_id: _cursors()
            for repository in (broken_repository, healthy_repository)
        },
        checks=checks,
        finished_runs=finished_runs,
    )
    def resolve_monitor(_source):
        def load(repository, **_kwargs):
            if repository.full_name == "example/broken":
                raise RuntimeError("provider unavailable")
            return RepositoryActivity(
                signals=(healthy_signal,), releases_complete=True, commits_complete=True,
            )
        return _Monitor(load)

    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url="sqlite://")

    assert {check.status for check in checks} == {"failed", "succeeded"}
    assert finished_runs[-1]["status"] == "partial"
    assert finished_runs[-1]["scanned_repository_count"] == 2
    assert finished_runs[-1]["failed_repository_count"] == 1


def test_scan_skips_when_another_run_holds_the_lease(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(scan, "acquire_monitoring_job_lease", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        scan,
        "list_all_subscription_watches",
        lambda **_kwargs: calls.append("listed") or [],
    )

    scan.run_repository_monitoring_scan(
        resolve_monitor=lambda _source: pytest.fail("Adapter resolved despite held lease"),
        database_url="sqlite://",
    )

    assert calls == []


def test_scan_records_classified_provider_failure(monkeypatch) -> None:
    repository = _repository()
    checks = []
    _configure_scan(
        monkeypatch,
        subscriptions=(_watch("sub_one", repository),),
        cursors={repository.repository_id: _cursors()},
        checks=checks,
    )
    resolve_monitor = lambda _source: _Monitor(
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RepositorySourceError(
                    source="github",
                    status="rate_limited",
                    public_message="GitHub is temporarily rate limited.",
                )
            )
        )

    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url="sqlite://")

    assert checks[0].status == "failed"
    assert checks[0].error_code == "rate_limited"
    assert checks[0].error_message == "GitHub is temporarily rate limited."


def test_scan_refreshes_repository_profile_after_provider_redirect(monkeypatch) -> None:
    repository = _repository()
    refreshed_repositories = []
    monitor = _Monitor(
        lambda *_args, **_kwargs: RepositoryActivity(signals=(), releases_complete=True, commits_complete=True, redirected=True),
        refreshed_name="example/renamed-repository",
    )
    _configure_scan(
        monkeypatch,
        subscriptions=(_watch("sub_one", repository),),
        cursors={repository.repository_id: _cursors()},
    )
    resolve_monitor = lambda _source: monitor
    monkeypatch.setattr(
        scan,
        "upsert_repositories",
        lambda repositories, **_kwargs: refreshed_repositories.extend(repositories),
    )

    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url="sqlite://")

    assert [repository.full_name for repository in refreshed_repositories] == [
        "example/renamed-repository"
    ]


def test_monitoring_lease_allows_only_one_holder(tmp_path) -> None:
    database_url = build_test_database_url(tmp_path / "monitoring-lease.sqlite3")
    migrate_test_database(database_url)

    assert acquire_monitoring_job_lease("scan", "run_one", database_url=database_url)
    assert not acquire_monitoring_job_lease("scan", "run_two", database_url=database_url)

    release_monitoring_job_lease("scan", "run_one", database_url=database_url)

    assert acquire_monitoring_job_lease("scan", "run_two", database_url=database_url)


def test_scan_persists_baseline_events_cursors_and_health_facts(tmp_path, monkeypatch) -> None:
    database_url = build_test_database_url(tmp_path / "monitoring-scan.sqlite3")
    migrate_test_database(database_url)
    repository = _repository()
    user = auth_storage.create_user(
        user_id="user_monitoring",
        email="monitoring@example.com",
        display_name="Monitoring User",
        database_url=database_url,
    )
    upsert_repositories((repository,), database_url=database_url)
    subscription = create_subscription(
        user_id=user.user_id,
        repository_id=repository.repository_id,
        selected_query="repository monitoring",
        database_url=database_url,
    )
    signals: list[Signal] = []
    monitor = _Monitor(
        lambda *_args, **_kwargs: RepositoryActivity(signals=tuple(signals), releases_complete=True, commits_complete=True)
    )
    resolve_monitor = lambda _source: monitor

    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)

    baseline_cursors = get_repository_monitoring_cursors(
        repository.repository_id,
        database_url=database_url,
    )
    assert len(monitor.calls) == 1
    assert set(baseline_cursors) == {
        scan.REPOSITORY_RELEASE_CHECKPOINT_KEY,
        scan.REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY,
    }

    published_at = datetime.now(UTC) + timedelta(minutes=1)
    signals.append(_signal("release-1", published_at))

    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)

    events = list_feed_events_for_user(user.user_id, database_url=database_url)
    cursors = get_repository_monitoring_cursors(
        repository.repository_id,
        database_url=database_url,
    )
    with session_scope(database_url) as session:
        runs = session.scalars(select(MonitoringRunRecordModel)).all()
        checks = session.scalars(select(RepositoryMonitoringCheckRecordModel)).all()

    assert [event.subscription_id for event in events] == [subscription.subscription_id]
    assert cursors[scan.REPOSITORY_RELEASE_CHECKPOINT_KEY] == published_at.isoformat()
    assert len(runs) == 2
    assert {run.status for run in runs} == {"succeeded"}
    assert len(checks) == 2
    assert {check.status for check in checks} == {"succeeded"}


def _configure_scan(
    monkeypatch,
    *,
    subscriptions: tuple[SubscriptionWatchRecord, ...],
    cursors: dict[str, dict[str, str]] | None = None,
    events: list | None = None,
    checks: list | None = None,
    finished_runs: list | None = None,
) -> None:
    monkeypatch.setattr(scan, "acquire_monitoring_job_lease", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(scan, "release_monitoring_job_lease", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scan, "create_monitoring_run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(scan, "list_all_subscription_watches", lambda **_kwargs: subscriptions)
    monkeypatch.setattr(
        scan,
        "get_repository_monitoring_cursors",
        lambda repository_id, **_kwargs: (cursors or {}).get(repository_id, {}),
    )
    monkeypatch.setattr(
        scan,
        "persist_repository_monitoring_result",
        lambda _repository_id, new_events, _values, **_kwargs: events.extend(new_events) if events is not None else None,
    )
    monkeypatch.setattr(
        scan,
        "record_repository_monitoring_check",
        lambda check, **_kwargs: checks.append(check) if checks is not None else None,
    )
    monkeypatch.setattr(
        scan,
        "finish_monitoring_run",
        lambda _run_id, **kwargs: finished_runs.append(kwargs) if finished_runs is not None else None,
    )


def _repository(repository_id: str = "github:repo:123", full_name: str = "example/repository") -> Repository:
    return Repository(
        repository_id=repository_id,
        source="github",
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        provider_repository_id=repository_id.rsplit(":", maxsplit=1)[-1],
    )


def _watch(subscription_id: str, repository: Repository) -> SubscriptionWatchRecord:
    return SubscriptionWatchRecord(
        subscription_id=subscription_id,
        user_id=f"user_{subscription_id}",
        repository=repository,
        selected_query=None,
        created_at="2026-08-01T12:00:00+00:00",
    )


def _signal(item_id: str, published_at: datetime) -> Signal:
    return Signal(
        source="github",
        kind="release",
        item_id=item_id,
        title="Release",
        url="https://github.com/example/repository/releases/tag/v1",
        published_at=published_at,
        raw_text="Release notes.",
    )


def _cursors() -> dict[str, str]:
    return {
        scan.REPOSITORY_RELEASE_CHECKPOINT_KEY: "2026-08-30T12:00:00+00:00",
        scan.REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY: "2026-08-30T12:00:00+00:00",
    }


class _Monitor:
    def __init__(
        self,
        load_activity: Callable[..., RepositoryActivity],
        refreshed_name: str | None = None,
    ) -> None:
        self._load_activity = load_activity
        self._refreshed_name = refreshed_name
        self.calls: list[Repository] = []
        self.call_kwargs: list[dict] = []

    def load_repository_activity(self, repository: Repository, **kwargs) -> RepositoryActivity:
        self.calls.append(repository)
        self.call_kwargs.append(kwargs)
        result = self._load_activity(repository, **kwargs)
        if isinstance(result, Exception):
            raise result
        return result

    def refresh_repository_profile(self, repository: Repository) -> Repository:
        if self._refreshed_name is None:
            return repository
        return Repository(
            repository_id=repository.repository_id,
            source=repository.source,
            full_name=self._refreshed_name,
            url=f"https://github.com/{self._refreshed_name}",
            metadata=repository.metadata,
            provider_repository_id=repository.provider_repository_id,
        )


@pytest.mark.parametrize("releases_complete,commits_complete", [(False, True), (True, False), (False, False)])
def test_incomplete_scan_retains_each_checkpoint_and_retries_without_duplicates(
    tmp_path, monkeypatch, releases_complete, commits_complete,
):
    from dataclasses import replace
    database_url = build_test_database_url(tmp_path / "partial-monitoring.sqlite3")
    migrate_test_database(database_url)
    repository = _repository()
    user = auth_storage.create_user(user_id="monitor-user", email="monitor@example.com",
                                    display_name="Monitor", database_url=database_url)
    upsert_repositories((repository,), database_url=database_url)
    create_subscription(user_id=user.user_id, repository_id=repository.repository_id,
                        selected_query="monitor", database_url=database_url)
    activity = RepositoryActivity(signals=(), releases_complete=True, commits_complete=True)
    monitor = _Monitor(lambda *_args, **_kwargs: activity)
    resolve_monitor = lambda _source: monitor
    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
    baseline = get_repository_monitoring_cursors(repository.repository_id, database_url=database_url)
    published_at = datetime.now(UTC) + timedelta(minutes=1)
    signals = (_signal("release-1", published_at),
               replace(_signal("commit-1", published_at), kind="commit"))
    activity = RepositoryActivity(signals=signals, releases_complete=releases_complete,
                                  commits_complete=commits_complete)
    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
    first_events = list_feed_events_for_user(user.user_id, database_url=database_url)
    assert len(first_events) == 2
    from app.storage.feed import mark_feed_event_read_for_user
    mark_feed_event_read_for_user(user.user_id, first_events[0].event_id, database_url=database_url)
    partial_cursors = get_repository_monitoring_cursors(repository.repository_id, database_url=database_url)
    for key, complete in ((scan.REPOSITORY_RELEASE_CHECKPOINT_KEY, releases_complete),
                          (scan.REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY, commits_complete)):
        assert partial_cursors[key] == (published_at.isoformat() if complete else baseline[key])
    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
    assert get_repository_monitoring_cursors(repository.repository_id, database_url=database_url) == partial_cursors
    retry_events = list_feed_events_for_user(user.user_id, database_url=database_url)
    assert {event.event_id for event in retry_events} == {event.event_id for event in first_events}
    assert next(event for event in retry_events if event.event_id == first_events[0].event_id).read_at is not None
    with session_scope(database_url) as session:
        runs = session.scalars(select(MonitoringRunRecordModel)).all()
        checks = session.scalars(select(RepositoryMonitoringCheckRecordModel)).all()
    assert sorted(run.status for run in runs) == ["partial", "partial", "succeeded"]
    assert sorted(check.status for check in checks) == ["partial", "partial", "succeeded"]
    assert sum(check.error_code == "incomplete_interval" for check in checks) == 2
    activity = replace(activity, releases_complete=True, commits_complete=True)
    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
    assert set(get_repository_monitoring_cursors(repository.repository_id, database_url=database_url).values()) == {published_at.isoformat()}
    assert len(list_feed_events_for_user(user.user_id, database_url=database_url)) == 2


def test_provider_error_keeps_checkpoints_for_retry(monkeypatch):
    repository = _repository()
    updates = []
    checks = []
    _configure_scan(monkeypatch, subscriptions=(_watch("sub_one", repository),),
                    cursors={repository.repository_id: _cursors()}, checks=checks)
    monkeypatch.setattr(scan, "persist_repository_monitoring_result", lambda *args, **kwargs: updates.append(args))
    def fail(*args, **kwargs):
        raise RepositorySourceError(source="github", status="timed_out", public_message="Provider timed out.")
    resolve_monitor = lambda _source: _Monitor(fail)
    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url="sqlite://")
    assert updates == []
    assert checks[0].status == "failed"
    assert checks[0].error_code == "timed_out"


@pytest.mark.parametrize("provider", ["github", "gitlab"])
def test_paginated_releases_recover_after_page_failure_without_duplicates(tmp_path, monkeypatch, provider):
    from dataclasses import replace
    from urllib.parse import parse_qs, urlsplit
    from app.sources.common import JsonResponse
    from app.sources.github import monitor as github
    from app.sources.gitlab import monitor as gitlab
    from app.storage.feed import mark_feed_event_read_for_user

    adapter = github if provider == "github" else gitlab
    database_url = build_test_database_url(tmp_path / "release-pagination.sqlite3")
    migrate_test_database(database_url)
    repository = replace(_repository(), source=provider, repository_id=f"{provider}:repo:123")
    user = auth_storage.create_user(user_id="release-user", email="release@example.com",
                                    display_name="Release", database_url=database_url)
    upsert_repositories((repository,), database_url=database_url)
    create_subscription(user_id=user.user_id, repository_id=repository.repository_id,
                        selected_query="releases", database_url=database_url)
    published_at = datetime.now(UTC) + timedelta(minutes=1)
    fail_page = True
    def fetch(url):
        if "?" not in url:
            return JsonResponse(payload={"commit": {"sha": "head", "id": "head"}} if "/branches/" in url else {"default_branch": "main"}, url=url)
        if "/commits?" in url:
            return JsonResponse(payload=[], url=url)
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        if page == 2 and fail_page:
            raise RepositorySourceError(source=provider, status="timed_out", public_message="Second page timed out")
        ids = range(1, 101) if page == 1 else range(101, 126)
        return JsonResponse(payload=[{"id": n, "tag_name": f"v{n}", "name": f"Release {n}",
                                     "published_at": published_at.isoformat(), "released_at": published_at.isoformat()}
                                    for n in ids], url=url)
    monkeypatch.setattr(adapter, "fetch_json", fetch)
    resolve_monitor = lambda _source: adapter
    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
    initial_events = list_feed_events_for_user(user.user_id, database_url=database_url)
    assert len(initial_events) == 100
    cursors = get_repository_monitoring_cursors(repository.repository_id, database_url=database_url)
    assert scan.REPOSITORY_RELEASE_CHECKPOINT_KEY not in cursors
    assert scan.REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY in cursors
    mark_feed_event_read_for_user(user.user_id, initial_events[0].event_id, database_url=database_url)
    fail_page = False
    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
    events = list_feed_events_for_user(user.user_id, database_url=database_url)
    assert len(events) == 125
    assert len({event.event_id for event in events}) == 125
    assert next(event for event in events if event.event_id == initial_events[0].event_id).read_at is not None
    cursors = get_repository_monitoring_cursors(repository.repository_id, database_url=database_url)
    assert cursors[scan.REPOSITORY_RELEASE_CHECKPOINT_KEY] == published_at.isoformat()
    with session_scope(database_url) as session:
        runs = session.scalars(select(MonitoringRunRecordModel)).all()
    assert sorted(run.status for run in runs) == ["partial", "succeeded", "succeeded"]


@pytest.mark.parametrize("provider", ["github", "gitlab"])
@pytest.mark.parametrize("partial_first", [False, True])
def test_sha_checkpoint_preserves_backdated_commits_and_retries(tmp_path, monkeypatch, provider, partial_first):
    from dataclasses import replace
    from app.models.monitoring import REPOSITORY_MAIN_COMMIT_SHA_CHECKPOINT_KEY
    from app.sources.github import monitor as github
    from app.sources.gitlab import monitor as gitlab
    from app.storage.feed import mark_feed_event_read_for_user
    from tests.fixtures.repository_monitoring import commit, fake_provider

    adapter = github if provider == "github" else gitlab
    database_url = build_test_database_url(tmp_path / "commit-sha.sqlite3")
    migrate_test_database(database_url)
    repository = replace(_repository(), source=provider, repository_id=f"{provider}:repo:123")
    user = auth_storage.create_user(user_id="commit-user", email="commit@example.com",
                                    display_name="Commit", database_url=database_url)
    upsert_repositories((repository,), database_url=database_url)
    create_subscription(user_id=user.user_id, repository_id=repository.repository_id,
                        selected_query="commits", database_url=database_url)
    # Releases are independently empty; retain the real commit adapter.
    def release_batch(*args, **kwargs):
        from app.sources.common.models import RepositoryActivityBatch
        return RepositoryActivityBatch(signals=(), complete=True)
    monkeypatch.setattr(adapter, "_load_release_signals", release_batch)
    resolve_monitor = lambda _source: adapter
    fake_provider(adapter, monkeypatch, [], head="old-head")
    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
    baseline = get_repository_monitoring_cursors(repository.repository_id, database_url=database_url)
    assert baseline[REPOSITORY_MAIN_COMMIT_SHA_CHECKPOINT_KEY] == "old-head"
    items = [commit("new-head"), *[commit(f"merged-{n}") for n in range(124)]]
    fake_provider(adapter, monkeypatch, items)
    if partial_first:
        monkeypatch.setattr(adapter, "MAX_COMMIT_PAGES", 1)
        scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
        assert len(list_feed_events_for_user(user.user_id, database_url=database_url)) == 100
        assert get_repository_monitoring_cursors(repository.repository_id, database_url=database_url) == baseline
        scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
        assert len(list_feed_events_for_user(user.user_id, database_url=database_url)) == 100
        monkeypatch.setattr(adapter, "MAX_COMMIT_PAGES", 10)
    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
    events = list_feed_events_for_user(user.user_id, database_url=database_url)
    assert len(events) == 125
    assert {event.published_at.year for event in events} == {2010}
    cursors = get_repository_monitoring_cursors(repository.repository_id, database_url=database_url)
    assert cursors[REPOSITORY_MAIN_COMMIT_SHA_CHECKPOINT_KEY] == "new-head"
    assert cursors[scan.REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY] == baseline[scan.REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY]
    mark_feed_event_read_for_user(user.user_id, events[0].event_id, database_url=database_url)
    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
    repeated = list_feed_events_for_user(user.user_id, database_url=database_url)
    assert len(repeated) == 125
    assert next(event for event in repeated if event.event_id == events[0].event_id).read_at is not None
    fake_provider(adapter, monkeypatch, [commit("rebased-head")], head="rebased-head", diverged=True)
    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
    assert get_repository_monitoring_cursors(repository.repository_id, database_url=database_url) == cursors
    assert len(list_feed_events_for_user(user.user_id, database_url=database_url)) == 125
    with session_scope(database_url) as session:
        checks = session.scalars(select(RepositoryMonitoringCheckRecordModel).order_by(RepositoryMonitoringCheckRecordModel.checked_at)).all()
    assert checks[-1].status == "partial"


@pytest.mark.parametrize("failure_stage", ["feed", "cursors", "commit"])
def test_scan_rolls_back_events_and_checkpoints_then_retries(tmp_path, monkeypatch, failure_stage):
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    from app.storage.monitoring import state
    from app.storage.feed.events import mark_feed_event_read_for_user

    database_url = build_test_database_url(tmp_path / "monitoring-rollback.sqlite3")
    migrate_test_database(database_url)
    repository = _repository()
    user = auth_storage.create_user(
        user_id="user_rollback", email="rollback@example.com",
        display_name="Rollback User", database_url=database_url,
    )
    upsert_repositories((repository,), database_url=database_url)
    create_subscription(
        user_id=user.user_id, repository_id=repository.repository_id,
        selected_query="monitoring", database_url=database_url,
    )
    published_at = datetime.now(UTC) + timedelta(minutes=1)
    signals = [_signal("release-1", published_at)]
    monitor = _Monitor(lambda *_args, **_kwargs: RepositoryActivity(
        signals=tuple(signals), releases_complete=True, commits_complete=True,
        commit_head_sha="old-head",
    ))
    resolve_monitor = lambda _source: monitor
    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
    baseline_cursors = get_repository_monitoring_cursors(repository.repository_id, database_url=database_url)
    baseline_event = list_feed_events_for_user(user.user_id, database_url=database_url)[0]
    marked = mark_feed_event_read_for_user(user.user_id, baseline_event.event_id, database_url=database_url)

    from dataclasses import replace
    signals[0] = replace(signals[0], title="Updated title")
    signals.append(_signal("release-2", published_at + timedelta(minutes=1)))
    monitor = _Monitor(lambda *_args, **_kwargs: RepositoryActivity(
        signals=tuple(signals), releases_complete=True, commits_complete=True,
        commit_head_sha="new-head",
    ))
    resolve_monitor = lambda _source: monitor

    def fail_commit(session):
        session.flush()
        raise RuntimeError("Injected monitoring commit failure")

    with monkeypatch.context() as fault:
        if failure_stage == "commit":
            original_persist = scan.persist_repository_monitoring_result
            def fail_persist(*args, **kwargs):
                event.listen(Session, "before_commit", fail_commit)
                try:
                    original_persist(*args, **kwargs)
                finally:
                    event.remove(Session, "before_commit", fail_commit)
            fault.setattr(scan, "persist_repository_monitoring_result", fail_persist)
        else:
            attribute = "write_feed_events" if failure_stage == "feed" else "_write_repository_monitoring_cursors"
            original_write = getattr(state, attribute)
            def fail_write(session, *args):
                original_write(session, *args)
                session.flush()
                raise RuntimeError("Injected monitoring write failure")
            fault.setattr(state, attribute, fail_write)
        scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)

    assert get_repository_monitoring_cursors(repository.repository_id, database_url=database_url) == baseline_cursors
    items = list_feed_events_for_user(user.user_id, database_url=database_url)
    assert len(items) == 1
    assert items[0].title == baseline_event.title
    assert items[0].read_at == marked.read_at
    with session_scope(database_url) as session:
        checks = session.scalars(select(RepositoryMonitoringCheckRecordModel)).all()
        assert [check.status for check in checks].count("failed") == 1

    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
    scan.run_repository_monitoring_scan(resolve_monitor=resolve_monitor, database_url=database_url)
    items = list_feed_events_for_user(user.user_id, database_url=database_url)
    assert len(items) == 2
    updated = next(item for item in items if item.event_id == baseline_event.event_id)
    assert updated.title == "Updated title"
    assert updated.read_at == marked.read_at
    cursors = get_repository_monitoring_cursors(repository.repository_id, database_url=database_url)
    assert cursors[scan.REPOSITORY_MAIN_COMMIT_SHA_CHECKPOINT_KEY] == "new-head"
    assert cursors[scan.REPOSITORY_RELEASE_CHECKPOINT_KEY] == signals[1].published_at.isoformat()
