"""Tests for durable Explore search job creation."""

from __future__ import annotations

from app import config
from app.models.search_run import SearchRun
from app.services.search.explore.jobs import create_explore_search_run


def test_openai_run_persists_planner_model_and_reasoning_effort(monkeypatch) -> None:
    stored_runs: list[SearchRun] = []
    monkeypatch.setattr(config, "AI_PLANNER_MODE", "openai")
    monkeypatch.setattr(config, "OPENAI_MODEL", "gpt-5.6-luna")
    monkeypatch.setattr(config, "OPENAI_REASONING_EFFORT", "low")
    monkeypatch.setattr(
        "app.services.search.explore.jobs.create_search_run",
        lambda run, **_kwargs: stored_runs.append(run),
    )
    monkeypatch.setattr(
        "app.services.search.explore.jobs.create_search_run_operation",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.search.explore.jobs.get_explore_search_run",
        lambda *_args, **_kwargs: {},
    )

    create_explore_search_run(
        topic_description="Paramagnetic NMR fitting",
        database_url="sqlite://",
    )

    assert len(stored_runs) == 1
    assert stored_runs[0].planner_model == "gpt-5.6-luna"
    assert stored_runs[0].planner_reasoning_effort == "low"
