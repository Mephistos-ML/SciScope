"""Tests for private durable search run reports."""

from __future__ import annotations

import pytest

from app.services.search.run_reports import read_search_run_report


def test_read_search_run_report_returns_owner_report(monkeypatch) -> None:
    report = {"run": {"runId": "run_1", "ownerUserId": "user_1"}, "stages": []}
    monkeypatch.setattr(
        "app.services.search.run_reports.get_search_run_report",
        lambda *_args, **_kwargs: report,
    )

    assert read_search_run_report(
        run_id="run_1",
        user_id="user_1",
        database_url="sqlite://",
    ) == report


def test_read_search_run_report_rejects_other_user(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.search.run_reports.get_search_run_report",
        lambda *_args, **_kwargs: {"run": {"ownerUserId": "user_1"}},
    )

    with pytest.raises(PermissionError, match="does not belong"):
        read_search_run_report(
            run_id="run_1",
            user_id="user_2",
            database_url="sqlite://",
        )
