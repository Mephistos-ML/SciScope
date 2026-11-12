# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Public result selection combines actual admission and ranking outcomes."""

from math import inf, log1p, nextafter

import pytest

from app.models.signal import Signal
from app.services.search.explore.canonical import (
    build_canonical_items,
    select_canonical_candidates,
)
from app.services.search.explore.evaluation import build_explore_search_evaluation
from tests.fixtures.explore import (
    build_explore_repository_signal,
    build_retrieved_candidates,
)


@pytest.mark.parametrize("threshold", [-1, float("nan"), float("inf"), -float("inf")])
def test_invalid_visibility_threshold_is_rejected(threshold):
    retrieved = build_retrieved_candidates(
        source_statuses=(), successful_source_count=0
    )
    with pytest.raises(ValueError, match="finite and nonnegative"):
        build_explore_search_evaluation(
            retrieved, queries=(), score_threshold=threshold
        )


def test_visibility_threshold_has_no_upper_bound():
    retrieved = build_retrieved_candidates(
        source_statuses=(), successful_source_count=0
    )
    evaluation = build_explore_search_evaluation(
        retrieved, queries=(), score_threshold=101
    )
    assert evaluation.score_threshold == 101
    assert build_canonical_items(evaluation) == []


@pytest.mark.parametrize(
    "threshold,expected_count",
    [
        (0.0, 1),
        (0.85 * log1p(1), 1),
        (nextafter(0.85 * log1p(1), inf), 0),
    ],
)
def test_public_selection_includes_threshold_equality(threshold, expected_count):
    retrieved = build_retrieved_candidates(
        build_explore_repository_signal("github:repo:1", query="paramagnetic nmr"),
        source_statuses=(),
        successful_source_count=1,
    )
    evaluation = build_explore_search_evaluation(
        retrieved,
        queries=("paramagnetic nmr",),
        score_threshold=threshold,
    )
    assert evaluation.admission.kept_count == 1
    assert evaluation.score_threshold == threshold
    assert len(evaluation.ranking.ranked_candidates) == 1
    assert evaluation.ranking.ranked_candidates[0].score == pytest.approx(0.85 * log1p(1))
    assert len(select_canonical_candidates(evaluation)) == expected_count
    assert len(build_canonical_items(evaluation)) == expected_count


def test_public_selection_requires_admission_and_score_threshold(monkeypatch):
    monkeypatch.setattr(
        "app.services.search.admission.service.EXPLORE_ADMISSION_MODE", "enforced"
    )
    query = "orca parser"
    rejected = Signal(
        source="github",
        kind="repository",
        item_id="github:repo:rejected",
        title="HeinrichHartmann/arxiv_meta",
        url="https://github.com/HeinrichHartmann/arxiv_meta",
        published_at=None,
        raw_text="HeinrichHartmann/arxiv_meta\nArxiv metadata mirror.",
        payload={
            "repo": "HeinrichHartmann/arxiv_meta",
            "query": query,
            "topics": ["metadata"],
            "language": "",
            "stars": 0,
        },
    )
    retrieved = build_retrieved_candidates(
        build_explore_repository_signal("github:repo:high", query=query),
        build_explore_repository_signal("github:repo:low", query=query),
        rejected,
        source_statuses=(),
        successful_source_count=1,
        match_locations=("name", "description", "name"),
    )
    evaluation = build_explore_search_evaluation(
        retrieved,
        queries=(query,),
        score_threshold=0.65,
    )
    assert evaluation.admission.kept_count == 2
    assert evaluation.admission.rejected_count == 1
    assert len(evaluation.ranking.ranked_candidates) == 3
    assert [item["itemId"] for item in build_canonical_items(evaluation)] == [
        "github:repo:high"
    ]
