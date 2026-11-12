# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Observable ranking/counting behavior for logarithmic match scoring."""

from dataclasses import replace
from math import log, log1p

import pytest

from app.models.signal import Signal
from app.services.search.ranking import rank_repository_candidates
from app.services.search.ranking.features import build_ranking_features
from app.services.search.ranking.models import LocationMatchCount, RankingFeatures
from app.services.search.ranking.score import (
    build_relevance_score_breakdown,
    calculate_relevance_score,
)
from app.services.search.retrieval import (
    CandidateProvenance,
    RepositoryCandidate,
    RetrievalMatchEvidence,
)


def _features(**counts):
    return RankingFeatures(
        matched_query_count=1,
        total_query_count=1,
        hit_count=1,
        evidence_count=sum(counts.values()),
        location_counts=tuple(
            LocationMatchCount(location, count) for location, count in counts.items()
        ),
    )


def test_score_matches_the_agreed_multilocation_example():
    features = _features(name=1, description=2, readme=5)
    expected = log(2) + 0.85 * log(3) + 0.65 * log(6)
    assert calculate_relevance_score(features) == pytest.approx(expected)
    breakdown = build_relevance_score_breakdown(features)
    assert sum(item.points for item in breakdown.locations) == pytest.approx(expected)
    assert [
        (item.location, item.count, item.weight) for item in breakdown.locations
    ] == [
        ("name", 1, 1.0),
        ("description", 2, 0.85),
        ("readme", 5, 0.65),
    ]
    assert breakdown.schema_version == 2
    assert breakdown.formula == "location_weighted_log_matches_v1"


@pytest.mark.parametrize(
    "location,weight",
    [
        ("name", 1),
        ("description", 0.85),
        ("topic", 0.75),
        ("readme", 0.65),
        ("documentation", 0.55),
        ("code", 0.60),
        ("other", 0.25),
        ("metadata", 0.65),
    ],
)
def test_location_weights_and_diminishing_positive_increments(location, weight):
    scores = [calculate_relevance_score(_features(**{location: n})) for n in range(5)]
    assert scores[0] == 0
    assert scores[1] == pytest.approx(weight * log(2))
    increments = [b - a for a, b in zip(scores, scores[1:])]
    assert all(delta > 0 for delta in increments)
    assert all(a > b for a, b in zip(increments, increments[1:]))


def test_empty_evidence_and_zero_counts_score_zero():
    assert calculate_relevance_score(_features()) == 0
    assert calculate_relevance_score(_features(code=0, readme=0)) == 0


@pytest.mark.parametrize("count", [-1, 1.5, True])
def test_invalid_counts_are_rejected(count):
    with pytest.raises(ValueError, match="nonnegative integer"):
        LocationMatchCount("code", count)


def test_counts_include_multiple_files_and_locations_for_the_same_query():
    evidence = (
        RetrievalMatchEvidence("science", "name"),
        RetrievalMatchEvidence("science", "readme", path="README.md"),
        RetrievalMatchEvidence("science", "code", path="src/a.py"),
        RetrievalMatchEvidence("science", "code", path="src/b.py"),
    )
    candidate = _build_candidate(
        item_id="github:repo:1",
        source="github",
        raw_text="science/tool",
        matched_queries=("science",),
        match_evidence=evidence,
    )
    features = build_ranking_features(candidate, ("science",))
    assert {item.location: item.count for item in features.location_counts} == {
        "name": 1,
        "readme": 1,
        "code": 2,
    }
    assert calculate_relevance_score(features) == pytest.approx(
        log(2) + 0.65 * log(2) + 0.6 * log(3)
    )


def test_duplicate_delivery_does_not_inflate_counts_or_score():
    original = RetrievalMatchEvidence(
        "Scientific Software",
        "code",
        path="src/tool.py",
        channel="code_search",
        origin="provider",
        retrieval_rank=1,
    )
    candidate = _build_candidate(
        item_id="github:repo:1",
        source="github",
        raw_text="science/tool",
        matched_queries=(original.query,),
        match_evidence=(original,),
    )
    duplicate = replace(
        candidate,
        provenance=replace(
            candidate.provenance,
            hit_count=20,
            match_evidence=(
                original,
                original,
                replace(
                    original,
                    query=" scientific   SOFTWARE ",
                    origin="catalog",
                    retrieval_rank=90,
                ),
                replace(original, channel="semantic_catalog", alignment=0.75),
                replace(original, path=" src\\tool.py "),
                # Historical file hits could be labeled by overlapping metadata.
                replace(original, location="description", origin="catalog"),
            ),
        ),
    )
    single = build_ranking_features(candidate, (original.query,))
    repeated = build_ranking_features(duplicate, (original.query,))
    assert single.location_counts == repeated.location_counts
    assert calculate_relevance_score(single) == calculate_relevance_score(repeated)
    assert repeated.hit_count == 20  # Delivery diagnostics remain independent.


def test_counts_only_current_queries_and_ignores_query_order():
    candidate = _build_candidate(
        item_id="github:repo:1",
        source="github",
        raw_text="science/tool",
        matched_queries=("historical", "current one", "current two"),
        match_evidence=tuple(
            RetrievalMatchEvidence(query, "description")
            for query in (
                "historical",
                "current one",
                "current two",
            )
        ),
    )
    first = build_ranking_features(
        candidate, ("current one", "current two", "current three")
    )
    second = build_ranking_features(
        candidate, ("current two", "current three", "CURRENT ONE", "current one")
    )
    assert first == second
    assert first.matched_query_count == 2
    assert first.total_query_count == 3
    assert first.location_counts == (LocationMatchCount("description", 2),)
    assert calculate_relevance_score(first) == pytest.approx(0.85 * log(3))


def test_alignment_does_not_change_the_count_formula():
    candidate = _build_candidate(
        item_id="github:repo:1",
        source="github",
        raw_text="science/tool",
        match_evidence=(
            RetrievalMatchEvidence("science", "description", alignment=0.75),
        ),
    )
    direct = replace(
        candidate,
        provenance=replace(
            candidate.provenance,
            match_evidence=(
                RetrievalMatchEvidence("science", "description", alignment=1.0),
            ),
        ),
    )
    assert calculate_relevance_score(
        build_ranking_features(candidate, ("science",))
    ) == (calculate_relevance_score(build_ranking_features(direct, ("science",))))


def test_more_file_matches_can_outweigh_a_higher_weight_location():
    one_name = _build_candidate(
        item_id="github:repo:name",
        source="github",
        raw_text="science/tool",
        match_evidence=(RetrievalMatchEvidence("science", "name"),),
    )
    three_files = _build_candidate(
        item_id="github:repo:files",
        source="github",
        raw_text="science/tool",
        match_evidence=tuple(
            RetrievalMatchEvidence("science", "code", path=f"src/{i}.py")
            for i in range(3)
        ),
    )
    result = rank_repository_candidates(
        (one_name, three_files), queries=("science",), relevance_cutoff=0.7
    )
    assert [item.candidate.repository_id for item in result.ranked_candidates] == [
        three_files.repository_id,
        one_name.repository_id,
    ]
    assert [item.candidate.repository_id for item in result.visible_candidates] == [
        three_files.repository_id
    ]


def test_full_precision_and_stable_identity_tie_break():
    a = _build_candidate(
        item_id="github:repo:a",
        source="github",
        raw_text="science/mie-fh",
        match_evidence=(RetrievalMatchEvidence("science", "name"),),
    )
    b = replace(a, repository_id="gitlab:repo:b")
    for candidates in ((a, b), (b, a)):
        result = rank_repository_candidates(
            candidates, queries=("science",), relevance_cutoff=0
        )
        assert result.ranked_candidates[0].candidate.repository_id == a.repository_id
        assert result.ranked_candidates[0].score == pytest.approx(log(2), abs=1e-14)
    # Ranking values retain small differences even when display rounding ties.
    lower = calculate_relevance_score(_features(code=10000))
    higher = calculate_relevance_score(_features(code=10001))
    assert higher > lower
    assert round(higher, 2) == round(lower, 2)


@pytest.mark.parametrize("cutoff", [-1, float("nan"), float("inf"), -float("inf")])
def test_invalid_cutoff_is_rejected(cutoff):
    with pytest.raises(ValueError, match="finite and nonnegative"):
        rank_repository_candidates((), queries=(), relevance_cutoff=cutoff)


def test_cutoff_has_no_upper_bound_and_equality_is_visible():
    assert (
        rank_repository_candidates(
            (), queries=(), relevance_cutoff=101
        ).visible_candidates
        == ()
    )
    candidate = _build_candidate(
        item_id="github:repo:a",
        source="github",
        raw_text="science/tool",
        match_evidence=(RetrievalMatchEvidence("science", "name"),),
    )
    result = rank_repository_candidates(
        (candidate,), queries=("science",), relevance_cutoff=log1p(1)
    )
    assert len(result.visible_candidates) == 1


def _build_candidate(
    *,
    item_id: str,
    source: str,
    raw_text: str,
    matched_channels: tuple[str, ...] = ("repository_search",),
    matched_queries: tuple[str, ...] = ("feynman-hibbs mie potential",),
    hit_count: int = 1,
    match_evidence: tuple[RetrievalMatchEvidence, ...] = (),
) -> RepositoryCandidate:
    title = "science/mie-fh" if "science/mie-fh" in raw_text else item_id.split(":")[-1]
    signal = Signal(
        source=source,
        kind="repository",
        item_id=item_id,
        title=title,
        url=f"https://example.test/{title}",
        published_at=None,
        raw_text=raw_text,
        payload={"repo": title, "topics": [], "language": "", "stars": 0},
    )
    return RepositoryCandidate(
        repository_id=item_id,
        signal=signal,
        provenance=CandidateProvenance(
            matched_queries=matched_queries,
            matched_channels=matched_channels,
            best_rank_by_channel={channel: 1 for channel in matched_channels},
            hit_count=hit_count,
            match_evidence=match_evidence,
        ),
    )
