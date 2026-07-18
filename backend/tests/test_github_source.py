"""Tests for the live GitHub release monitoring adapter."""

from __future__ import annotations

from datetime import UTC, datetime

from app.sources.github import monitor as github_monitor


def test_load_repo_activity_builds_release_signals(monkeypatch) -> None:
    started_after = datetime(2026, 7, 17, 10, 0, tzinfo=UTC)

    def fake_fetch_json(url: str) -> object:
        if url.endswith("/releases?per_page=10"):
            return [
                {
                    "id": 12,
                    "name": "v0.3.0",
                    "tag_name": "v0.3.0",
                    "html_url": "https://github.com/Mephistos-ML/paranmr/releases/tag/v0.3.0",
                    "published_at": "2026-07-17T12:15:00Z",
                    "body": "Adds PCS fitting improvements.",
                }
            ]

        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(github_monitor, "fetch_json", fake_fetch_json)

    signals = github_monitor.load_repo_activity(
        "Mephistos-ML/paranmr",
        started_after=started_after,
    )

    assert len(signals) == 1
    release_signal = signals[0]
    assert release_signal.source_type == "github_release"
    assert release_signal.item_id == "Mephistos-ML/paranmr:release:12"
    assert "PCS fitting improvements" in release_signal.raw_text


def test_load_repo_activity_ignores_events_before_start(monkeypatch) -> None:
    started_after = datetime(2026, 7, 17, 13, 0, tzinfo=UTC)

    def fake_fetch_json(url: str) -> object:
        if url.endswith("/releases?per_page=10"):
            return [
                {
                    "id": 5,
                    "name": "v0.2.0",
                    "tag_name": "v0.2.0",
                    "html_url": "https://github.com/Mephistos-ML/paranmr/releases/tag/v0.2.0",
                    "published_at": "2026-07-17T12:00:00Z",
                    "body": "Too old.",
                }
            ]

        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(github_monitor, "fetch_json", fake_fetch_json)

    signals = github_monitor.load_repo_activity(
        "Mephistos-ML/paranmr",
        started_after=started_after,
    )

    assert signals == []
