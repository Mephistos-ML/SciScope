"""Tests for Feed presentation rules."""

from app.services.feed.service import _read_feed_summary


def test_feed_summary_is_normalized_and_bounded() -> None:
    source = "  ".join(["A concise event summary."] * 40)

    summary = _read_feed_summary(f"Event title\n\n{source}")

    assert len(summary) <= 320
    assert summary.endswith("…")
    assert "  " not in summary
