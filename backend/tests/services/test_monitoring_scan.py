"""Tests for the stateless repository monitoring scan use case."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from tests.conftest import build_test_database_url, migrate_test_database
from app.database.records import MonitoringRunRecordModel, RepositoryMonitoringCheckRecordModel
from app.database.session import session_scope
from app.models.repository import Repository
from app.models.signal import Signal
from app.services.monitoring import scan
from app.sources.common import RepositoryActivity
from app.sources.common import RepositorySourceError
from app.storage import auth as auth_storage
from app.storage.feed import list_feed_events_for_user
from app.storage.monitoring import (
    acquire_monitoring_job_lease,
    get_repository_monitoring_cursors,
    release_monitoring_job_lease,
)
from app.storage.repositories import upsert_repositories
from app.storage.subscriptions import create_subscription
from app.storage.subscriptions import SubscriptionWatchRecord


def test_scan_baselines_new_repository_without_loading_history(monkeypatch) -> None:
    repository = _repository()
    cursor_updates: list[tuple[str, dict[str, str]]] = []
    monitor = _Monitor(lambda *_args, **_kwargs: AssertionError("must not load history"))
    _configure_scan(monkeypatch, subscriptions=(_watch("sub_one", repository),))
    monkeypatch.setattr(scan, "get_repository_monitor", lambda _source: monitor)
    monkeypatch.setattr(
        scan,
        "upsert_repository_monitoring_cursors",
        lambda repository_id, values, **_kwargs: cursor_updates.append((repository_id, values)),
    )

    scan.run_repository_monitoring_scan(database_url="sqlite://")

    assert monitor.calls == []
    assert len(cursor_updates) == 1
    repository_id, values = cursor_updates[0]
    assert repository_id == repository.repository_id
    assert set(values) == {
        scan.REPOSITORY_RELEASE_CHECKPOINT_KEY,
        scan.REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY,
    }


def test_scan_loads_each_repository_once_and_fans_out_events(monkeypatch) -> None:
    repository = _repository()
    watches = (_watch("sub_one", repository), _watch("sub_two", repository))
    signal = _signal("release-1", datetime(2026, 9, 1, 12, tzinfo=UTC))
    monitor = _Monitor(lambda *_args, **_kwargs: RepositoryActivity(signals=(signal,)))
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
    monkeypatch.setattr(scan, "get_repository_monitor", lambda _source: monitor)

    scan.run_repository_monitoring_scan(database_url="sqlite://")

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
    monkeypatch.setattr(
        scan,
        "get_repository_monitor",
        lambda _source: _Monitor(
            lambda repository, **_kwargs: (
                (_ for _ in ()).throw(RuntimeError("provider unavailable"))
                if repository.full_name == "example/broken"
                else RepositoryActivity(signals=(healthy_signal,))
            )
        ),
    )

    scan.run_repository_monitoring_scan(database_url="sqlite://")

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

    scan.run_repository_monitoring_scan(database_url="sqlite://")

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
    monkeypatch.setattr(
        scan,
        "get_repository_monitor",
        lambda _source: _Monitor(
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RepositorySourceError(
                    source="github",
                    status="rate_limited",
                    public_message="GitHub is temporarily rate limited.",
                )
            )
        ),
    )

    scan.run_repository_monitoring_scan(database_url="sqlite://")

    assert checks[0].status == "failed"
    assert checks[0].error_code == "rate_limited"
    assert checks[0].error_message == "GitHub is temporarily rate limited."


def test_scan_refreshes_repository_profile_after_provider_redirect(monkeypatch) -> None:
    repository = _repository()
    refreshed_repositories = []
    monitor = _Monitor(
        lambda *_args, **_kwargs: RepositoryActivity(signals=(), redirected=True),
        refreshed_name="example/renamed-repository",
    )
    _configure_scan(
        monkeypatch,
        subscriptions=(_watch("sub_one", repository),),
        cursors={repository.repository_id: _cursors()},
    )
    monkeypatch.setattr(scan, "get_repository_monitor", lambda _source: monitor)
    monkeypatch.setattr(
        scan,
        "upsert_repositories",
        lambda repositories, **_kwargs: refreshed_repositories.extend(repositories),
    )

    scan.run_repository_monitoring_scan(database_url="sqlite://")

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
        lambda *_args, **_kwargs: RepositoryActivity(signals=tuple(signals))
    )
    monkeypatch.setattr(scan, "get_repository_monitor", lambda _source: monitor)

    scan.run_repository_monitoring_scan(database_url=database_url)

    baseline_cursors = get_repository_monitoring_cursors(
        repository.repository_id,
        database_url=database_url,
    )
    assert monitor.calls == []
    assert set(baseline_cursors) == {
        scan.REPOSITORY_RELEASE_CHECKPOINT_KEY,
        scan.REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY,
    }

    published_at = datetime.now(UTC) + timedelta(minutes=1)
    signals.append(_signal("release-1", published_at))

    scan.run_repository_monitoring_scan(database_url=database_url)

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
    monkeypatch.setattr(scan, "upsert_repository_monitoring_cursors", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        scan,
        "upsert_feed_events",
        lambda new_events, **_kwargs: events.extend(new_events) if events is not None else None,
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

    def load_repository_activity(self, repository: Repository, **kwargs) -> RepositoryActivity:
        self.calls.append(repository)
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
