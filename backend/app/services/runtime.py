"""Scan orchestration and API-facing view models."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import threading

from app.config import DATABASE_URL
from app.config import MONITORING_INTERVAL_SECONDS, POLLING_FREQUENCY_SECONDS
from app.models.repository import Repository
from app.models.signal import Signal
from app.services.monitoring import load_repository_signals, sync_repository_baseline
from app.runtime.state import STATE
from app.sources.replay import load_replay_signals
from app.storage.repositories import list_repository_checkpoints
from app.storage.signals import load_seen_signal_ids, upsert_signals
from app.storage.subscriptions import (
    SubscriptionWatchRecord,
    list_all_subscription_watches,
)


@dataclass(frozen=True)
class SignalView:
    """Dashboard-friendly signal projection."""

    view_id: str
    subscription_id: str
    repository_id: str
    repository_full_name: str
    selected_query: str | None
    item_id: str
    title: str
    source: str
    kind: str
    url: str
    published_at: datetime | None
    raw_text: str
    normalized_text: str
    metadata: dict[str, object]
    is_new: bool


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


def list_signal_views() -> list[SignalView]:
    """Return signal views sorted for presentation."""

    signals = STATE.signals.values()
    return sorted(
        signals,
        key=lambda item: (
            item.published_at is not None,
            item.published_at or datetime.min.replace(tzinfo=UTC),
            item.item_id,
        ),
        reverse=True,
    )


def get_signal_view(item_id: str) -> SignalView | None:
    """Return one signal view by id."""

    signal = STATE.signals.get(item_id)
    if isinstance(signal, SignalView):
        return signal
    for candidate in STATE.signals.values():
        if isinstance(candidate, SignalView) and candidate.item_id == item_id:
            return candidate
    return None


def get_status_payload(*, database_url: str = DATABASE_URL) -> dict[str, object]:
    """Return a compact JSON-serializable status payload."""

    subscriptions = list_all_subscription_watches(database_url=database_url)
    signals = list_signal_views()
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
        "totalSignals": len(signals),
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


def get_signal_list_payload(*, database_url: str = DATABASE_URL) -> dict[str, object]:
    """Return a compact list payload for the frontend."""

    return {
        "items": [
            {
                "itemId": signal.item_id,
                "viewId": signal.view_id,
                "subscriptionId": signal.subscription_id,
                "repositoryId": signal.repository_id,
                "repositoryFullName": signal.repository_full_name,
                "selectedQuery": signal.selected_query,
                "title": signal.title,
                "source": signal.source,
                "signalKind": signal.kind,
                "url": signal.url,
                "publishedAt": (
                    signal.published_at.isoformat(timespec="seconds")
                    if signal.published_at is not None
                    else None
                ),
                "isNew": signal.is_new,
            }
            for signal in list_signal_views()
        ]
    }


def get_signal_detail_payload(
    item_id: str,
    *,
    database_url: str = DATABASE_URL,
) -> dict[str, object] | None:
    """Return one detailed payload for the frontend."""

    signal = get_signal_view(item_id)
    if signal is None:
        return None

    return {
        "itemId": signal.item_id,
        "viewId": signal.view_id,
        "subscriptionId": signal.subscription_id,
        "repositoryId": signal.repository_id,
        "repositoryFullName": signal.repository_full_name,
        "selectedQuery": signal.selected_query,
        "title": signal.title,
        "source": signal.source,
        "signalKind": signal.kind,
        "url": signal.url,
        "publishedAt": (
            signal.published_at.isoformat(timespec="seconds")
            if signal.published_at is not None
            else None
        ),
        "rawText": signal.raw_text,
        "normalizedText": signal.normalized_text,
        "metadata": signal.metadata,
        "isNew": signal.is_new,
    }


def _run_scan_cycle_unlocked(database_url: str) -> None:
    subscriptions = list_all_subscription_watches(database_url=database_url)
    signals: list[SignalView] = []
    STATE.last_scan_error = None

    try:
        replay_signals = load_replay_signals()
        for subscription in subscriptions:
            signals.extend(
                _build_signal_view(raw_signal, subscription)
                for raw_signal in replay_signals
                if _signal_belongs_to_repository(raw_signal, subscription.repository)
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
            signals.extend(
                _build_signal_view(raw_signal, subscription)
                for raw_signal in live_signals
            )
    except Exception as exc:
        message = f"Repository source failed to load: {exc}"
        STATE.last_scan_error = (
            f"{STATE.last_scan_error}; {message}"
            if STATE.last_scan_error
            else message
        )

    seen_ids_by_source = _load_seen_ids_by_source(
        signals,
        database_url=database_url,
    )
    signal_views: dict[str, SignalView] = {}
    signals_to_store: list[Signal] = []
    for signal in signals:
        seen_ids = seen_ids_by_source.get(signal.source, set())
        signal_views[signal.view_id] = SignalView(
            view_id=signal.view_id,
            subscription_id=signal.subscription_id,
            repository_id=signal.repository_id,
            repository_full_name=signal.repository_full_name,
            selected_query=signal.selected_query,
            item_id=signal.item_id,
            title=signal.title,
            source=signal.source,
            kind=signal.kind,
            url=signal.url,
            published_at=signal.published_at,
            raw_text=signal.raw_text,
            normalized_text=signal.normalized_text,
            metadata=signal.metadata,
            is_new=signal.item_id not in seen_ids,
        )
        signals_to_store.append(
            Signal(
                source=signal.source,
                kind=signal.kind,
                item_id=signal.item_id,
                title=signal.title,
                url=signal.url,
                published_at=signal.published_at,
                raw_text=signal.raw_text,
                normalized_text=signal.normalized_text,
                payload=signal.metadata,
            )
        )

    STATE.signals.clear()
    STATE.signals.update(signal_views)
    upsert_signals(signals_to_store, database_url=database_url)
    STATE.last_scan_at = datetime.now(UTC)


def _auto_scan_loop(database_url: str) -> None:
    stop_event = STATE.auto_scan_stop_event
    while not stop_event.wait(POLLING_FREQUENCY_SECONDS):
        with STATE.scan_lock:
            if _should_run_monitoring():
                _run_scan_cycle_unlocked(database_url)


def _build_signal_view(
    signal: Signal,
    subscription: SubscriptionWatchRecord,
) -> SignalView:
    return SignalView(
        view_id=f"{subscription.subscription_id}:{signal.item_id}",
        subscription_id=subscription.subscription_id,
        repository_id=subscription.repository.repository_id,
        repository_full_name=subscription.repository.full_name,
        selected_query=subscription.selected_query,
        item_id=signal.item_id,
        title=signal.title,
        source=signal.source,
        kind=signal.kind,
        url=signal.url,
        published_at=signal.published_at,
        raw_text=signal.raw_text,
        normalized_text=signal.normalized_text,
        metadata=dict(signal.payload),
        is_new=False,
    )


def _load_seen_ids_by_source(
    signals: list[SignalView],
    *,
    database_url: str,
) -> dict[str, set[str]]:
    """Load seen ids once per source for the current scan batch."""

    grouped_sources: dict[str, set[str]] = defaultdict(set)
    for signal in signals:
        grouped_sources[signal.source].add(signal.item_id)

    return {
        source: load_seen_signal_ids(source, database_url=database_url)
        for source in grouped_sources
    }


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
    repository: Repository,
) -> bool:
    repo_name = signal.payload.get("repo")
    if isinstance(repo_name, str) and repo_name.strip():
        return repo_name.strip() == repository.full_name
    return False
def _should_run_monitoring() -> bool:
    """Return whether the next source monitoring cycle is due."""

    if STATE.last_scan_at is None:
        return True

    return datetime.now(UTC) - STATE.last_scan_at >= timedelta(
        seconds=MONITORING_INTERVAL_SECONDS
    )
