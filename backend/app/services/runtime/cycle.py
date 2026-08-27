"""One-scan execution flow for the monitoring runtime."""

from __future__ import annotations

from datetime import UTC, datetime

from app.config import DATABASE_URL
from app.models.signal import Signal
from app.runtime.state import STATE
from app.services.feed import build_feed_event
from app.services.monitoring import load_repository_signals, sync_repository_baseline
from app.sources.replay import load_replay_signals
from app.storage.feed import upsert_feed_events
from app.storage.subscriptions import (
    SubscriptionWatchRecord,
    list_all_subscription_watches,
)


def run_scan_cycle(*, database_url: str = DATABASE_URL) -> None:
    """Run one scan cycle for the current repository subscriptions."""

    with STATE.scan_lock:
        run_scan_cycle_unlocked(database_url=database_url)


def run_baseline_sync(*, database_url: str = DATABASE_URL) -> None:
    """Initialize checkpoints for explicit repository subscriptions."""

    for subscription in list_all_subscription_watches(database_url=database_url):
        sync_repository_baseline(
            subscription.subscription_id,
            subscription.repository,
            baseline_started_at=STATE.monitoring_started_at,
            database_url=database_url,
        )


def run_scan_cycle_unlocked(*, database_url: str) -> None:
    subscriptions = list_all_subscription_watches(database_url=database_url)
    STATE.last_scan_error = None
    feed_events = []

    try:
        replay_signals = load_replay_signals()
        for subscription in subscriptions:
            feed_events.extend(
                build_feed_event(raw_signal, subscription)
                for raw_signal in replay_signals
                if signal_matches_subscription(raw_signal, subscription)
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
                if signal_matches_subscription(raw_signal, subscription)
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


def signal_matches_subscription(
    signal: Signal,
    subscription: SubscriptionWatchRecord,
) -> bool:
    repo_name = signal.payload.get("repo")
    if not isinstance(repo_name, str) or not repo_name.strip():
        return False

    if repo_name.strip() != subscription.repository.full_name:
        return False

    if signal.published_at is None:
        return True

    subscribed_at = datetime.fromisoformat(subscription.created_at).astimezone(UTC)
    return signal.published_at > subscribed_at
