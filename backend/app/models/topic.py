"""Research topic and profile models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResearchTopic:
    """User-facing research topic.

    V0 starts with manually written topics and later adds topic creation through
    the web layer.
    """

    slug: str
    label: str
    description: str = ""


@dataclass(frozen=True)
class ResearchProfile:
    """Backend research profile used for deterministic matching in V0.

    This shape is intentionally simple. It can later be populated by an LLM or
    edited through a UI without forcing changes in the matching layer.
    """

    topic_slug: str
    core_terms: tuple[str, ...] = ()
    synonyms: tuple[str, ...] = ()
    related_terms: tuple[str, ...] = ()
    negative_terms: tuple[str, ...] = ()
    seed_queries: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)
