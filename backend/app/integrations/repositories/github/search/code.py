# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""GitHub code-aware repository search."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import logging
from time import monotonic
from urllib.parse import quote_plus

from app.models.signal import Signal
from app.integrations.repositories.github.search.file_policy import build_code_search_query
from app.integrations.repositories.common.models import (
    RepositoryCandidate, RepositoryDiscoveryBatch, DiscoveryCoverageReason,
)
from app.integrations.repositories.common.factories import build_repository_candidate_signal
from app.integrations.repositories.common.deadlines import raise_source_timeout_error
from app.integrations.repositories.common.source_status import RepositorySourceError
from app.integrations.repositories.github.client import GitHubClient
from app.integrations.repositories.github.repository import map_repository_profile

logger = logging.getLogger(__name__)


def discover_repository_candidates_from_code(
    queries: Sequence[str],
    *,
    client: GitHubClient,
    deadline_monotonic: float | None = None,
    per_query_limit: int = 100,
    max_pages: int = 10,
    report_result_count: Callable[[int], None] | None = None,
) -> list[Signal]:
    """Collect signals strictly for offline callers that handle coverage separately.

    Unlike the product batch contract, a terminal request error aborts collection.
    Current research runners rely on this to preserve their interrupted checkpoints.
    """
    batch = search_code(
        queries, client=client, deadline_monotonic=deadline_monotonic,
        per_query_limit=per_query_limit, max_pages=max_pages,
    )
    if report_result_count is not None:
        for count in batch.reported_result_counts:
            report_result_count(count)
    if batch.error is not None:
        raise batch.error
    return list(batch.signals)


def search_code(
    queries: Sequence[str], *, client: GitHubClient,
    deadline_monotonic: float | None = None,
    per_query_limit: int = 100, max_pages: int = 10,
) -> RepositoryDiscoveryBatch:
    """Return validated page prefixes and coverage even after a later IO failure."""
    if type(per_query_limit) is not int or not 1 <= per_query_limit <= 100:
        raise ValueError("GitHub code search page size must be between 1 and 100")
    if type(max_pages) is not int or not 1 <= max_pages <= 10:
        raise ValueError("GitHub code search page budget must be between 1 and 10")
    signals: list[Signal] = []
    counts: list[int] = []
    reasons: list[DiscoveryCoverageReason] = []

    def result(error: RepositorySourceError | None = None) -> RepositoryDiscoveryBatch:
        return RepositoryDiscoveryBatch(
            tuple(signals), tuple(counts), tuple(dict.fromkeys(reasons)), error,
        )

    for query in queries:
        returned = 0
        reported_total: int | None = None
        for page in range(1, max_pages + 1):
            search_url = _build_code_search_url(
                query, per_query_limit=per_query_limit, page=page, client=client,
            )
            try:
                if deadline_monotonic is not None and monotonic() >= deadline_monotonic:
                    raise_source_timeout_error(source="github", operation="code search")
                response = client.fetch_json(
                    search_url, deadline_monotonic=deadline_monotonic,
                    max_response_bytes=2 * 1024 * 1024,
                )
                payload = response.payload
                if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                    raise RepositorySourceError(source="github", status="error",
                                                public_message="GitHub returned an invalid search response.")
                items = payload["items"]
                if len(items) > per_query_limit:
                    raise RepositorySourceError(source="github", status="error",
                                                public_message="GitHub returned an invalid search response.")
                total = payload.get("total_count")
                incomplete = payload.get("incomplete_results")
                if total is not None and (type(total) is not int or total < 0):
                    raise RepositorySourceError(source="github", status="error",
                                                public_message="GitHub returned an invalid search response.")
                if incomplete is not None and type(incomplete) is not bool:
                    raise RepositorySourceError(source="github", status="error",
                                                public_message="GitHub returned an invalid search response.")
            except RepositorySourceError as error:
                logger.warning("GitHub code search stopped query=%r page=%s status=%s retained_signals=%s",
                               query, page, error.status, len(signals))
                return result(error)

            if total is None or incomplete is None:
                reasons.append("coverage_unknown")
            if total is not None:
                counts.append(total)
                reported_total = max(reported_total or 0, total)
            if incomplete:
                reasons.append("provider_incomplete")
            for item in items:
                if not isinstance(item, dict) or not isinstance(item.get("repository"), dict):
                    reasons.append("unmapped_items")
                    continue
                repository = item["repository"]
                full_name = repository.get("full_name")
                provider_id = repository.get("id")
                path = item.get("path")
                if (not isinstance(full_name, str) or len(full_name.split("/")) != 2
                    or not all(full_name.split("/"))
                    or type(provider_id) is not int or provider_id <= 0
                    or not isinstance(path, str) or not path.strip()):
                    reasons.append("unmapped_items")
                    continue
                try:
                    profile = map_repository_profile({
                        **repository,
                        "html_url": repository.get("html_url") or f"https://github.com/{full_name}",
                    })
                except RepositorySourceError:
                    reasons.append("unmapped_items")
                    continue
                candidate = RepositoryCandidate(
                    source="github", full_name=profile.full_name, url=profile.url,
                    query=query, provider_repository_id=profile.provider_repository_id,
                    description=profile.description, owner_login=profile.owner_login,
                    language=profile.language, topics=(), matched_path=path,
                    provider_updated_at=profile.provider_updated_at,
                )
                signals.append(build_repository_candidate_signal(candidate))
            returned += len(items)
            if reported_total is not None and returned > reported_total:
                reasons.append("provider_incomplete")
            if len(items) < per_query_limit:
                if reported_total is not None and returned < reported_total:
                    reasons.append("provider_truncated")
                break
            if reported_total is not None and returned == reported_total:
                break
            if page == max_pages and (reported_total is None or returned < reported_total):
                reasons.append("page_budget")
    return result()


def _build_code_search_url(query: str, *, client: GitHubClient, per_query_limit: int, page: int) -> str:
    encoded_query = quote_plus(build_code_search_query(query))
    return (
        f"{client.api_base}/search/code"
        f"?q={encoded_query}&per_page={per_query_limit}&page={page}"
    )
