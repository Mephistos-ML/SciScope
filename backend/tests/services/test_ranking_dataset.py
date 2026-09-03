"""Tests for internal ranking-dataset capture."""

from __future__ import annotations

from app.services import ranking_dataset


def test_save_ranking_dataset_run_captures_server_side_beta_snapshot(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        ranking_dataset,
        "get_explore_search_job",
        lambda _job_id: {
            "ownerUserId": "user_1",
            "responseMode": "beta",
            "status": "completed",
            "topicDescription": "paramagnetic NMR",
            "aiSearchPlan": {"queries": ["paramagnetic nmr"]},
            "items": [
                {
                    "itemId": "github:repo:123",
                    "source": "github",
                    "fullName": "Mephistos-ML/paranmr",
                    "url": "https://github.com/Mephistos-ML/paranmr",
                    "description": "PCS fitting",
                    "stars": 14,
                    "providerUpdatedAt": "2026-09-03T12:30:00+00:00",
                    "score": 88.0,
                    "beta": {"scoreBreakdown": {"queryCoverage": 1.0}},
                }
            ],
        },
    )
    monkeypatch.setattr(
        ranking_dataset,
        "create_ranking_dataset_run",
        lambda run, examples, **_kwargs: captured.update(run=run, examples=examples),
    )

    result = ranking_dataset.save_ranking_dataset_run(
        user_id="user_1",
        search_job_id="job_1",
        labels={"github:repo:123": 2},
        database_url="sqlite://",
    )

    assert result["candidateCount"] == 1
    example = captured["examples"][0]
    assert example.manual_label == 2
    assert example.features["scoreBreakdown"]["queryCoverage"] == 1.0
