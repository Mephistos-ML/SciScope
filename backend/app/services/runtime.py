"""Scan orchestration and API-facing view models."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import threading

from app.config import (
    DISCOVERY_INTERVAL_SECONDS,
    MONITORING_INTERVAL_SECONDS,
    POLLING_FREQUENCY_SECONDS,
)
from app.models.signal import RawSignal
from app.runtime.state import STATE
from app.services.search.matching import match_signal_to_profile
from app.services.search.normalization import normalize_raw_signal
from app.services.topics.registry import (
    list_runtime_profiles,
    list_runtime_topics,
)
from app.sources.repositories.runtime import (
    discover_repository_entities_for_profile,
    describe_repository_checkpoints,
    describe_watched_repositories,
    load_repository_signals_for_profile,
    sync_repository_baseline_for_profile,
)
from app.sources.replay import load_replay_signals
from app.storage.seen_signals import load_seen_signal_ids, upsert_raw_signals


@dataclass(frozen=True)
class SignalView:
    """Dashboard-friendly signal projection."""

    view_id: str
    topic_slug: str
    item_id: str
    topic_label: str
    title: str
    source: str
    signal_kind: str
    url: str
    matched: bool
    score: float
    reason: str
    matched_terms: tuple[str, ...]
    excluded_terms: tuple[str, ...]
    raw_text: str
    normalized_text: str
    metadata: dict[str, object]
    is_new: bool


def start_monitoring() -> None:
    """Start the scheduler, run discovery, and initialize monitoring baselines."""

    if not STATE.auto_scan_started:
        STATE.monitoring_started_at = datetime.now(UTC)
        STATE.auto_scan_stop_event = threading.Event()
        STATE.auto_scan_started = True
        STATE.auto_scan_thread = threading.Thread(
            target=_auto_scan_loop,
            name="sciscope-auto-scan",
            daemon=True,
        )
        STATE.auto_scan_thread.start()
    elif STATE.monitoring_started_at is None:
        STATE.monitoring_started_at = datetime.now(UTC)

    run_discovery_cycle()
    run_baseline_sync()


def stop_monitoring() -> None:
    """Stop the background auto-scan loop."""

    if not STATE.auto_scan_started:
        return

    STATE.auto_scan_started = False
    STATE.auto_scan_stop_event.set()
    STATE.auto_scan_thread = None


def run_scan_cycle() -> None:
    """Run one replay-backed scan cycle."""

    with STATE.scan_lock:
        _run_scan_cycle_unlocked()


def list_signal_views() -> list[SignalView]:
    """Return signal views sorted for presentation."""

    signals = STATE.signals.values()
    return sorted(signals, key=lambda item: (-item.score, item.item_id))


def get_signal_view(item_id: str) -> SignalView | None:
    """Return one signal view by id."""

    signal = STATE.signals.get(item_id)
    if isinstance(signal, SignalView):
        return signal
    for candidate in STATE.signals.values():
        if isinstance(candidate, SignalView) and candidate.item_id == item_id:
            return candidate
    return None


def get_status_payload() -> dict[str, object]:
    """Return a compact JSON-serializable status payload."""

    runtime_profiles = list_runtime_profiles()
    runtime_topics = list_runtime_topics()
    signals = list_signal_views()
    watched_entities = _describe_all_watched_repositories(runtime_profiles)
    source_checkpoints = _describe_all_repository_checkpoints(runtime_profiles)
    primary_topic = runtime_topics[0] if runtime_topics else None
    primary_profile = runtime_profiles[0] if runtime_profiles else None
    return {
        "topicSlug": primary_profile.topic_slug if primary_profile else None,
        "topicLabel": primary_topic.label if primary_topic else None,
        "subscriptionCount": len(runtime_profiles),
        "topics": [
            {
                "topicSlug": topic.slug,
                "topicLabel": topic.label,
            }
            for topic in runtime_topics
        ],
        "autoScanStarted": STATE.auto_scan_started,
        "autoScanIntervalSeconds": MONITORING_INTERVAL_SECONDS,
        "monitoringIntervalSeconds": MONITORING_INTERVAL_SECONDS,
        "discoveryIntervalSeconds": DISCOVERY_INTERVAL_SECONDS,
        "lastScanAt": (
            STATE.last_scan_at.isoformat(timespec="seconds")
            if STATE.last_scan_at
            else None
        ),
        "lastScanError": STATE.last_scan_error,
        "lastDiscoveryAt": (
            STATE.last_discovery_at.isoformat(timespec="seconds")
            if STATE.last_discovery_at
            else None
        ),
        "lastDiscoveryError": STATE.last_discovery_error,
        "lastDiscoveryResult": STATE.last_discovery_result,
        "discoveryQueries": (
            list(STATE.last_discovery_result.get("queries", []))
            if isinstance(STATE.last_discovery_result, dict)
            else []
        ),
        "watchedEntities": watched_entities,
        "sourceCheckpoints": source_checkpoints,
        "totalSignals": len(signals),
        "matchedSignals": sum(1 for signal in signals if signal.matched),
    }


def run_discovery_cycle() -> None:
    """Run one discovery cycle."""

    try:
        discovery_results = [
            discover_repository_entities_for_profile(profile)
            for profile in list_runtime_profiles()
        ]
        STATE.last_discovery_result = _build_discovery_summary_payload(discovery_results)
        STATE.last_discovery_at = datetime.now(UTC)
        STATE.last_discovery_error = None
    except Exception as exc:
        STATE.last_discovery_error = str(exc)
        STATE.last_discovery_at = datetime.now(UTC)
        STATE.last_scan_error = f"Discovery failed: {exc}"


def run_baseline_sync() -> None:
    """Initialize checkpoints for newly admitted source entities."""

    for profile in list_runtime_profiles():
        sync_repository_baseline_for_profile(profile)


def get_signal_list_payload() -> dict[str, object]:
    """Return a compact list payload for the frontend."""

    return {
        "items": [
            {
                "itemId": signal.item_id,
                "viewId": signal.view_id,
                "topicSlug": signal.topic_slug,
                "topicLabel": signal.topic_label,
                "title": signal.title,
                "source": signal.source,
                "signalKind": signal.signal_kind,
                "url": signal.url,
                "matched": signal.matched,
                "score": signal.score,
                "reason": signal.reason,
                "isNew": signal.is_new,
            }
            for signal in list_signal_views()
        ]
    }


def get_signal_detail_payload(item_id: str) -> dict[str, object] | None:
    """Return one detailed payload for the frontend."""

    signal = get_signal_view(item_id)
    if signal is None:
        return None

    return {
        "itemId": signal.item_id,
        "viewId": signal.view_id,
        "topicSlug": signal.topic_slug,
        "topicLabel": signal.topic_label,
        "title": signal.title,
        "source": signal.source,
        "signalKind": signal.signal_kind,
        "url": signal.url,
        "matched": signal.matched,
        "score": signal.score,
        "reason": signal.reason,
        "matchedTerms": list(signal.matched_terms),
        "excludedTerms": list(signal.excluded_terms),
        "rawText": signal.raw_text,
        "normalizedText": signal.normalized_text,
        "metadata": signal.metadata,
        "isNew": signal.is_new,
    }


def _run_scan_cycle_unlocked() -> None:
    signals: list[SignalView] = []
    STATE.last_scan_error = None

    try:
        replay_signals = load_replay_signals()
        runtime_topics_by_slug = {
            topic.slug: topic
            for topic in list_runtime_topics()
        }
        for profile in list_runtime_profiles():
            topic = runtime_topics_by_slug.get(profile.topic_slug)
            if topic is None:
                continue
            signals.extend(
                _build_signal_view(
                    raw_signal,
                    active_profile=profile,
                    topic_label=topic.label,
                )
                for raw_signal in replay_signals
            )
    except Exception as exc:
        STATE.last_scan_error = f"Replay fixtures failed to load: {exc}"

    try:
        runtime_topics_by_slug = {
            topic.slug: topic
            for topic in list_runtime_topics()
        }
        for profile in list_runtime_profiles():
            live_signals = load_repository_signals_for_profile(profile)
            topic = runtime_topics_by_slug.get(profile.topic_slug)
            if topic is None:
                continue
            signals.extend(
                _build_signal_view(
                    raw_signal,
                    active_profile=profile,
                    topic_label=topic.label,
                )
                for raw_signal in live_signals
            )
    except Exception as exc:
        message = f"Repository source failed to load: {exc}"
        STATE.last_scan_error = (
            f"{STATE.last_scan_error}; {message}"
            if STATE.last_scan_error
            else message
        )

    seen_ids_by_source = _load_seen_ids_by_source(signals)
    signal_views: dict[str, SignalView] = {}
    raw_signals_to_store: list[RawSignal] = []
    for signal in signals:
        seen_ids = seen_ids_by_source.get(signal.source, set())
        signal_views[signal.view_id] = SignalView(
            view_id=signal.view_id,
            topic_slug=signal.topic_slug,
            item_id=signal.item_id,
            topic_label=signal.topic_label,
            title=signal.title,
            source=signal.source,
            signal_kind=signal.signal_kind,
            url=signal.url,
            matched=signal.matched,
            score=signal.score,
            reason=signal.reason,
            matched_terms=signal.matched_terms,
            excluded_terms=signal.excluded_terms,
            raw_text=signal.raw_text,
            normalized_text=signal.normalized_text,
            metadata=signal.metadata,
            is_new=signal.item_id not in seen_ids,
        )
        raw_signals_to_store.append(
            RawSignal(
                source=signal.source,
                source_type=str(signal.metadata.get("source_type", signal.signal_kind)),
                item_id=signal.item_id,
                title=signal.title,
                url=signal.url,
                published_at=None,
                raw_text=signal.raw_text,
                payload=signal.metadata,
            )
        )

    STATE.signals.clear()
    STATE.signals.update(signal_views)
    upsert_raw_signals(raw_signals_to_store)
    STATE.last_scan_at = datetime.now(UTC)


def _auto_scan_loop() -> None:
    stop_event = STATE.auto_scan_stop_event
    while not stop_event.wait(POLLING_FREQUENCY_SECONDS):
        with STATE.scan_lock:
            if _should_run_discovery():
                run_discovery_cycle()
                run_baseline_sync()

            if _should_run_monitoring():
                _run_scan_cycle_unlocked()


def _build_signal_view(
    raw_signal: RawSignal,
    *,
    active_profile,
    topic_label: str,
) -> SignalView:
    normalized_signal = normalize_raw_signal(raw_signal)
    match = match_signal_to_profile(normalized_signal, active_profile)

    return SignalView(
        view_id=f"{active_profile.topic_slug}:{normalized_signal.item_id}",
        topic_slug=active_profile.topic_slug,
        item_id=normalized_signal.item_id,
        topic_label=topic_label,
        title=normalized_signal.title,
        source=normalized_signal.source,
        signal_kind=normalized_signal.signal_kind,
        url=normalized_signal.url,
        matched=match.matched,
        score=match.score,
        reason=match.reason,
        matched_terms=match.matched_terms,
        excluded_terms=match.excluded_terms,
        raw_text=raw_signal.raw_text,
        normalized_text=normalized_signal.normalized_text,
        metadata=normalized_signal.metadata,
        is_new=False,
    )


def _load_seen_ids_by_source(signals: list[SignalView]) -> dict[str, set[str]]:
    """Load seen ids once per source for the current scan batch."""

    grouped_sources: dict[str, set[str]] = defaultdict(set)
    for signal in signals:
        grouped_sources[signal.source].add(signal.item_id)

    return {
        source: load_seen_signal_ids(source)
        for source in grouped_sources
    }


def _build_discovery_summary_payload(discovery_results) -> dict[str, object]:
    if not discovery_results:
        return {
            "topicSlug": None,
            "queries": [],
            "candidateCount": 0,
            "entityCount": 0,
            "matchedEntityCount": 0,
            "profiles": [],
        }

    merged_queries: list[str] = []
    seen_queries: set[str] = set()
    for result in discovery_results:
        for query in result.queries:
            if query in seen_queries:
                continue
            seen_queries.add(query)
            merged_queries.append(query)

    return {
        "topicSlug": "all-subscriptions" if len(discovery_results) > 1 else discovery_results[0].topic_slug,
        "queries": merged_queries,
        "candidateCount": sum(result.candidate_count for result in discovery_results),
        "entityCount": sum(result.entity_count for result in discovery_results),
        "matchedEntityCount": sum(result.matched_entity_count for result in discovery_results),
        "profiles": [result.to_payload() for result in discovery_results],
    }


def _describe_all_watched_repositories(
    profiles: tuple,
) -> list[dict[str, object]]:
    watched: list[dict[str, object]] = []
    for profile in profiles:
        watched.extend(describe_watched_repositories(profile.topic_slug))
    return watched


def _describe_all_repository_checkpoints(
    profiles: tuple,
) -> list[dict[str, object]]:
    checkpoints: list[dict[str, object]] = []
    for profile in profiles:
        checkpoints.extend(describe_repository_checkpoints(profile.topic_slug))
    return checkpoints


def _should_run_discovery() -> bool:
    """Return whether the next daily discovery cycle is due."""

    if STATE.last_discovery_at is None:
        return True

    return datetime.now(UTC) - STATE.last_discovery_at >= timedelta(
        seconds=DISCOVERY_INTERVAL_SECONDS
    )


def _should_run_monitoring() -> bool:
    """Return whether the next source monitoring cycle is due."""

    if STATE.last_scan_at is None:
        return True

    return datetime.now(UTC) - STATE.last_scan_at >= timedelta(
        seconds=MONITORING_INTERVAL_SECONDS
    )
