"""Embedding responses must preserve input identity and reject unusable vectors."""

import httpx2 as httpx
import pytest

from app.integrations.ai.openai.embeddings import OpenAiTextEmbedder
from app.models.ai import AiDependencyError, AiResponseError


def embedder():
    return OpenAiTextEmbedder("secret-key", "https://example.test/v1", 2, "test-model", 2)


def respond(monkeypatch, payload, status=200):
    monkeypatch.setattr(httpx.Client, "post", lambda *args, **kwargs: httpx.Response(
        status, json=payload, request=httpx.Request("POST", "https://example.test/v1/embeddings"),
    ))


def test_vectors_follow_input_indexes_instead_of_response_order(monkeypatch):
    respond(monkeypatch, {"data": [
        {"index": 1, "embedding": [3, 4]}, {"index": 0, "embedding": [1, 2]},
    ]})
    assert embedder()(("first", "second")) == ((1.0, 2.0), (3.0, 4.0))
    assert "secret-key" not in repr(embedder())


@pytest.mark.parametrize("data", [
    [],
    [{"index": 0, "embedding": [1, 2]}, {"index": 0, "embedding": [3, 4]}],
    [{"index": 2, "embedding": [1, 2]}, {"index": 1, "embedding": [3, 4]}],
    [{"index": False, "embedding": [1, 2]}, {"index": 1, "embedding": [3, 4]}],
    [{"index": 0, "embedding": [1]}, {"index": 1, "embedding": [3, 4]}],
    [{"index": 0, "embedding": [True, 2]}, {"index": 1, "embedding": [3, 4]}],
    [{"index": 0, "embedding": ["1", 2]}, {"index": 1, "embedding": [3, 4]}],
])
def test_invalid_vectors_cannot_enter_catalog(monkeypatch, data):
    respond(monkeypatch, {"data": data})
    with pytest.raises(AiResponseError):
        embedder()(("first", "second"))


def test_nonfinite_vector_is_rejected(monkeypatch):
    monkeypatch.setattr(httpx.Response, "json", lambda _: {"data": [{"index": 0, "embedding": [float("nan"), 2]}]})
    respond(monkeypatch, {})
    with pytest.raises(AiResponseError):
        embedder()(("first",))


@pytest.mark.parametrize("status", [401, 429, 503])
def test_http_failure_is_safe_and_preserves_cause(monkeypatch, status):
    respond(monkeypatch, {"error": "secret-key private provider diagnostics"}, status)
    with pytest.raises(AiDependencyError) as failure:
        embedder()(("first",))
    assert str(status) in str(failure.value)
    assert "secret-key" not in str(failure.value)
    assert isinstance(failure.value.__cause__, httpx.HTTPStatusError)


def test_timeout_translates_at_adapter_boundary(monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ReadTimeout("private diagnostics")
    monkeypatch.setattr(httpx.Client, "post", fail)
    with pytest.raises(AiDependencyError) as failure:
        embedder()(("first",))
    assert isinstance(failure.value.__cause__, httpx.ReadTimeout)


def test_invalid_json_translates_at_adapter_boundary(monkeypatch):
    monkeypatch.setattr(httpx.Client, "post", lambda *args, **kwargs: httpx.Response(
        200, text="not json", request=httpx.Request("POST", "https://example.test"),
    ))
    with pytest.raises(AiResponseError):
        embedder()(("first",))
