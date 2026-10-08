"""Embedding capability used by catalog application policy."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class TextEmbedder(Protocol):
    def __call__(self, inputs: Sequence[str]) -> tuple[tuple[float, ...], ...]: ...


@dataclass(frozen=True)

class EmbeddingProvider:
    model: str
    embed: TextEmbedder
