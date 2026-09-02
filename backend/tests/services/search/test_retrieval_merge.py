"""Tests for retrieval candidate merge behavior."""

from __future__ import annotations

import time
from dataclasses import replace

from app.models.signal import Signal
from app.services.search.retrieval.merge import merge_retrieval_hits
from app.services.search.retrieval.service import run_external_repository_retrieval
from app.sources.common import RepositorySourceError


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
            "description": "A python package for working with ORCA.",
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
    second_signal = replace(
        _build_repository_signal(
            "gitlab:repo:kragskow-group/orto",
            query="orca output parser python",
        ),
        payload={
            **_build_repository_signal(
                "gitlab:repo:kragskow-group/orto",
                query="orca output parser python",
            ).payload,
            "matched_path": "src/orto/parser.py",
        },
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
    assert candidate.provenance.match_evidence[0].location == "description"
    assert candidate.provenance.match_evidence[1].location == "code"
    assert candidate.provenance.match_evidence[1].path == "src/orto/parser.py"


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
    assert len(candidate.provenance.match_evidence) == 2


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


def test_merge_retrieval_hits_classifies_match_locations_by_strength() -> None:
    name_signal = replace(
        _build_repository_signal(
            "github:repo:science/feynman-hibbs-mie",
            query="feynman hibbs mie",
        ),
        title="science/feynman-hibbs-mie",
        payload={
            **_build_repository_signal(
                "github:repo:science/feynman-hibbs-mie",
                query="feynman hibbs mie",
            ).payload,
            "repo": "science/feynman-hibbs-mie",
        },
    )
    description_signal = replace(
        _build_repository_signal(
            "github:repo:science/solver",
            query="feynman hibbs mie",
        ),
        title="science/solver",
        payload={
            **_build_repository_signal(
                "github:repo:science/solver",
                query="feynman hibbs mie",
            ).payload,
            "repo": "science/solver",
            "description": "Feynman-Hibbs Mie potential solver.",
        },
    )
    readme_signal = _build_repository_signal(
        "github:repo:science/readme-tool",
        query="feynman hibbs mie",
    )
    readme_signal = replace(
        readme_signal,
        title="science/readme-tool",
        payload={
            **readme_signal.payload,
            "repo": "science/readme-tool",
            "description": "",
            "matched_path": "README.md",
        },
    )
    code_signal = replace(
        readme_signal,
        item_id="github:repo:science/code-tool",
        title="science/code-tool",
        payload={
            **readme_signal.payload,
            "repo": "science/code-tool",
            "matched_path": "src/solver.cpp",
        },
    )
    documentation_signal = replace(
        readme_signal,
        item_id="github:repo:science/docs-tool",
        title="science/docs-tool",
        payload={
            **readme_signal.payload,
            "repo": "science/docs-tool",
            "matched_path": "docs/feynman_hibbs.md",
        },
    )

    candidates = merge_retrieval_hits(
        (
            _build_hit(
                source="github",
                channel="repository_search",
                query="feynman hibbs mie",
                rank=1,
                signal=name_signal,
            ),
            _build_hit(
                source="github",
                channel="repository_search",
                query="feynman hibbs mie",
                rank=1,
                signal=description_signal,
            ),
            _build_hit(
                source="github",
                channel="code_search",
                query="feynman hibbs mie",
                rank=1,
                signal=readme_signal,
            ),
            _build_hit(
                source="github",
                channel="code_search",
                query="feynman hibbs mie",
                rank=1,
                signal=code_signal,
            ),
            _build_hit(
                source="github",
                channel="code_search",
                query="feynman hibbs mie",
                rank=1,
                signal=documentation_signal,
            ),
        )
    )

    assert [
        candidate.provenance.match_evidence[0].location
        for candidate in candidates
    ] == ["name", "description", "readme", "code", "documentation"]


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


def test_run_external_repository_retrieval_retains_completed_code_queries_after_timeout() -> None:
    def discover_github_code_candidates(queries: tuple[str, ...]) -> list[Signal]:
        query = queries[0]
        if query == "timed out query":
            raise RepositorySourceError(
                source="github",
                status="timed_out",
                public_message="GitHub code search timed out right now.",
            )
        return [
            _build_repository_signal(
                f"github:repo:science/{query.replace(' ', '-')}",
                query=query,
            )
        ]

    retrieved = run_external_repository_retrieval(
        ("first query", "timed out query", "last query"),
        discoverers=(
            ("github", "code_search", discover_github_code_candidates),
        ),
    )

    assert [candidate.repository_id for candidate in retrieved.candidates] == [
        "github:repo:science/first-query",
        "github:repo:science/last-query",
    ]
    assert retrieved.partial is True
    assert retrieved.source_statuses == (
        {
            "source": "github",
            "status": "ok",
            "candidateCount": 2,
            "error": None,
        },
    )
    assert retrieved.warnings == (
        "GitHub code search returned timed_out for 1 query and retained results from 2 completed queries.",
    )


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
