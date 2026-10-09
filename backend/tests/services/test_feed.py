"""Tests for Feed presentation rules."""

from uuid import UUID

from app.models.feed import build_feed_event_id
from app.services.feed.service import to_feed_item_payload
from dataclasses import replace
from tests.fixtures.feed import feed_event


def test_feed_event_id_is_stable_unique_per_subscription_source_and_item_and_url_safe() -> None:
    identities = (
        ("subscription-123", "github", "owner/repository:commit:abc123"),
        ("subscription-456", "github", "owner/repository:commit:abc123"),
        ("subscription-123", "gitlab", "owner/repository:commit:abc123"),
        ("subscription-123", "github", "owner/repository:commit:def456"),
    )
    event_ids = [build_feed_event_id(*identity) for identity in identities]
    assert len(set(event_ids)) == len(identities)
    for identity, event_id in zip(identities, event_ids, strict=True):
        assert event_id == build_feed_event_id(*identity)
        assert UUID(event_id).version == 5
        assert "/" not in event_id


def test_feed_summary_is_normalized_and_bounded() -> None:
    source = "  ".join(["A concise event summary."] * 40)

    event = replace(feed_event(), raw_text=f"Event title\n\n{source}")
    summary = to_feed_item_payload(event)["summary"]

    assert len(summary) <= 320
    assert summary.endswith("…")
    assert "  " not in summary


def test_subject_only_commits_and_descriptionless_releases_have_no_fabricated_summary():
    from app.integrations.repositories.common.factories import build_repository_commit_signal, build_repository_release_signal
    from app.integrations.repositories.common.models import RepositoryCommit, RepositoryRelease
    from datetime import UTC, datetime

    published = datetime.now(UTC)
    signals = (
        build_repository_commit_signal(RepositoryCommit("github", "science/tool", "a" * 40, "Improve solver",
                                                       "https://example.com/commit", published,
                                                       author_name="Researcher", body="Improve solver")),
        build_repository_release_signal(RepositoryRelease("github", "science/tool", "2", "v2.0",
                                                         "https://example.com/release", published, "v2.0", "")),
    )
    for signal in signals:
        event = replace(feed_event(), kind=signal.kind, title=signal.title, raw_text=signal.raw_text, metadata=signal.payload)
        assert to_feed_item_payload(event)["summary"] == ""
