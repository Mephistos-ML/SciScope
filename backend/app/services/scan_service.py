"""Scan orchestration and API-facing view models."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
import threading
import time

from app.config import AUTO_SCAN_INTERVAL_SECONDS
from app.models.signal import RawSignal
from app.runtime.state import STATE
from app.services.discovery_service import discover_github_entities_for_profile
from app.services.matching import match_signal_to_profile
from app.services.normalization import normalize_raw_signal
from app.services.profile_builder import PNMR_PROFILE, PNMR_TOPIC
from app.sources.github.monitor import load_repo_activity
from app.sources.replay import load_replay_signals
from app.storage.entities import list_entities_by_ids, list_topic_entity_matches
from app.storage.seen_signals import load_seen_signal_ids, upsert_raw_signals


@dataclass(frozen=True)
class SignalView:
    """Dashboard-friendly signal projection."""

    item_id: str
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
    """Start the background auto-scan loop and run one immediate scan."""

    try:
        discover_github_entities_for_profile(PNMR_PROFILE)
    except Exception as exc:
        STATE.last_scan_error = f"GitHub discovery failed: {exc}"

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

    run_scan_cycle()


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
    return None


def get_status_payload() -> dict[str, object]:
    """Return a compact JSON-serializable status payload."""

    signals = list_signal_views()
    return {
        "topicSlug": PNMR_PROFILE.topic_slug,
        "topicLabel": PNMR_TOPIC.label,
        "autoScanStarted": STATE.auto_scan_started,
        "autoScanIntervalSeconds": AUTO_SCAN_INTERVAL_SECONDS,
        "lastScanAt": (
            STATE.last_scan_at.isoformat(timespec="seconds")
            if STATE.last_scan_at
            else None
        ),
        "lastScanError": STATE.last_scan_error,
        "totalSignals": len(signals),
        "matchedSignals": sum(1 for signal in signals if signal.matched),
    }


def get_signal_list_payload() -> dict[str, object]:
    """Return a compact list payload for the frontend."""

    return {
        "items": [
            {
                "itemId": signal.item_id,
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
        signals.extend(_build_signal_view(raw_signal) for raw_signal in replay_signals)
    except Exception as exc:
        STATE.last_scan_error = f"Replay fixtures failed to load: {exc}"

    try:
        live_signals = _load_live_github_signals()
        signals.extend(_build_signal_view(raw_signal) for raw_signal in live_signals)
    except Exception as exc:
        message = f"GitHub source failed to load: {exc}"
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
        signal_views[signal.item_id] = SignalView(
            item_id=signal.item_id,
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
    while not stop_event.wait(AUTO_SCAN_INTERVAL_SECONDS):
        run_scan_cycle()


def _build_signal_view(raw_signal: RawSignal) -> SignalView:
    normalized_signal = normalize_raw_signal(raw_signal)
    match = match_signal_to_profile(normalized_signal, PNMR_PROFILE)

    return SignalView(
        item_id=normalized_signal.item_id,
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


def _load_live_github_signals() -> list[RawSignal]:
    started_after = STATE.monitoring_started_at
    repo_names = _load_watched_github_repositories()

    signals: list[RawSignal] = []
    for repo_name in repo_names:
        signals.extend(
            load_repo_activity(
                repo_name,
                started_after=started_after,
            )
        )
    return signals


def _load_watched_github_repositories() -> tuple[str, ...]:
    matches = list_topic_entity_matches(PNMR_PROFILE.topic_slug)
    entity_ids = [match.entity_id for match in matches if match.source == "github"]
    entities = list_entities_by_ids(entity_ids)

    repos: list[str] = []
    for entity in entities:
        if entity.source != "github" or entity.entity_type != "repository":
            continue

        repo_name = entity.metadata.get("repo")
        if not isinstance(repo_name, str) or not repo_name.strip():
            repo_name = entity.canonical_name
        repo_name = repo_name.strip()
        if repo_name:
            repos.append(repo_name)
    return tuple(repos)
