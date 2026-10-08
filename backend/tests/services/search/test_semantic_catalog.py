"""Tests for source-agnostic semantic catalog candidates."""

from __future__ import annotations

from app import config
from app.services.ai.embeddings import EmbeddingProvider
from app.models.ai import AiDependencyError
from app.models.repository import Repository
from app.services.search import semantic
import pytest


def test_semantic_retrieval_maps_historical_evidence_to_the_current_query(monkeypatch) -> None:
    monkeypatch.setattr(semantic, "semantic_catalog_is_available", lambda **_: True)
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
        embeddings=EmbeddingProvider("test-model", lambda _: ((0.1, 0.2),)),
        database_url="postgresql://example.test/sciscope",
    )

    evidence = candidates[0].provenance.match_evidence[0]
    assert candidates[0].provenance.matched_queries == ("pcs tensor estimation",)
    assert evidence.query == "pcs tensor estimation"
    assert evidence.location == "readme"
    assert evidence.path == "README.md"
    assert evidence.alignment == 0.82
    assert evidence.channel == "semantic_catalog"
    assert evidence.origin == "catalog"
    assert evidence.retrieval_rank == 1


def test_backfill_propagates_embedding_errors(monkeypatch) -> None:
    monkeypatch.setattr(semantic, "list_repositories", lambda **_: [])
    monkeypatch.setattr(semantic, "list_repository_search_evidence", lambda **_: [])
    monkeypatch.setattr(
        semantic,
        "persist_semantic_catalog_documents",
        lambda *_, **__: (_ for _ in ()).throw(AiDependencyError("forbidden")),
    )

    with pytest.raises(AiDependencyError, match="forbidden"):
        semantic.backfill_semantic_catalog(embeddings=EmbeddingProvider("test", lambda _: ()), database_url="postgresql://example.test/sciscope")


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


def test_unavailable_embeddings_preserve_lexical_catalog_results(monkeypatch):
    from app.services.search import catalog
    from app.models.repository import CatalogRepositoryMatch
    monkeypatch.setattr(semantic, "semantic_catalog_is_available", lambda **_: True)
    repository = Repository("github:repo:123", "github", "owner/science", "https://example.test/science")
    monkeypatch.setattr(catalog, "find_catalog_repository_matches", lambda *args, **kwargs: (
        CatalogRepositoryMatch(repository, ("scientific query",), ()),
    ))

    def fail(inputs):
        raise AiDependencyError("Embedding dependency unavailable.")

    candidates = catalog.retrieve_catalog_candidates(
        ("scientific query",), database_url="unused",
        embeddings=EmbeddingProvider("test-model", fail),
    )
    assert tuple(candidate.repository_id for candidate in candidates) == (repository.repository_id,)
    assert candidates[0].provenance.origins == ("catalog",)


def test_failed_embedding_batch_does_not_write_partial_vectors(monkeypatch):
    monkeypatch.setattr(semantic, "semantic_catalog_is_available", lambda **_: True)
    monkeypatch.setattr(config, "SEMANTIC_EMBEDDING_BATCH_SIZE", 1)
    monkeypatch.setattr(semantic, "filter_missing_query_embeddings", lambda documents, **kwargs: documents)
    writes = []
    monkeypatch.setattr(semantic, "upsert_query_embeddings", lambda *args, **kwargs: writes.append(args))
    calls = []

    def embed(inputs):
        calls.append(inputs)
        if len(calls) == 2:
            raise AiDependencyError("unavailable")
        return ((1.0, 2.0),)

    with pytest.raises(AiDependencyError):
        semantic.persist_semantic_catalog_documents(
            (), ("first", "second"), database_url="unused", raise_on_error=True,
            embeddings=EmbeddingProvider("test-model", embed),
        )
    assert len(calls) == 2
    assert writes == []


@pytest.mark.parametrize("operation", ["persist", "retrieve"])
def test_absent_capability_skips_embedding_and_database_io(monkeypatch, operation):
    monkeypatch.setattr(config, "SEMANTIC_CATALOG_ENABLED", True)
    def unexpected(**kwargs):
        pytest.fail("Disabled semantic operations must not access persistence")
    monkeypatch.setattr(semantic, "semantic_catalog_is_available", unexpected)
    if operation == "persist":
        semantic.persist_semantic_catalog_documents((), ("query",), database_url="unused", embeddings=None)
    else:
        assert semantic.retrieve_semantic_catalog_candidates(("query",), database_url="unused", embeddings=None) == ()
