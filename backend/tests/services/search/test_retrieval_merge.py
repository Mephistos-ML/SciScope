"""Tests for retrieval candidate merge behavior."""

from __future__ import annotations

from app.models.signal import Signal
from app.services.search.retrieval.merge import merge_retrieval_hits
from app.services.search.retrieval.service import run_external_repository_retrieval


def _build_repository_signal(
    item_id: str,
    *,
    query: str,
    source: str = "github",
) -> Signal:
    return Signal(
        source=source,
        kind="repository",
        item_id=item_id,
        title="kragskow-group/orto",
        url="https://example.com/kragskow-group/orto",
        published_at=None,
        raw_text="kragskow-group/orto\nA python package for working with ORCA.",
        payload={
            "repo": "kragskow-group/orto",
            "query": query,
            "topics": ["orca", "chemistry"],
            "language": "Python",
            "stars": 12,
        },
    )


def test_merge_retrieval_hits_accumulates_candidate_provenance() -> None:
    first_signal = _build_repository_signal(
        "gitlab:repo:kragskow-group/orto",
        query="orca python",
    )
    second_signal = _build_repository_signal(
        "gitlab:repo:kragskow-group/orto",
        query="orca output parser python",
    )

    candidates = merge_retrieval_hits(
        (
            _build_hit(
                source="gitlab",
                channel="repository_search",
                query="orca python",
                rank=7,
                signal=first_signal,
            ),
            _build_hit(
                source="gitlab",
                channel="code_search",
                query="orca output parser python",
                rank=3,
                signal=second_signal,
            ),
        )
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.repository_id == "gitlab:repo:kragskow-group/orto"
    assert candidate.signal.payload["query"] == "orca output parser python"
    assert candidate.provenance.matched_queries == (
        "orca python",
        "orca output parser python",
    )
    assert candidate.provenance.matched_channels == (
        "repository_search",
        "code_search",
    )
    assert dict(candidate.provenance.best_rank_by_channel) == {
        "repository_search": 7,
        "code_search": 3,
    }
    assert candidate.provenance.hit_count == 2


def test_run_external_repository_retrieval_merges_duplicate_repo_hits() -> None:
    def discover_github_candidates(_queries: tuple[str, ...]) -> list[Signal]:
        return [
            _build_repository_signal(
                "github:repo:mephistos-ml/paranmr",
                query="paramagnetic nmr",
            ),
            _build_repository_signal(
                "github:repo:mephistos-ml/paranmr",
                query="pcs susceptibility tensor fitting",
            ),
        ]

    retrieved = run_external_repository_retrieval(
        ("paramagnetic nmr", "pcs susceptibility tensor fitting"),
        discoverers=(("github", "repository_search", discover_github_candidates),),
    )

    assert retrieved.successful_source_count == 1
    assert len(retrieved.candidates) == 1
    candidate = retrieved.candidates[0]
    assert candidate.repository_id == "github:repo:mephistos-ml/paranmr"
    assert candidate.provenance.matched_queries == (
        "paramagnetic nmr",
        "pcs susceptibility tensor fitting",
    )
    assert candidate.provenance.matched_channels == ("repository_search",)
    assert dict(candidate.provenance.best_rank_by_channel) == {
        "repository_search": 1,
    }
    assert candidate.provenance.hit_count == 2


def _build_hit(
    *,
    source: str,
    channel: str,
    query: str,
    rank: int,
    signal: Signal,
):
    from app.services.search.retrieval.models import RetrievalHit

    return RetrievalHit(
        source=source,
        channel=channel,
        query=query,
        rank=rank,
        signal=signal,
    )
