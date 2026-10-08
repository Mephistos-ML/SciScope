"""Exercise real pgvector operators, model isolation, upserts and batch rollback."""

from hashlib import sha256

import pytest

from app.models.persistence import PersistenceError
from app.storage.repositories import semantic

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("kind", ["profile", "query"])
def test_vector_cache_invalidates_changed_content_and_models(postgres_url, kind):
    upsert = semantic.upsert_profile_embeddings if kind == "profile" else semantic.upsert_query_embeddings
    missing = semantic.filter_missing_profile_embeddings if kind == "profile" else semantic.filter_missing_query_embeddings
    vector = [1.0, *([0.0] * 1535)]
    content_hash = sha256(b"original").hexdigest()
    upsert({"first": (content_hash, vector)}, embedding_model="model-a", database_url=postgres_url)
    assert missing({"first": "original", "second": "new"}, embedding_model="model-a", database_url=postgres_url) == {"second": "new"}
    assert missing({"first": "changed"}, embedding_model="model-a", database_url=postgres_url) == {"first": "changed"}
    assert missing({"first": "original"}, embedding_model="model-b", database_url=postgres_url) == {"first": "original"}
    # The first valid row must roll back when a later vector violates dimensions.
    with pytest.raises(PersistenceError):
        upsert({"second": (content_hash, vector), "invalid": (content_hash, [1.0])},
               embedding_model="model-a", database_url=postgres_url)
    assert missing({"second": "original"}, embedding_model="model-a", database_url=postgres_url) == {"second": "original"}


def test_cosine_retrieval_honors_threshold_model_and_updated_vectors(postgres_url):
    first = [1.0, *([0.0] * 1535)]
    orthogonal = [0.0, 1.0, *([0.0] * 1534)]
    semantic.upsert_profile_embeddings({"near": ("hash", first), "far": ("hash", orthogonal)},
                                       embedding_model="model-a", database_url=postgres_url)
    def retrieve(model="model-a"):
        return semantic.find_semantic_profiles(first, embedding_model=model, limit=1,
                                              min_similarity=0.9, database_url=postgres_url)
    assert retrieve() == [{"repository_id": "near", "similarity": pytest.approx(1.0)}]
    assert retrieve("model-b") == []
    semantic.upsert_profile_embeddings({"near": ("new-hash", orthogonal)},
                                       embedding_model="model-a", database_url=postgres_url)
    assert retrieve() == []


def test_injected_semantic_capability_ingests_and_retrieves_after_global_disable(postgres_url, monkeypatch):
    from app import config
    from app.composition.repositories import build_repository_adapters
    from app.composition.search import build_explore_dependencies
    from app.integrations.ai.openai.embeddings import OpenAiTextEmbedder
    from app.models.repository import Repository
    from app.services.search import semantic as application
    from app.storage.repositories.repositories import upsert_repositories

    calls = []
    def embed(self, inputs):
        calls.append(tuple(inputs))
        return tuple((1.0, *([0.0] * 1535)) for _ in inputs)
    monkeypatch.setattr(OpenAiTextEmbedder, "__call__", embed)
    monkeypatch.setattr(config, "SEMANTIC_CATALOG_ENABLED", True)
    selected = build_explore_dependencies(repositories=build_repository_adapters()).embeddings
    assert selected is not None
    monkeypatch.setattr(config, "SEMANTIC_CATALOG_ENABLED", False)
    repository = Repository("github:repo:123", "github", "science/tool", "https://github.com/science/tool", {})
    upsert_repositories((repository,), database_url=postgres_url)
    application.persist_semantic_catalog_documents((repository,), ("Scientific query",),
        embeddings=selected, database_url=postgres_url)
    assert len(calls) == 2
    application.persist_semantic_catalog_documents((repository,), ("Scientific query",),
        embeddings=selected, database_url=postgres_url)
    assert len(calls) == 2
    candidates = application.retrieve_semantic_catalog_candidates(("Scientific query",),
        embeddings=selected, database_url=postgres_url)
    assert len(calls) == 3
    assert [candidate.repository_id for candidate in candidates] == [repository.repository_id]
    assert candidates[0].provenance.matched_queries == ("scientific query",)
    assert candidates[0].provenance.match_evidence[0].alignment == pytest.approx(1.0)
