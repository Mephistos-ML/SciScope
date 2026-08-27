"""Repository monitoring runtime orchestration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import threading

from app.config import DATABASE_URL
from app.config import MONITORING_INTERVAL_SECONDS, POLLING_FREQUENCY_SECONDS
from app.models.signal import Signal
from app.services.feed import build_feed_event
from app.services.monitoring import load_repository_signals, sync_repository_baseline
from app.runtime.state import STATE
from app.sources.replay import load_replay_signals
from app.storage.repositories import list_repository_checkpoints
from app.storage.feed import count_feed_events, upsert_feed_events
from app.storage.subscriptions import (
    SubscriptionWatchRecord,
    list_all_subscription_watches,
)


def start_monitoring(*, database_url: str = DATABASE_URL) -> None:
    """Start the scheduler and initialize repository monitoring baselines."""

    if not STATE.auto_scan_started:
        STATE.monitoring_started_at = datetime.now(UTC)
        STATE.auto_scan_stop_event = threading.Event()
        STATE.auto_scan_started = True
        STATE.auto_scan_thread = threading.Thread(
            target=lambda: _auto_scan_loop(database_url),
            name="sciscope-auto-scan",
            daemon=True,
        )
        STATE.auto_scan_thread.start()
    elif STATE.monitoring_started_at is None:
        STATE.monitoring_started_at = datetime.now(UTC)

    run_baseline_sync(database_url=database_url)


def stop_monitoring(*, database_url: str = DATABASE_URL) -> None:
    """Stop the background auto-scan loop."""

    if not STATE.auto_scan_started:
        return

    STATE.auto_scan_started = False
    STATE.auto_scan_stop_event.set()
    STATE.auto_scan_thread = None


def run_scan_cycle(*, database_url: str = DATABASE_URL) -> None:
    """Run one scan cycle for the current repository subscriptions."""

    with STATE.scan_lock:
        _run_scan_cycle_unlocked(database_url)


def get_status_payload(*, database_url: str = DATABASE_URL) -> dict[str, object]:
    """Return a compact JSON-serializable status payload."""

    subscriptions = list_all_subscription_watches(database_url=database_url)
    return {
        "subscriptionCount": len(subscriptions),
        "subscriptions": [
            {
                "subscriptionId": subscription.subscription_id,
                "repositoryId": subscription.repository.repository_id,
                "source": subscription.repository.source,
                "fullName": subscription.repository.full_name,
                "selectedQuery": subscription.selected_query,
            }
            for subscription in subscriptions
        ],
        "autoScanStarted": STATE.auto_scan_started,
        "autoScanIntervalSeconds": MONITORING_INTERVAL_SECONDS,
        "monitoringIntervalSeconds": MONITORING_INTERVAL_SECONDS,
        "lastScanAt": (
            STATE.last_scan_at.isoformat(timespec="seconds")
            if STATE.last_scan_at
            else None
        ),
        "lastScanError": STATE.last_scan_error,
        "watchedRepositories": _describe_watched_repositories(subscriptions),
        "sourceCheckpoints": _describe_repository_checkpoints(
            subscriptions,
            database_url=database_url,
        ),
        "totalFeedEvents": count_feed_events(database_url=database_url),
    }


def run_baseline_sync(*, database_url: str = DATABASE_URL) -> None:
    """Initialize checkpoints for explicit repository subscriptions."""

    for subscription in list_all_subscription_watches(database_url=database_url):
        sync_repository_baseline(
            subscription.subscription_id,
            subscription.repository,
            baseline_started_at=STATE.monitoring_started_at,
            database_url=database_url,
        )


def _run_scan_cycle_unlocked(database_url: str) -> None:
    subscriptions = list_all_subscription_watches(database_url=database_url)
    STATE.last_scan_error = None
    feed_events = []

    try:
        replay_signals = load_replay_signals()
        for subscription in subscriptions:
            feed_events.extend(
                build_feed_event(raw_signal, subscription)
                for raw_signal in replay_signals
                if _signal_belongs_to_repository(raw_signal, subscription)
            )
    except Exception as exc:
        STATE.last_scan_error = f"Replay fixtures failed to load: {exc}"

    try:
        for subscription in subscriptions:
            live_signals = load_repository_signals(
                subscription.subscription_id,
                subscription.repository,
                baseline_started_after=STATE.monitoring_started_at,
                database_url=database_url,
            )
            feed_events.extend(
                build_feed_event(raw_signal, subscription)
                for raw_signal in live_signals
                if _signal_belongs_to_repository(raw_signal, subscription)
            )
    except Exception as exc:
        message = f"Repository source failed to load: {exc}"
        STATE.last_scan_error = (
            f"{STATE.last_scan_error}; {message}"
            if STATE.last_scan_error
            else message
        )

    upsert_feed_events(feed_events, database_url=database_url)
    STATE.last_scan_at = datetime.now(UTC)


def _auto_scan_loop(database_url: str) -> None:
    stop_event = STATE.auto_scan_stop_event
    while not stop_event.wait(POLLING_FREQUENCY_SECONDS):
        with STATE.scan_lock:
            if _should_run_monitoring():
                _run_scan_cycle_unlocked(database_url)


def _describe_watched_repositories(
    subscriptions: list[SubscriptionWatchRecord],
) -> list[dict[str, object]]:
    return [
        {
            "subscriptionId": subscription.subscription_id,
            "repositoryId": subscription.repository.repository_id,
            "source": subscription.repository.source,
            "fullName": subscription.repository.full_name,
            "url": subscription.repository.url,
            "selectedQuery": subscription.selected_query,
            "stars": subscription.repository.metadata.get("stars"),
            "language": subscription.repository.metadata.get("language"),
        }
        for subscription in subscriptions
    ]


def _describe_repository_checkpoints(
    subscriptions: list[SubscriptionWatchRecord],
    *,
    database_url: str,
) -> list[dict[str, object]]:
    checkpoints: list[dict[str, object]] = []
    for subscription in subscriptions:
        for checkpoint in list_repository_checkpoints(
            subscription.subscription_id,
            subscription.repository.repository_id,
            database_url=database_url,
        ):
            checkpoints.append(
                {
                    "subscriptionId": subscription.subscription_id,
                    "repositoryId": subscription.repository.repository_id,
                    "source": subscription.repository.source,
                    "fullName": subscription.repository.full_name,
                    "checkpointKey": checkpoint.checkpoint_key,
                    "checkpointValue": checkpoint.checkpoint_value,
                    "updatedAt": checkpoint.updated_at.isoformat(timespec="seconds"),
                }
            )
    return checkpoints


def _signal_belongs_to_repository(
    signal: Signal,
    subscription: SubscriptionWatchRecord,
) -> bool:
    repo_name = signal.payload.get("repo")
    if isinstance(repo_name, str) and repo_name.strip():
        if repo_name.strip() != subscription.repository.full_name:
            return False

        if signal.published_at is None:
            return True

        subscribed_at = datetime.fromisoformat(subscription.created_at).astimezone(UTC)
        return signal.published_at > subscribed_at
    return False


def _should_run_monitoring() -> bool:
    """Return whether the next source monitoring cycle is due."""

    if STATE.last_scan_at is None:
        return True

    return datetime.now(UTC) - STATE.last_scan_at >= timedelta(
        seconds=MONITORING_INTERVAL_SECONDS
    )
