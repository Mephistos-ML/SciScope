"""Stateless repository monitoring scan use case."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from functools import partial
import logging

from app.models.monitoring import (
    MonitoringRun, RepositoryMonitoringCheck, REPOSITORY_MAIN_COMMIT_SHA_CHECKPOINT_KEY,
    REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY, REPOSITORY_RELEASE_CHECKPOINT_KEY,
    MonitoringLease, MonitoringLeaseLostError,
)
from app.models.repository import Repository
from app.models.signal import Signal
from app.services.feed.service import build_feed_event
from app.services.feed.publications import build_feed_update_groups
from app.services.monitoring.releases import enrich_release_events
from app.storage.feed.events import get_existing_feed_event_ids
from app.integrations.repositories.common.source_status import RepositorySourceError
from app.services.monitoring.capabilities import RepositoryMonitor
from app.storage.monitoring.state import (
    create_monitoring_run,
    finish_monitoring_run,
    get_repository_monitoring_cursors,
    persist_repository_monitoring_result,
    record_repository_monitoring_check,
)
from app.storage.subscriptions.watches import (
    SubscriptionWatchRecord,
    list_all_subscription_watches,
)


JOB_NAME = "repository-monitoring-scan"
logger = logging.getLogger(__name__)


def scan_repository_subscriptions(
    *,
    resolve_monitor: Callable[[str], RepositoryMonitor | None],
    lease: MonitoringLease, ensure_lease: Callable[[], None],
    database_url: str,
) -> None:
    """Scan every uniquely watched repository and fan out new events."""

    run_id = lease.holder_id
    failed_count = 0
    scanned_count = 0
    started = False
    try:
        ensure_lease()
        create_monitoring_run(
            MonitoringRun(run_id, datetime.now(UTC), None, "running", 0, 0, None),
            lease=lease, database_url=database_url,
        )
        started = True
        subscriptions_by_repository = defaultdict(list)
        for subscription in list_all_subscription_watches(database_url=database_url):
            subscriptions_by_repository[subscription.repository.repository_id].append(subscription)

        for subscriptions in subscriptions_by_repository.values():
            ensure_lease()
            repository = subscriptions[0].repository
            scanned_count += 1
            try:
                complete = _scan_repository(
                    repository, subscriptions, resolve_monitor=resolve_monitor,
                    database_url=database_url, lease=lease, ensure_lease=ensure_lease,
                )
                if not complete:
                    failed_count += 1
                    logger.warning("Repository monitoring read an incomplete interval for %s", repository.repository_id)
                check = RepositoryMonitoringCheck(
                    repository.repository_id,
                    datetime.now(UTC),
                    "succeeded" if complete else "partial",
                    None if complete else "incomplete_interval",
                    None if complete else "Activity reading is incomplete; monitoring will retry.",
                )
            except MonitoringLeaseLostError:
                raise
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
            record_repository_monitoring_check(check, run_id=run_id, lease=lease, database_url=database_url)

        status = "partial" if failed_count else "succeeded"
        finish_monitoring_run(run_id, status=status, scanned_repository_count=scanned_count, failed_repository_count=failed_count, error_summary=None, lease=lease, database_url=database_url)
    except MonitoringLeaseLostError:
        raise
    except Exception:
        logger.exception("Repository monitoring run failed unexpectedly.")
        if started:
            finish_monitoring_run(
                run_id, status="failed", scanned_repository_count=scanned_count,
                failed_repository_count=failed_count, error_summary="Monitoring run failed unexpectedly.",
                lease=lease, database_url=database_url,
            )
        raise


def _scan_repository(
    repository: Repository,
    subscriptions: list[SubscriptionWatchRecord],
    *,
    resolve_monitor: Callable[[str], RepositoryMonitor | None],
    lease: MonitoringLease, ensure_lease: Callable[[], None],
    database_url: str,
) -> bool:
    monitor = resolve_monitor(repository.source)
    if monitor is None:
        return True
    cursors = get_repository_monitoring_cursors(repository.repository_id, database_url=database_url)
    subscription_started_at = min(
        datetime.fromisoformat(subscription.created_at).astimezone(UTC)
        for subscription in subscriptions
    )
    release_after = _read_cursor(
        cursors,
        REPOSITORY_RELEASE_CHECKPOINT_KEY,
        subscription_started_at,
    )
    commit_after = _read_cursor(
        cursors,
        REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY,
        subscription_started_at,
    )
    commit_after_sha = cursors.get(REPOSITORY_MAIN_COMMIT_SHA_CHECKPOINT_KEY)
    activity = monitor.load_repository_activity(
        repository,
        release_started_after=release_after,
        commit_started_after=commit_after,
        commit_after_sha=commit_after_sha,
    )
    ensure_lease()
    refreshed_repository = None
    if activity.redirected:
        profile = monitor.refresh_repository_profile(repository)
        if profile != repository:
            refreshed_repository = profile
            subscriptions = [
                replace(subscription, repository=refreshed_repository)
                for subscription in subscriptions
            ]
    events = [
        build_feed_event(signal, subscription)
        for subscription in subscriptions
        for signal in activity.signals
        if (signal.kind == "commit" and commit_after_sha is not None)
        or _is_after_subscription(signal.published_at, subscription.created_at)
    ]
    release_ids = [event.event_id for event in events if event.kind == "release"]
    existing_ids = get_existing_feed_event_ids(release_ids, database_url=database_url) if release_ids else set()
    publication = enrich_release_events(events, activity.signals, subscriptions, repository, monitor,
                                   existing_ids=existing_ids, ensure_lease=ensure_lease)
    checkpoint_updates: dict[str, str] = {}
    if activity.releases_complete:
        checkpoint_updates[REPOSITORY_RELEASE_CHECKPOINT_KEY] = _latest(
            activity.signals, "release", release_after,
        ).isoformat()
    if activity.commits_complete:
        if activity.commit_head_sha is not None:
            checkpoint_updates[REPOSITORY_MAIN_COMMIT_SHA_CHECKPOINT_KEY] = activity.commit_head_sha
        checkpoint_updates[REPOSITORY_MAIN_COMMIT_CHECKPOINT_KEY] = _latest(
            activity.signals, "commit", commit_after,
        ).isoformat()
    persist_repository_monitoring_result(
        repository.repository_id, publication.events, checkpoint_updates, database_url=database_url,
        supplemental_events=publication.supplemental_events,
        lease=lease, refreshed_repository=refreshed_repository,
        group_new_events=partial(build_feed_update_groups,
                                 publication_key=lease.holder_id, created_at=datetime.now(UTC)),
    )
    return activity.releases_complete and activity.commits_complete


def _read_cursor(cursors: dict[str, str], key: str, fallback: datetime) -> datetime:
    value = cursors.get(key)
    return datetime.fromisoformat(value).astimezone(UTC) if value else fallback


def _latest(signals: tuple[Signal, ...], kind: str, fallback: datetime) -> datetime:
    return max(fallback, max(
        (
            signal.published_at
            for signal in signals
            if signal.kind == kind and signal.published_at
        ),
        default=fallback,
    ))


def _is_after_subscription(published_at: datetime | None, created_at: str) -> bool:
    return published_at is None or published_at > datetime.fromisoformat(created_at).astimezone(UTC)
