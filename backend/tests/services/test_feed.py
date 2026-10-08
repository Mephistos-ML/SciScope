"""Tests for Feed presentation rules."""

from uuid import UUID

from app.models.feed import build_feed_event_id
from app.services.feed.service import _read_feed_summary


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

    summary = _read_feed_summary(f"Event title\n\n{source}")

    assert len(summary) <= 320
    assert summary.endswith("…")
    assert "  " not in summary
