"""Tests for source-agnostic semantic catalog candidates."""

from __future__ import annotations

from app import config
from app.models.repository import Repository
from app.services.search import semantic
import pytest


def test_semantic_retrieval_maps_historical_evidence_to_the_current_query(monkeypatch) -> None:
    monkeypatch.setattr(config, "SEMANTIC_CATALOG_ENABLED", True)
    monkeypatch.setattr(semantic, "semantic_catalog_is_available", lambda **_: True)
    monkeypatch.setattr(semantic, "_embed_texts", lambda _: ((0.1, 0.2),))
    monkeypatch.setattr(
        semantic,
        "find_semantic_query_evidence",
        lambda *_, **__: [
            {
                "repository_id": "github:repo:123",
                "query_normalized": "paramagnetic nmr fitting",
                "channel": "code_search",
                "match_location": "readme",
                "matched_path": "README.md",
                "provider_rank": 4,
                "hit_count": 1,
                "similarity": 0.82,
            }
        ],
    )
    monkeypatch.setattr(semantic, "find_semantic_profiles", lambda *_, **__: [])
    monkeypatch.setattr(
        semantic,
        "list_repositories_by_ids",
        lambda *_, **__: [
            Repository(
                repository_id="github:repo:123",
                source="github",
                full_name="Mephistos-ML/paranmr",
                url="https://github.com/Mephistos-ML/paranmr",
                description="Paramagnetic NMR fitting toolkit.",
            )
        ],
    )

    candidates = semantic.retrieve_semantic_catalog_candidates(
        ("PCS tensor estimation",),
        database_url="postgresql://example.test/sciscope",
    )

    evidence = candidates[0].provenance.match_evidence[0]
    assert candidates[0].provenance.matched_queries == ("pcs tensor estimation",)
    assert evidence.query == "pcs tensor estimation"
    assert evidence.location == "readme"
    assert evidence.path == "README.md"
    assert evidence.alignment == 0.82


def test_backfill_propagates_embedding_errors(monkeypatch) -> None:
    monkeypatch.setattr(semantic, "list_repositories", lambda **_: [])
    monkeypatch.setattr(semantic, "list_repository_search_evidence", lambda **_: [])
    monkeypatch.setattr(
        semantic,
        "persist_semantic_catalog_documents",
        lambda *_, **__: (_ for _ in ()).throw(semantic.SemanticEmbeddingError("forbidden")),
    )

    with pytest.raises(semantic.SemanticEmbeddingError, match="forbidden"):
        semantic.backfill_semantic_catalog(database_url="postgresql://example.test/sciscope")


def test_profile_text_bounds_provider_metadata(monkeypatch) -> None:
    monkeypatch.setattr(config, "SEMANTIC_EMBEDDING_MAX_INPUT_CHARS", 30)
    repository = Repository(
        repository_id="github:repo:123",
        source="github",
        full_name="owner/repository",
        url="https://github.com/owner/repository",
        description="A description that is longer than the embedding document budget.",
    )

    assert semantic._profile_text(repository) == "owner/repository\nA description"


def test_document_batches_respect_item_and_character_limits(monkeypatch) -> None:
    monkeypatch.setattr(config, "SEMANTIC_EMBEDDING_BATCH_SIZE", 3)
    monkeypatch.setattr(config, "SEMANTIC_EMBEDDING_BATCH_MAX_CHARS", 10)

    batches = semantic._document_batches(
        {"first": "aaaaaa", "second": "bbbbbb", "third": "cc", "fourth": "dd"}
    )

    assert batches == (
        (("first", "aaaaaa"),),
        (("second", "bbbbbb"), ("third", "cc"), ("fourth", "dd")),
    )
