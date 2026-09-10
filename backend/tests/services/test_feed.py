"""Tests for Feed presentation rules."""

from uuid import UUID

from app.models.feed import build_feed_event_id
from app.services.feed.service import _read_feed_summary


def test_feed_event_id_is_stable_and_url_safe() -> None:
    event_id = build_feed_event_id(
        "subscription-123",
        "github",
        "owner/repository:commit:abc123",
    )

    assert event_id == build_feed_event_id(
        "subscription-123",
        "github",
        "owner/repository:commit:abc123",
    )
    assert UUID(event_id).version == 5
    assert "/" not in event_id


def test_feed_summary_is_normalized_and_bounded() -> None:
    source = "  ".join(["A concise event summary."] * 40)

    summary = _read_feed_summary(f"Event title\n\n{source}")

    assert len(summary) <= 320
    assert summary.endswith("…")
    assert "  " not in summary
