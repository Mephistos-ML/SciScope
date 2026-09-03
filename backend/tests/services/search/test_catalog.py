"""Tests for catalog ingestion and local retrieval."""

from __future__ import annotations

from app.models.signal import Signal
from app.services.search.catalog import (
    persist_catalog_candidates,
    retrieve_catalog_candidates,
)
from app.services.search.retrieval import (
    CandidateProvenance,
    RepositoryCandidate,
    RetrievalMatchEvidence,
)
from tests.conftest import build_test_database_url, migrate_test_database


def test_catalog_retrieval_keeps_query_specific_evidence(tmp_path) -> None:
    database_url = build_test_database_url(tmp_path / "catalog.sqlite3")
    migrate_test_database(database_url)
    candidate = RepositoryCandidate(
        repository_id="github:repo:123",
        signal=Signal(
            source="github",
            kind="repository",
            item_id="github:repo:123",
            title="Mephistos-ML/paranmr",
            url="https://github.com/Mephistos-ML/paranmr",
            published_at=None,
            raw_text="Paramagnetic NMR fitting toolkit.",
            payload={
                "repo": "Mephistos-ML/paranmr",
                "provider_repository_id": "123",
                "author": "Mephistos-ML",
                "description": "Paramagnetic NMR fitting toolkit.",
                "language": "Python",
                "topics": ["paramagnetic-nmr"],
                "stars": 14,
                "provider_updated_at": "2026-09-03T12:30:00+00:00",
                "matched_excerpt": "Fits paramagnetic relaxation rates.",
            },
        ),
        provenance=CandidateProvenance(
            matched_queries=("paramagnetic nmr", "paramagnetic relaxation"),
            matched_channels=("repository_search", "code_search"),
            best_rank_by_channel={"repository_search": 1, "code_search": 3},
            hit_count=2,
            match_evidence=(
                RetrievalMatchEvidence(
                    query="paramagnetic nmr",
                    location="description",
                ),
                RetrievalMatchEvidence(
                    query="paramagnetic relaxation",
                    location="code",
                    path="paranmr/relaxation.py",
                ),
            ),
        ),
    )
    persist_catalog_candidates((candidate,), database_url=database_url)

    pnmr = retrieve_catalog_candidates(("paramagnetic nmr",), database_url=database_url)
    relaxation = retrieve_catalog_candidates(("relaxation",), database_url=database_url)

    assert pnmr[0].repository_id == "github:repo:123"
    assert pnmr[0].signal.payload["query"] == "paramagnetic nmr"
    assert pnmr[0].signal.payload["provider_updated_at"] == "2026-09-03T12:30:00+00:00"
    assert pnmr[0].provenance.match_evidence[0].location == "description"
    assert relaxation[0].provenance.matched_queries == ("relaxation",)
    assert relaxation[0].provenance.match_evidence[0].location == "code"
    assert relaxation[0].provenance.match_evidence[0].path == "paranmr/relaxation.py"
