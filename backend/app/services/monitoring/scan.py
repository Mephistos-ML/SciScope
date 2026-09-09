"""Stateless repository monitoring scan use case."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import UTC, datetime
import logging
from uuid import uuid4

from app.config import DATABASE_URL
from app.models.monitoring import MonitoringRun, RepositoryMonitoringCheck
from app.models.repository import Repository
from app.models.signal import Signal
from app.services.feed.service import build_feed_event
from app.sources.common.factories import (
    REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY,
    REPOSITORY_RELEASE_CHECKPOINT_KEY,
)
from app.sources.common.source_status import RepositorySourceError
from app.sources.registry import get_repository_monitor
from app.storage.feed.events import upsert_feed_events
from app.storage.monitoring.state import (
    acquire_monitoring_job_lease,
    create_monitoring_run,
    finish_monitoring_run,
    get_repository_monitoring_cursors,
    record_repository_monitoring_check,
    release_monitoring_job_lease,
    upsert_repository_monitoring_cursors,
)
from app.storage.repositories.repositories import upsert_repositories
from app.storage.subscriptions.watches import (
    SubscriptionWatchRecord,
    list_all_subscription_watches,
)


JOB_NAME = "repository-monitoring-scan"
logger = logging.getLogger(__name__)


def run_repository_monitoring_scan(*, database_url: str = DATABASE_URL) -> None:
    """Scan every uniquely watched repository and fan out new events."""

    run_id = str(uuid4())
    if not acquire_monitoring_job_lease(JOB_NAME, run_id, database_url=database_url):
        return

    started_at = datetime.now(UTC)
    create_monitoring_run(
        MonitoringRun(run_id, started_at, None, "running", 0, 0, None),
        database_url=database_url,
    )
    failed_count = 0
    scanned_count = 0
    try:
        subscriptions_by_repository = defaultdict(list)
        for subscription in list_all_subscription_watches(database_url=database_url):
            subscriptions_by_repository[subscription.repository.repository_id].append(subscription)

        for subscriptions in subscriptions_by_repository.values():
            repository = subscriptions[0].repository
            scanned_count += 1
            try:
                _scan_repository(repository, subscriptions, database_url=database_url)
                check = RepositoryMonitoringCheck(
                    repository.repository_id,
                    datetime.now(UTC),
                    "succeeded",
                    None,
                    None,
                )
            except RepositorySourceError as error:
                failed_count += 1
                logger.warning(
                    "Repository monitoring source %s failed for %s: %s",
                    repository.source,
                    repository.repository_id,
                    error,
                    exc_info=True,
                )
                check = RepositoryMonitoringCheck(
                    repository.repository_id,
                    datetime.now(UTC),
                    "failed",
                    error.status,
                    error.public_message,
                )
            except Exception:
                failed_count += 1
                logger.exception(
                    "Repository monitoring failed unexpectedly for %s.",
                    repository.repository_id,
                )
                check = RepositoryMonitoringCheck(
                    repository.repository_id,
                    datetime.now(UTC),
                    "failed",
                    "unexpected",
                    "Monitoring will retry automatically.",
                )
            record_repository_monitoring_check(check, run_id=run_id, database_url=database_url)

        status = "partial" if failed_count else "succeeded"
        finish_monitoring_run(run_id, status=status, scanned_repository_count=scanned_count, failed_repository_count=failed_count, error_summary=None, database_url=database_url)
    except Exception:
        logger.exception("Repository monitoring run failed unexpectedly.")
        finish_monitoring_run(
            run_id,
            status="failed",
            scanned_repository_count=scanned_count,
            failed_repository_count=failed_count,
            error_summary="Monitoring run failed unexpectedly.",
            database_url=database_url,
        )
        raise
    finally:
        release_monitoring_job_lease(JOB_NAME, run_id, database_url=database_url)


def _scan_repository(
    repository: Repository,
    subscriptions: list[SubscriptionWatchRecord],
    *,
    database_url: str,
) -> None:
    monitor = get_repository_monitor(repository.source)
    if monitor is None:
        return
    cursors = get_repository_monitoring_cursors(repository.repository_id, database_url=database_url)
    now = datetime.now(UTC)
    release_after = _read_cursor(cursors, REPOSITORY_RELEASE_CHECKPOINT_KEY, now)
    commit_after = _read_cursor(cursors, REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY, now)
    if not cursors:
        upsert_repository_monitoring_cursors(
            repository.repository_id,
            {
                REPOSITORY_RELEASE_CHECKPOINT_KEY: now.isoformat(),
                REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY: now.isoformat(),
            },
            database_url=database_url,
        )
        return
    activity = monitor.load_repository_activity(
        repository,
        release_started_after=release_after,
        commit_started_after=commit_after,
    )
    if activity.redirected:
        refreshed_repository = monitor.refresh_repository_profile(repository)
        if refreshed_repository != repository:
            upsert_repositories((refreshed_repository,), database_url=database_url)
            subscriptions = [
                replace(subscription, repository=refreshed_repository)
                for subscription in subscriptions
            ]
    events = [
        build_feed_event(signal, subscription)
        for subscription in subscriptions
        for signal in activity.signals
        if _is_after_subscription(signal.published_at, subscription.created_at)
    ]
    upsert_feed_events(events, database_url=database_url)
    upsert_repository_monitoring_cursors(
        repository.repository_id,
        {
            REPOSITORY_RELEASE_CHECKPOINT_KEY: _latest(
                activity.signals,
                "release",
                release_after,
            ).isoformat(),
            REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY: _latest(
                activity.signals,
                "commit",
                commit_after,
            ).isoformat(),
        },
        database_url=database_url,
    )


def _read_cursor(cursors: dict[str, str], key: str, fallback: datetime) -> datetime:
    value = cursors.get(key)
    return datetime.fromisoformat(value).astimezone(UTC) if value else fallback


def _latest(signals: tuple[Signal, ...], kind: str, fallback: datetime) -> datetime:
    return max(
        (
            signal.published_at
            for signal in signals
            if signal.kind == kind and signal.published_at
        ),
        default=fallback,
    )


def _is_after_subscription(published_at: datetime | None, created_at: str) -> bool:
    return published_at is None or published_at > datetime.fromisoformat(created_at).astimezone(UTC)
