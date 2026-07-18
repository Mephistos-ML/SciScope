"""GitHub repository discovery and entity admission."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from urllib.parse import quote_plus

from app.models.discovery import DiscoveryResult
from app.models.entity import Entity, TopicEntityMatch
from app.models.signal import RawSignal
from app.models.topic import ResearchProfile
from app.sources.github.client import GITHUB_API_BASE, fetch_json
from app.sources.github.query_builder import build_repository_search_queries
from app.services.matching import match_signal_to_profile
from app.services.normalization import normalize_raw_signal
from app.storage.entities import upsert_entities, upsert_topic_entity_matches
from app.storage.seen_signals import DB_PATH


def discover_repository_candidates(
    queries: Sequence[str],
    *,
    per_query_limit: int = 5,
) -> list[RawSignal]:
    """Search GitHub repositories for topic-derived queries."""

    signals: list[RawSignal] = []
    for query in queries:
        search_url = _build_repository_search_url(query, per_query_limit=per_query_limit)
        payload = fetch_json(search_url)
        if not isinstance(payload, dict):
            continue

        items = payload.get("items")
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            full_name = str(item.get("full_name") or "").strip()
            if not full_name:
                continue

            description = str(item.get("description") or "")
            topics = item.get("topics")
            topic_list = [str(value) for value in topics] if isinstance(topics, list) else []
            language = str(item.get("language") or "")
            stars = int(item.get("stargazers_count") or 0)
            owner = item.get("owner")
            owner_login = ""
            if isinstance(owner, dict):
                owner_login = str(owner.get("login") or "")

            signals.append(
                RawSignal(
                    source="github",
                    source_type="github_repository",
                    item_id=f"github:repo:{full_name}",
                    title=full_name,
                    url=str(item.get("html_url") or f"https://github.com/{full_name}"),
                    published_at=None,
                    raw_text=_build_repository_text(
                        full_name=full_name,
                        description=description,
                        topics=topic_list,
                        language=language,
                    ),
                    payload={
                        "signal_kind": "github_repository",
                        "repo": full_name,
                        "author": owner_login,
                        "topics": topic_list,
                        "language": language,
                        "stars": stars,
                        "query": query,
                    },
                )
            )

    return signals


def discover_github_entities_for_profile(
    profile: ResearchProfile,
    *,
    db_path: Path = DB_PATH,
) -> DiscoveryResult:
    """Discover GitHub repositories relevant to one research profile."""

    queries = build_repository_search_queries(profile)
    candidates = discover_repository_candidates(queries)

    deduped_candidates = _dedupe_repository_candidates(candidates)
    entities: list[Entity] = []
    matches: list[TopicEntityMatch] = []

    for raw_signal in deduped_candidates.values():
        normalized_signal = normalize_raw_signal(raw_signal)
        match = match_signal_to_profile(normalized_signal, profile)

        if not match.matched:
            continue

        repo_name = str(raw_signal.payload.get("repo") or raw_signal.title)
        entities.append(
            Entity(
                entity_id=raw_signal.item_id,
                source=raw_signal.source,
                entity_type="repository",
                canonical_name=repo_name,
                url=raw_signal.url,
                metadata={
                    "repo": repo_name,
                    "query": raw_signal.payload.get("query"),
                    "topics": raw_signal.payload.get("topics", []),
                    "language": raw_signal.payload.get("language"),
                    "stars": raw_signal.payload.get("stars"),
                },
            )
        )
        matches.append(
            TopicEntityMatch(
                topic_slug=profile.topic_slug,
                entity_id=raw_signal.item_id,
                source=raw_signal.source,
                matched_terms=match.matched_terms,
                excluded_terms=match.excluded_terms,
                score=match.score,
                active=True,
                reason=match.reason,
                metadata={
                    "repo": repo_name,
                    "query": raw_signal.payload.get("query"),
                },
            )
        )

    upsert_entities(entities, db_path=db_path)
    upsert_topic_entity_matches(matches, db_path=db_path)

    return DiscoveryResult(
        topic_slug=profile.topic_slug,
        queries=queries,
        candidate_count=len(candidates),
        entity_count=len(entities),
        matched_entity_count=len(matches),
    )


def _build_repository_search_url(query: str, *, per_query_limit: int) -> str:
    encoded_query = quote_plus(query)
    return (
        f"{GITHUB_API_BASE}/search/repositories"
        f"?q={encoded_query}&sort=updated&order=desc&per_page={per_query_limit}"
    )


def _dedupe_repository_candidates(
    candidates: list[RawSignal],
) -> dict[str, RawSignal]:
    deduped: dict[str, RawSignal] = {}
    for signal in candidates:
        existing = deduped.get(signal.item_id)
        if existing is None:
            deduped[signal.item_id] = signal
            continue

        existing_query = str(existing.payload.get("query") or "")
        incoming_query = str(signal.payload.get("query") or "")
        if len(incoming_query) > len(existing_query):
            deduped[signal.item_id] = signal

    return deduped


def _build_repository_text(
    *,
    full_name: str,
    description: str,
    topics: Sequence[str],
    language: str,
) -> str:
    parts: list[str] = [full_name, description]
    if topics:
        parts.append(" ".join(topic.strip() for topic in topics if topic.strip()))
    if language.strip():
        parts.append(language.strip())
    return "\n".join(part.strip() for part in parts if part.strip())
