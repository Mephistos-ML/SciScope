"""GitLab repository discovery and entity admission."""

from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import quote_plus

from app.config import DATABASE_URL
from app.models.discovery import DiscoveryResult
from app.models.signal import RawSignal
from app.models.subscription import SubscriptionQueryProfile
from app.services.search.matching import match_signal_to_profile
from app.services.search.normalization import normalize_raw_signal
from app.sources.common import (
    RepositoryCandidate,
    build_repository_candidate_signal,
    build_repository_entity,
    build_repository_subscription_match,
)
from app.sources.gitlab.client import GITLAB_API_BASE, fetch_json
from app.storage.repositories import (
    upsert_repositories,
    upsert_subscription_repository_matches,
)


def discover_repository_candidates(
    queries: Sequence[str],
    *,
    per_query_limit: int = 10,
) -> list[RawSignal]:
    """Search GitLab projects for topic-derived queries."""

    signals: list[RawSignal] = []
    for query in queries:
        search_url = _build_repository_search_url(query, per_query_limit=per_query_limit)
        payload = fetch_json(search_url)
        if not isinstance(payload, list):
            continue

        for item in payload:
            if not isinstance(item, dict):
                continue

            full_name = str(item.get("path_with_namespace") or "").strip()
            if not full_name:
                continue

            description = str(item.get("description") or "")
            topics = item.get("topics")
            topic_list = [str(value) for value in topics] if isinstance(topics, list) else []
            stars = int(item.get("star_count") or 0)
            owner_login = full_name.split("/", 1)[0] if "/" in full_name else ""

            candidate = RepositoryCandidate(
                source="gitlab",
                full_name=full_name,
                url=str(item.get("web_url") or ""),
                query=query,
                description=description,
                owner_login=owner_login,
                language="",
                stars=stars,
                topics=tuple(topic_list),
            )
            signals.append(build_repository_candidate_signal(candidate))

    return signals


def discover_gitlab_repositories_for_profile(
    profile: SubscriptionQueryProfile,
    *,
    database_url: str | None = None,
) -> DiscoveryResult:
    """Discover GitLab repositories relevant to one subscription."""

    resolved_database_url = database_url or DATABASE_URL
    queries = profile.query_terms
    candidates = discover_repository_candidates(queries)

    deduped_candidates = _dedupe_repository_candidates(candidates)
    repositories = []
    matches = []

    for raw_signal in deduped_candidates.values():
        normalized_signal = normalize_raw_signal(raw_signal)
        match = match_signal_to_profile(normalized_signal, profile)

        if not match.matched:
            continue

        repositories.append(build_repository_entity(raw_signal))
        matches.append(
            build_repository_subscription_match(
                raw_signal,
                subscription_id=profile.subscription_id,
                match=match,
            )
        )

    upsert_repositories(repositories, database_url=resolved_database_url)
    upsert_subscription_repository_matches(
        matches,
        database_url=resolved_database_url,
    )

    return DiscoveryResult(
        subscription_id=profile.subscription_id,
        queries=queries,
        candidate_count=len(candidates),
        repository_count=len(repositories),
        matched_repository_count=len(matches),
    )


def _build_repository_search_url(query: str, *, per_query_limit: int) -> str:
    encoded_query = quote_plus(query)
    return (
        f"{GITLAB_API_BASE}/search"
        f"?scope=projects&search={encoded_query}&per_page={per_query_limit}"
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
