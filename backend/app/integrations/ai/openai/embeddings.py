"""OpenAI embedding protocol and validated, ordered vector mapping."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isfinite

import httpx2 as httpx

from app.models.ai import AiConfigurationError, AiDependencyError, AiResponseError


@dataclass(frozen=True)
class OpenAiTextEmbedder:
    api_key: str = field(repr=False)
    base_url: str
    timeout_seconds: float
    model: str
    dimensions: int

    def __call__(self, inputs: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        if not inputs:
            return ()
        if not self.api_key:
            raise AiConfigurationError("Missing OPENAI_API_KEY for embeddings.")
        try:
            with httpx.Client(
                base_url=self.base_url.rstrip("/"), timeout=self.timeout_seconds,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            ) as client:
                response = client.post("/embeddings", json={"model": self.model, "input": list(inputs)})
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AiDependencyError(f"Embedding request failed with status {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise AiDependencyError("Embedding request could not be completed.") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise AiResponseError("Embedding response returned invalid JSON.") from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or len(data) != len(inputs):
            raise AiResponseError("Embedding response did not match the input batch.")
        vectors: dict[int, tuple[float, ...]] = {}
        for item in data:
            index = item.get("index") if isinstance(item, dict) else None
            vector = item.get("embedding") if isinstance(item, dict) else None
            if type(index) is not int or not 0 <= index < len(inputs) or index in vectors:
                raise AiResponseError("Embedding response used invalid or duplicate input indexes.")
            if not isinstance(vector, list) or len(vector) != self.dimensions:
                raise AiResponseError("Embedding response used an unexpected vector dimension.")
            if any(type(value) not in (int, float) for value in vector):
                raise AiResponseError("Embedding response contained invalid vector values.")
            try:
                converted = tuple(float(value) for value in vector)
            except (ValueError, OverflowError) as exc:
                raise AiResponseError("Embedding response contained invalid vector values.") from exc
            if not all(isfinite(value) for value in converted):
                raise AiResponseError("Embedding response contained invalid vector values.")
            vectors[index] = converted
        return tuple(vectors[index] for index in range(len(inputs)))
