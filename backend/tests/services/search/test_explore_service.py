"""Explore application policy with real ranking, catalog and durable worker execution."""

from dataclasses import replace
import pytest
from app.models.signal import Signal
from app.models.ai import AiSearchPlan
from app.models.explore_access import ExploreActor, ExploreAdmission, ExploreTier
from app.services.ai.planner import AiSearchPlanner, AiPlannerIdentity
from app.services.search.explore.dependencies import ExploreDependencies
from app.services.search.explore.service import run_explore_search
from app.services.search.explore.jobs import create_explore_search_run
from app.jobs.process_search_runs import process_next_search_run_operation
from app.storage.search_runs import get_search_run
from app.services.search.retrieval.models import (
    CandidateProvenance,
    RepositoryCandidate,
    RetrievalMatchEvidence,
    RetrievedCandidates,
)
from tests.fixtures.database import build_test_database_url, migrate_test_database
from tests.fixtures.explore import (
    build_ready_repository_ai_plan,
    build_explore_repository_signal,
    build_code_only_explore_repository_signal,
    build_retrieved_candidates,
)


@pytest.fixture
def database_url(tmp_path):
    url = build_test_database_url(tmp_path / "explore.sqlite3")
    migrate_test_database(url)
    return url


@pytest.fixture
def dependencies():
    return ExploreDependencies(
        AiSearchPlanner(
            lambda **kwargs: AiSearchPlan("pending", ()),
            AiPlannerIdentity("bootstrap", None, None),
        ),
        (),
        None,
    )


def test_explore_search_returns_partial_results_when_one_source_fails(
    monkeypatch, database_url, dependencies
) -> None:
    dependencies = replace(
        dependencies,
        planner=replace(
            dependencies.planner,
            build_search_plan=lambda topic_description: build_ready_repository_ai_plan(
                "paramagnetic nmr"
            ),
        ),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda queries, **kwargs: build_retrieved_candidates(
            build_explore_repository_signal(
                "github:repo:102",
                query=queries[0],
            ),
            source_statuses=(
                {
                    "source": "github",
                    "status": "ok",
                    "candidateCount": 1,
                    "error": None,
                },
                {
                    "source": "gitlab",
                    "status": "unauthorized",
                    "candidateCount": 0,
                    "error": "GitLab auth failed.",
                },
            ),
            successful_source_count=1,
        ),
    )

    payload = run_explore_search(
        topic_description="Paramagnetic NMR analysis workflows",
        dependencies=dependencies,
        database_url=database_url,
    )

    assert len(payload["items"]) == 1
    assert payload["aiSearchPlan"] == {"status": "ready", "queries": []}
    assert payload["sourceStatuses"][0]["source"] == "github"
    assert payload["sourceStatuses"][1]["status"] == "unauthorized"


def test_explore_search_refreshes_external_candidates_after_a_strong_catalog_match(
    monkeypatch,
    database_url,
    dependencies,
) -> None:
    query = "paramagnetic nmr"
    dependencies = replace(
        dependencies,
        planner=replace(
            dependencies.planner,
            build_search_plan=lambda topic_description: build_ready_repository_ai_plan(
                query
            ),
        ),
    )
    local_candidates = build_retrieved_candidates(
        *(
            build_explore_repository_signal(
                f"github:repo:{1000 + index}",
                query=query,
            )
            for index in range(10)
        ),
        source_statuses=(),
        successful_source_count=1,
    ).candidates
    monkeypatch.setattr(
        "app.services.search.explore.service.retrieve_catalog_candidates",
        lambda *_, **__: local_candidates,
    )
    external_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda queries, **kwargs: (
            external_calls.append(queries)
            or build_retrieved_candidates(
                build_explore_repository_signal(
                    "github:repo:2000",
                    query=queries[0],
                ),
                source_statuses=(
                    {
                        "source": "github",
                        "status": "ok",
                        "candidateCount": 1,
                        "error": None,
                    },
                ),
                successful_source_count=1,
            )
        ),
    )

    run_explore_search(
        topic_description="Paramagnetic NMR analysis workflows",
        dependencies=dependencies,
        database_url=database_url,
    )

    assert external_calls == [(query,)]


def test_explore_search_keeps_retrieved_candidate_without_literal_query_phrase(
    monkeypatch,
    database_url,
    dependencies,
) -> None:
    query = "LAMMPS Feynman-Hibbs"
    dependencies = replace(
        dependencies,
        planner=replace(
            dependencies.planner,
            build_search_plan=lambda topic_description: build_ready_repository_ai_plan(
                query
            ),
        ),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda queries, **kwargs: RetrievedCandidates(
            candidates=(
                RepositoryCandidate(
                    repository_id="github:repo:115",
                    signal=build_code_only_explore_repository_signal(
                        "github:repo:115",
                        query=queries[0],
                    ),
                    provenance=CandidateProvenance(
                        matched_queries=(queries[0],),
                        matched_channels=("code_search",),
                        best_rank_by_channel={"code_search": 1},
                        hit_count=1,
                        match_evidence=(
                            RetrievalMatchEvidence(
                                query=queries[0],
                                location="code",
                                path="src/pair_mie_fh.cpp",
                            ),
                        ),
                    ),
                ),
            ),
            source_statuses=(
                {
                    "source": "github",
                    "status": "ok",
                    "candidateCount": 1,
                    "error": None,
                },
            ),
            successful_source_count=1,
        ),
    )

    payload = run_explore_search(
        topic_description="LAMMPS extension for Feynman-Hibbs corrected Mie pair potentials",
        dependencies=dependencies,
        database_url=database_url,
    )

    assert len(payload["items"]) == 1
    assert payload["items"][0]["itemId"] == "github:repo:115"
    assert payload["items"][0]["score"] >= 50.0


def test_explore_search_applies_ranking_order_and_relevance_cutoff(
    monkeypatch, database_url, dependencies
) -> None:
    queries = (
        "lammps feynman-hibbs",
        "feynman-hibbs mie potential",
        "quantum-corrected mie potential",
        "lammps pair style mie",
        "semiclassical correction",
    )
    dependencies = replace(
        dependencies,
        planner=replace(
            dependencies.planner,
            build_search_plan=lambda topic_description: build_ready_repository_ai_plan(
                *queries
            ),
        ),
    )
    top_signal = build_explore_repository_signal(
        "github:repo:108",
        query=queries[0],
    )
    top_signal = Signal(
        source=top_signal.source,
        kind=top_signal.kind,
        item_id=top_signal.item_id,
        title="science/feynman-hibbs-mie",
        url=top_signal.url,
        published_at=top_signal.published_at,
        raw_text=top_signal.raw_text,
        payload=top_signal.payload,
    )
    metadata_signal = build_explore_repository_signal(
        "github:repo:110",
        query=queries[0],
    )
    weak_signal = build_explore_repository_signal(
        "github:repo:109",
        query=queries[0],
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda _queries, **kwargs: build_retrieved_candidates(
            top_signal,
            metadata_signal,
            weak_signal,
            source_statuses=(
                {
                    "source": "github",
                    "status": "ok",
                    "candidateCount": 3,
                    "error": None,
                },
            ),
            successful_source_count=1,
            match_locations=("name", "description", "other"),
        ),
    )

    payload = run_explore_search(
        topic_description="LAMMPS Feynman-Hibbs Mie potential",
        dependencies=dependencies,
        database_url=database_url,
    )

    assert [item["itemId"] for item in payload["items"]] == [
        top_signal.item_id,
        metadata_signal.item_id,
    ]


def test_explore_search_enforced_mode_hides_rejected_candidates(
    monkeypatch, database_url, dependencies
) -> None:
    monkeypatch.setattr(
        "app.services.search.admission.service.EXPLORE_ADMISSION_MODE",
        "enforced",
    )
    dependencies = replace(
        dependencies,
        planner=replace(
            dependencies.planner,
            build_search_plan=lambda topic_description: build_ready_repository_ai_plan(
                "orca parser"
            ),
        ),
    )
    weak_signal = Signal(
        source="github",
        kind="repository",
        item_id="github:repo:101",
        title="HeinrichHartmann/arxiv_meta",
        url="https://github.com/HeinrichHartmann/arxiv_meta",
        published_at=None,
        raw_text="HeinrichHartmann/arxiv_meta\nArxiv metadata mirror.",
        payload={
            "repo": "HeinrichHartmann/arxiv_meta",
            "query": "orca parser",
            "topics": ["metadata"],
            "language": "",
            "stars": 0,
        },
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda queries, **kwargs: build_retrieved_candidates(
            build_code_only_explore_repository_signal(
                "github:repo:115",
                query=queries[0],
            ),
            weak_signal,
            source_statuses=(
                {
                    "source": "github",
                    "status": "ok",
                    "candidateCount": 2,
                    "error": None,
                },
            ),
            successful_source_count=1,
        ),
    )

    payload = run_explore_search(
        topic_description="A python package for working with Orca.",
        dependencies=dependencies,
        database_url=database_url,
    )

    assert len(payload["items"]) == 1
    assert payload["items"][0]["itemId"] == "github:repo:115"
    assert "admission" not in payload


def test_explore_search_retries_timeouts_before_advancing_to_next_query(
    monkeypatch, database_url, dependencies
) -> None:
    dependencies = replace(
        dependencies,
        planner=replace(
            dependencies.planner,
            build_search_plan=lambda topic_description: build_ready_repository_ai_plan(
                "primary query",
                "fallback query",
                "final query",
            ),
        ),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.retrieve_catalog_candidates",
        lambda *_, **__: (),
    )
    attempted_queries: list[str] = []

    def _retrieve(queries, **_kwargs):
        query = queries[0]
        attempted_queries.append(query)
        if query == "primary query":
            return build_retrieved_candidates(
                source_statuses=(
                    {
                        "source": "github",
                        "status": "timed_out",
                        "candidateCount": 0,
                        "error": "GitHub search timed out.",
                    },
                ),
                successful_source_count=0,
                partial=True,
                warnings=("GitHub search timed out.",),
            )
        return build_retrieved_candidates(
            build_explore_repository_signal(
                "github:repo:107",
                query=query,
            ),
            source_statuses=(
                {
                    "source": "github",
                    "status": "ok",
                    "candidateCount": 1,
                    "error": None,
                },
            ),
            successful_source_count=1,
        )

    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        _retrieve,
    )

    payload = run_explore_search(
        topic_description="Fallback workflow",
        dependencies=dependencies,
        database_url=database_url,
    )

    assert payload["items"][0]["itemId"] == "github:repo:107"
    assert payload["canExpand"] is True
    assert attempted_queries == [
        "primary query",
        "primary query",
        "primary query",
        "fallback query",
    ]


def test_explore_search_retries_partial_timeouts_and_merges_attempt_results(
    monkeypatch, database_url, dependencies
) -> None:
    dependencies = replace(
        dependencies,
        planner=replace(
            dependencies.planner,
            build_search_plan=lambda topic_description: build_ready_repository_ai_plan(
                "primary query",
                "fallback query",
            ),
        ),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.retrieve_catalog_candidates",
        lambda *_, **__: (),
    )
    attempted_queries: list[str] = []
    attempt_results = iter(
        (
            build_retrieved_candidates(
                build_explore_repository_signal(
                    "github:repo:112",
                    query="primary query",
                ),
                source_statuses=(
                    {
                        "source": "github",
                        "status": "ok",
                        "candidateCount": 1,
                        "error": None,
                    },
                ),
                successful_source_count=1,
                partial=True,
                warnings=("GitHub search timed out after partial results.",),
            ),
            build_retrieved_candidates(
                build_explore_repository_signal(
                    "github:repo:113",
                    query="primary query",
                ),
                source_statuses=(
                    {
                        "source": "github",
                        "status": "ok",
                        "candidateCount": 1,
                        "error": None,
                    },
                ),
                successful_source_count=1,
                partial=True,
                warnings=("GitHub search timed out after partial results.",),
            ),
            build_retrieved_candidates(
                build_explore_repository_signal(
                    "github:repo:106",
                    query="primary query",
                ),
                source_statuses=(
                    {
                        "source": "github",
                        "status": "ok",
                        "candidateCount": 1,
                        "error": None,
                    },
                ),
                successful_source_count=1,
            ),
        )
    )

    def _retrieve(queries, **_kwargs):
        attempted_queries.append(queries[0])
        return next(attempt_results)

    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        _retrieve,
    )

    payload = run_explore_search(
        topic_description="Partial timeout workflow",
        dependencies=dependencies,
        database_url=database_url,
    )

    assert attempted_queries == ["primary query", "primary query", "primary query"]
    assert {item["itemId"] for item in payload["items"]} == {
        "github:repo:112",
        "github:repo:113",
        "github:repo:106",
    }


def test_explore_search_run_fails_after_all_timeout_retries_are_exhausted(
    monkeypatch, database_url, dependencies
) -> None:
    dependencies = replace(
        dependencies,
        planner=replace(
            dependencies.planner,
            build_search_plan=lambda topic_description: build_ready_repository_ai_plan(
                "primary query",
                "fallback query",
                "final query",
            ),
        ),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.retrieve_catalog_candidates",
        lambda *_, **__: (),
    )
    attempted_queries: list[str] = []

    def _retrieve(queries, **_kwargs):
        attempted_queries.append(queries[0])
        return build_retrieved_candidates(
            source_statuses=(
                {
                    "source": "github",
                    "status": "timed_out",
                    "candidateCount": 0,
                    "error": "GitHub search timed out.",
                },
            ),
            successful_source_count=0,
            partial=True,
            warnings=("GitHub search timed out.",),
        )

    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        _retrieve,
    )

    created = create_explore_search_run(
        topic_description="Exhausted timeout workflow",
        admission=ExploreAdmission(
            ExploreActor(ExploreTier.GUEST, "guest_ip", "application-test"),
            bypass_quota=True,
        ),
        database_url=database_url,
        dependencies=dependencies,
    )
    assert process_next_search_run_operation(
        worker_id="test-worker",
        database_url=database_url,
        dependencies=dependencies,
    )
    run = get_search_run(created["runId"], database_url=database_url)

    assert run.status == "failed"
    assert (
        run.error_message
        == "Repository search is temporarily unavailable across all providers."
    )
    assert attempted_queries == [
        "primary query",
        "primary query",
        "primary query",
        "fallback query",
        "fallback query",
        "fallback query",
        "final query",
        "final query",
        "final query",
    ]
