# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Bounded popularity signal and its effect on observable ranking behavior."""

from dataclasses import replace
from math import log, log1p

import pytest

from app.services.search.ranking import rank_repository_candidates
from app.services.search.ranking.models import PopularityBoostParameters
from tests.fixtures.explore import (
    build_explore_repository_signal,
    build_retrieved_candidates,
)


def _candidate(
    stars, *, title="science/tool", item_id="github:repo:1", location="description"
):
    signal = build_explore_repository_signal(item_id, query="science")
    signal = replace(signal, title=title, payload={**signal.payload, "stars": stars})
    return build_retrieved_candidates(
        signal,
        source_statuses=(),
        successful_source_count=1,
        match_locations=(location,),
    ).candidates[0]


@pytest.mark.parametrize("stars", [0, 1, 10, 100, 1000, 10000, 10**400])
def test_log_popularity_is_normalized_and_bonus_is_bounded(stars):
    ranked = rank_repository_candidates(
        (_candidate(stars),),
        queries=("science",),
        popularity_boost=PopularityBoostParameters(
            max_bonus=0.05, reference_stars=1000
        ),
    ).ranked_candidates[0]
    popularity = ranked.score_breakdown.popularity
    expected = log(1 + min(stars, 1000)) / log(1001)
    assert popularity.stars == stars
    assert popularity.normalized_popularity == pytest.approx(expected)
    assert 0 <= popularity.contribution <= 0.05
    assert popularity.contribution == pytest.approx(0.05 * expected)
    assert ranked.score == pytest.approx(0.85 * log1p(1) + 0.05 * expected)


@pytest.mark.parametrize("stars", [None, -1, "100", 2.5, True, float("inf")])
def test_missing_or_invalid_star_counts_are_neutral(stars):
    ranked = rank_repository_candidates(
        (_candidate(stars),),
        queries=("science",),
        popularity_boost=PopularityBoostParameters(max_bonus=0.05),
    ).ranked_candidates[0]
    assert ranked.features.stars is None
    assert ranked.score_breakdown.popularity.stars is None
    assert ranked.score_breakdown.popularity.normalized_popularity == 0
    assert ranked.score_breakdown.popularity.contribution == 0


def test_zero_default_bonus_preserves_match_only_order_and_scores():
    a = _candidate(0, title="aaa", item_id="github:repo:1")
    b = _candidate(1000, title="zzz", item_id="github:repo:2")
    default = rank_repository_candidates((b, a), queries=("science",))
    assert [item.candidate.repository_id for item in default.ranked_candidates] == [
        a.repository_id,
        b.repository_id,
    ]
    assert all(item.score == 0.85 * log1p(1) for item in default.ranked_candidates)
    boosted = rank_repository_candidates(
        (a, b),
        queries=("science",),
        popularity_boost=PopularityBoostParameters(max_bonus=0.05),
    )
    assert [item.candidate.repository_id for item in boosted.ranked_candidates] == [
        b.repository_id,
        a.repository_id,
    ]


def test_popularity_cannot_reverse_a_match_score_gap_larger_than_its_cap():
    strong = _candidate(0, item_id="github:repo:strong", location="name")
    weak = _candidate(1000000, item_id="github:repo:weak", location="code")
    result = rank_repository_candidates(
        (weak, strong),
        queries=("science",),
        popularity_boost=PopularityBoostParameters(max_bonus=0.05),
    )
    assert log1p(1) - 0.6 * log1p(1) > 0.05
    assert result.ranked_candidates[0].candidate.repository_id == strong.repository_id


def test_star_reference_is_fixed_independently_of_the_candidate_pool():
    candidate = _candidate(10)
    parameters = PopularityBoostParameters(max_bonus=0.05)
    alone = rank_repository_candidates(
        (candidate,), queries=("science",), popularity_boost=parameters
    )
    together = rank_repository_candidates(
        (candidate, _candidate(10**6, item_id="github:repo:2")),
        queries=("science",),
        popularity_boost=parameters,
    )
    rescored = next(
        item
        for item in together.ranked_candidates
        if item.candidate.repository_id == candidate.repository_id
    )
    assert rescored.score == alone.ranked_candidates[0].score


def test_additive_bonus_is_explicit_even_without_current_query_matches():
    candidate = _candidate(1000)
    result = rank_repository_candidates(
        (candidate,),
        queries=("different query",),
        popularity_boost=PopularityBoostParameters(max_bonus=0.05),
    ).ranked_candidates[0]
    assert result.score_breakdown.locations == ()
    assert result.score == 0.05


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_bonus": -1},
        {"max_bonus": float("nan")},
        {"max_bonus": float("inf")},
        {"max_bonus": True},
        {"reference_stars": 0},
        {"reference_stars": -1},
        {"reference_stars": True},
        {"reference_stars": 1.5},
    ],
)
def test_invalid_popularity_parameters_are_rejected(kwargs):
    with pytest.raises(ValueError):
        PopularityBoostParameters(**kwargs)
