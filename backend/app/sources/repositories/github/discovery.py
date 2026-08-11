"""GitHub repository discovery and entity admission."""

from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import quote_plus

from app.config import DATABASE_URL
from app.models.discovery import DiscoveryResult
from app.models.signal import RawSignal
from app.models.topic import ResearchProfile
from app.services.matching import match_signal_to_profile
from app.services.normalization import normalize_raw_signal
from app.sources.repositories.common import (
    RepositoryCandidate,
    build_repository_candidate_signal,
    build_repository_entity,
    build_repository_subscription_match,
)
from app.sources.repositories.common.query_builder import (
    build_repository_search_queries,
)
from app.sources.repositories.github.client import GITHUB_API_BASE, fetch_json
from app.storage.entities import upsert_entities, upsert_subscription_entity_matches


def discover_repository_candidates(
    queries: Sequence[str],
    *,
    per_query_limit: int = 10,
) -> list[RawSignal]:
    """Search GitHub repositories for topic-derived queries."""

    signals: list[RawSignal] = []
    for query in queries:
        search_url = _build_repository_search_url(
            query, per_query_limit=per_query_limit
        )
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
            topic_list = (
                [str(value) for value in topics] if isinstance(topics, list) else []
            )
            language = str(item.get("language") or "")
            stars = int(item.get("stargazers_count") or 0)
            owner = item.get("owner")
            owner_login = ""
            if isinstance(owner, dict):
                owner_login = str(owner.get("login") or "")

            candidate = RepositoryCandidate(
                source="github",
                full_name=full_name,
                url=str(item.get("html_url") or f"https://github.com/{full_name}"),
                query=query,
                description=description,
                owner_login=owner_login,
                language=language,
                stars=stars,
                topics=tuple(topic_list),
            )
            signals.append(build_repository_candidate_signal(candidate))

    return signals


def discover_github_entities_for_profile(
    profile: ResearchProfile,
    *,
    database_url: str | None = None,
) -> DiscoveryResult:
    """Discover GitHub repositories relevant to one research profile."""

    resolved_database_url = database_url or DATABASE_URL
    queries = build_repository_search_queries(profile)
    candidates = discover_repository_candidates(queries)

    deduped_candidates = _dedupe_repository_candidates(candidates)
    entities = []
    matches = []

    for raw_signal in deduped_candidates.values():
        normalized_signal = normalize_raw_signal(raw_signal)
        match = match_signal_to_profile(normalized_signal, profile)

        if not match.matched:
            continue

        entities.append(build_repository_entity(raw_signal))
        matches.append(
            build_repository_subscription_match(
                raw_signal,
                subscription_id=profile.topic_slug,
                match=match,
            )
        )

    upsert_entities(entities, database_url=resolved_database_url)
    upsert_subscription_entity_matches(matches, database_url=resolved_database_url)

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
