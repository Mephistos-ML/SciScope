"""Release grouping policy and the repository enrichment resource budget."""

from dataclasses import replace
from datetime import timedelta

import pytest

from app.models.feed import FeedReleaseCommitDetails, RELEASE_COMMIT_METADATA_KEY, read_feed_release_commit_details
from app.models.monitoring import ReleaseCommitDetails
from app.models.signal import Signal
from app.services.feed.publications import build_feed_update_groups
from app.services.feed.service import build_feed_event
from app.services.monitoring import releases
from app.storage.subscriptions.watches import SubscriptionWatchRecord
from app.models.repository import Repository
from tests.fixtures.feed import feed_event


def test_ambiguous_release_membership_does_not_arbitrarily_hide_the_commit_batch():
    commit = feed_event()
    first = feed_event("release:one", kind="release")
    second = feed_event("release:two", kind="release")
    references = FeedReleaseCommitDetails("complete", (commit.event_id,), "b" * 40, "a" * 40, 1).to_metadata()
    events = (replace(first, metadata={RELEASE_COMMIT_METADATA_KEY: references}),
              replace(second, metadata={RELEASE_COMMIT_METADATA_KEY: references}), commit)
    groups = build_feed_update_groups(events, publication_key="scan-one", created_at=first.created_at)
    assert {group.event_ids for group in groups if group.kind == "release"} == {(first.event_id,), (second.event_id,)}
    assert [group.event_ids for group in groups if group.kind == "commits"] == [(commit.event_id,)]


@pytest.mark.parametrize("exhaust_deadline", [False, True])
def test_optional_enrichment_budget_prioritizes_newest_releases_and_shares_requests(monkeypatch, exhaust_deadline):
    now = feed_event().created_at
    repository = Repository("github:repo:123", "github", "science/tool", "https://github.com/science/tool")
    watches = [SubscriptionWatchRecord(f"sub-{user}", user, repository, None, now.isoformat()) for user in ("alice", "bob")]
    signals = [Signal("github", "release", f"release:{index}", f"v{index}", repository.url,
                      now + timedelta(minutes=index), "Notes", payload={"repo": repository.full_name}) for index in range(7)]
    events = [build_feed_event(signal, watch) for watch in watches for signal in signals]
    clock = [100.0]
    monkeypatch.setattr(releases, "monotonic", lambda: clock[0])
    requests = []
    class Monitor:
        def load_release_commit_details(self, repository, signal, *, deadline_monotonic):
            requests.append(signal.item_id)
            assert deadline_monotonic == 115
            if exhaust_deadline:
                clock[0] = 115
            return ReleaseCommitDetails("complete", (), "a" * 40, "a" * 40, 0)
    result = releases.enrich_release_events(events, signals, watches, repository, Monitor(),
                                           existing_ids=set(), ensure_lease=lambda: None)
    assert requests == (["release:6"] if exhaust_deadline else [f"release:{index}" for index in range(6, 1, -1)])
    assert len(result.events) == 14  # No releases are delayed or discarded when details hit their budget.
    enriched = [event for event in result.events if read_feed_release_commit_details(event.metadata).status == "complete"]
    assert len(enriched) == len(requests) * 2
