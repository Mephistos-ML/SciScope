"""Bounded optional release enrichment before the fenced publication transaction."""

from collections.abc import Callable, Sequence
from dataclasses import replace
from time import monotonic
import logging

from app.models.feed import FeedEvent, FeedReleaseCommitDetails, RELEASE_COMMIT_METADATA_KEY, FeedPublicationEvents
from app.models.monitoring import ReleaseCommitDetails
from app.models.repository import Repository
from app.models.signal import Signal
from app.services.feed.service import build_feed_event
from app.services.monitoring.capabilities import RepositoryMonitor
from app.storage.subscriptions.watches import SubscriptionWatchRecord

logger = logging.getLogger(__name__)

MAX_RELEASE_COMPARISONS_PER_SCAN = 5
RELEASE_COMPARISON_BUDGET_SECONDS = 15


def enrich_release_events(
    events: Sequence[FeedEvent], signals: Sequence[Signal], subscriptions: Sequence[SubscriptionWatchRecord],
    repository: Repository, monitor: RepositoryMonitor, *, existing_ids: set[str], ensure_lease: Callable[[], None],
) -> FeedPublicationEvents:
    """Enrich only fresh releases; keep raw events as the single commit content owner."""
    fresh_releases = [event for event in events if event.kind == "release" and event.event_id not in existing_ids]
    release_signals = {signal.item_id: signal for signal in signals if signal.kind == "release"}
    watches = {watch.subscription_id: watch for watch in subscriptions}
    facts = {event.event_id: event for event in events}
    supplemental: dict[str, FeedEvent] = {}
    details_by_item: dict[str, ReleaseCommitDetails] = {}
    started = monotonic()
    deadline = started + RELEASE_COMPARISON_BUDGET_SECONDS
    attempted = 0
    for event in sorted(fresh_releases, key=lambda event: (event.published_at is not None, event.published_at, event.item_id), reverse=True):
        if event.item_id not in details_by_item:
            ensure_lease()
            details = ReleaseCommitDetails()
            if len(details_by_item) < MAX_RELEASE_COMPARISONS_PER_SCAN and monotonic() < deadline:
                attempted += 1
                details = monitor.load_release_commit_details(repository, release_signals[event.item_id],
                                                              deadline_monotonic=deadline)
            details_by_item[event.item_id] = details
        details = details_by_item[event.item_id]
        commits = tuple(build_feed_event(signal, watches[event.subscription_id]) for signal in details.commits)
        if any(commit.source != event.source or commit.metadata.get("repo") != event.metadata.get("repo") for commit in commits):
            raise ValueError("Release comparison returned commits from a different repository.")
        for commit in commits:
            if commit.event_id not in facts:
                supplemental.setdefault(commit.event_id, commit)
        references = FeedReleaseCommitDetails(details.status, tuple(commit.event_id for commit in commits),
                                              details.base_sha, details.head_sha, details.total_count)
        facts[event.event_id] = replace(event, metadata={**event.metadata, RELEASE_COMMIT_METADATA_KEY: references.to_metadata()})
    ensure_lease()
    if fresh_releases:
        logger.info("Release commit enrichment completed", extra={
            "repository_id": repository.repository_id, "comparison_count": attempted,
            "complete_count": sum(details.status == "complete" for details in details_by_item.values()),
            "partial_count": sum(details.status == "partial" for details in details_by_item.values()),
            "unavailable_count": sum(details.status == "unavailable" for details in details_by_item.values()),
            "duration_ms": round((monotonic() - started) * 1000),
        })
    return FeedPublicationEvents(tuple(facts.values()), tuple(supplemental.values()))
