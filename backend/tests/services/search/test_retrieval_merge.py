"""Tests for retrieval candidate merge behavior."""

from __future__ import annotations

import time

from app.models.signal import Signal
from app.services.search.retrieval.merge import merge_retrieval_hits
from app.services.search.retrieval import service as retrieval_service
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


def test_merge_retrieval_hits_preserves_language_from_richer_duplicate_signal() -> None:
    repository_signal = _build_repository_signal(
        "github:repo:ecto/phyz",
        query="quantum pair potential",
    )
    code_signal = Signal(
        source="github",
        kind="repository",
        item_id="github:repo:ecto/phyz",
        title="ecto/phyz",
        url="https://github.com/ecto/phyz",
        published_at=None,
        raw_text="ecto/phyz\nMatched code path: src/pair_mie_fh.cpp",
        payload={
            "repo": "ecto/phyz",
            "query": "pair potential",
            "topics": [],
            "language": "",
            "stars": 0,
        },
    )

    candidates = merge_retrieval_hits(
        (
            _build_hit(
                source="github",
                channel="repository_search",
                query="quantum pair potential",
                rank=1,
                signal=repository_signal,
            ),
            _build_hit(
                source="github",
                channel="code_search",
                query="pair potential",
                rank=2,
                signal=code_signal,
            ),
        )
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.signal.payload["language"] == "Python"
    assert candidate.signal.payload["stars"] == 12
    assert candidate.signal.payload["topics"] == ["orca", "chemistry"]
    assert "Matched code path:" in candidate.signal.raw_text


def test_run_external_repository_retrieval_marks_partial_when_parallel_lane_misses_soft_timeout() -> None:
    def discover_github_candidates(_queries: tuple[str, ...]) -> list[Signal]:
        return [
            _build_repository_signal(
                "github:repo:mephistos-ml/paranmr",
                query="paramagnetic nmr",
            )
        ]

    def discover_gitlab_candidates(_queries: tuple[str, ...]) -> list[Signal]:
        time.sleep(0.2)
        return []

    started_at = time.monotonic()
    retrieved = run_external_repository_retrieval(
        ("paramagnetic nmr",),
        discoverers=(
            ("github", "repository_search", discover_github_candidates),
            ("gitlab", "repository_search", discover_gitlab_candidates),
        ),
        soft_deadline_monotonic=time.monotonic() + 0.05,
    )
    elapsed_seconds = time.monotonic() - started_at

    assert retrieved.successful_source_count == 1
    assert len(retrieved.candidates) == 1
    assert retrieved.partial is True
    assert "partial coverage" in retrieved.warnings[0]
    assert elapsed_seconds < 0.15


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
