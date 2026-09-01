from app.models.signal import Signal
from app.services.search.ranking import rank_repository_candidates
from app.services.search.ranking.score import calculate_relevance_score
from app.services.search.ranking.models import RankingFeatures
from app.services.search.retrieval import CandidateProvenance, RepositoryCandidate


def test_ranking_rewards_multiple_independent_query_matches_with_diminishing_returns() -> None:
    one_match = calculate_relevance_score(
        RankingFeatures(
            matched_query_count=1,
            total_query_count=5,
            hit_count=1,
            name_match=0.0,
            description_match=0.0,
            topics_match=0.0,
        )
    )
    two_matches = calculate_relevance_score(
        RankingFeatures(
            matched_query_count=2,
            total_query_count=5,
            hit_count=2,
            name_match=0.0,
            description_match=0.0,
            topics_match=0.0,
        )
    )
    five_matches = calculate_relevance_score(
        RankingFeatures(
            matched_query_count=5,
            total_query_count=5,
            hit_count=5,
            name_match=0.0,
            description_match=0.0,
            topics_match=0.0,
        )
    )

    assert one_match < two_matches < five_matches
    assert (two_matches - one_match) > (five_matches - two_matches) / 3


def test_ranking_weights_name_match_more_than_description_match() -> None:
    name_match = calculate_relevance_score(
        RankingFeatures(
            matched_query_count=1,
            total_query_count=5,
            hit_count=1,
            name_match=1.0,
            description_match=0.0,
            topics_match=0.0,
        )
    )
    description_match = calculate_relevance_score(
        RankingFeatures(
            matched_query_count=1,
            total_query_count=5,
            hit_count=1,
            name_match=0.0,
            description_match=1.0,
            topics_match=0.0,
        )
    )

    assert name_match > description_match


def test_ranking_ignores_source_channel_and_matched_code_path() -> None:
    github_candidate = _build_candidate(
        item_id="github:repo:science/mie-fh",
        source="github",
        matched_channels=("code_search",),
        raw_text=(
            "science/mie-fh\n"
            "Feynman-Hibbs Mie potential package.\n"
            "Matched code path: src/feynman_hibbs_mie.cpp"
        ),
    )
    gitlab_candidate = _build_candidate(
        item_id="gitlab:repo:science/mie-fh",
        source="gitlab",
        matched_channels=("repository_search",),
        raw_text="science/mie-fh\nFeynman-Hibbs Mie potential package.",
    )

    result = rank_repository_candidates(
        (github_candidate, gitlab_candidate),
        queries=("Feynman-Hibbs Mie potential",),
        relevance_cutoff=0.0,
    )

    assert result.ranked_candidates[0].score == result.ranked_candidates[1].score
    assert result.ranked_candidates[0].features == result.ranked_candidates[1].features


def test_ranking_sorts_candidates_and_applies_relevance_cutoff() -> None:
    strong_candidate = _build_candidate(
        item_id="github:repo:science/lammps-mie-fh",
        source="github",
        raw_text=(
            "science/lammps-mie-fh\n"
            "LAMMPS Feynman-Hibbs Mie potential extension."
        ),
        matched_queries=(
            "lammps feynman-hibbs",
            "feynman-hibbs mie potential",
        ),
        hit_count=2,
    )
    weak_candidate = _build_candidate(
        item_id="github:repo:other/example",
        source="github",
        raw_text="other/example\nGeneral scientific utilities.",
        matched_queries=("pair potential",),
        hit_count=1,
    )

    result = rank_repository_candidates(
        (weak_candidate, strong_candidate),
        queries=(
            "lammps feynman-hibbs",
            "feynman-hibbs mie potential",
            "quantum-corrected mie potential",
            "lammps pair style mie",
            "semiclassical correction",
        ),
        relevance_cutoff=40.0,
    )

    assert [
        candidate.candidate.repository_id for candidate in result.ranked_candidates
    ] == [strong_candidate.repository_id, weak_candidate.repository_id]
    assert [
        candidate.candidate.repository_id for candidate in result.visible_candidates
    ] == [strong_candidate.repository_id]


def _build_candidate(
    *,
    item_id: str,
    source: str,
    raw_text: str,
    matched_channels: tuple[str, ...] = ("repository_search",),
    matched_queries: tuple[str, ...] = ("feynman-hibbs mie potential",),
    hit_count: int = 1,
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
        ),
    )
