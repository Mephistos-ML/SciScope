# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Count distinct current-search evidence by repository location."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from app.services.search.ranking.models import LocationMatchCount, RankingFeatures
from app.services.search.retrieval.evidence import (
    classify_match_path,
    count_current_query_matches,
    normalize_query,
)
from app.services.search.retrieval import RepositoryCandidate


def build_ranking_features(
    candidate: RepositoryCandidate,
    queries: Sequence[str],
) -> RankingFeatures:
    """Count query/location/path matches, independently of delivery provenance.

    The current provider contract identifies a file-level hit, not individual
    occurrences within a file. Distinct queries count separately. Rank, origin,
    channel and alignment describe delivery/quality, not a new match identity.
    """

    normalized_queries = tuple(
        dict.fromkeys(normalize_query(query) for query in queries if query.strip())
    )
    current_queries = set(normalized_queries)
    evidence = candidate.provenance.match_evidence
    distinct_matches = {
        (
            normalize_query(item.query),
            classify_match_path(item.path, fallback=item.channel)
            if item.path.strip()
            else item.location,
            item.path.replace("\\", "/").strip(),
        )
        for item in evidence
        if normalize_query(item.query) in current_queries
    }
    counts = Counter(location for _, location, _ in distinct_matches)
    reported_stars = candidate.signal.payload.get("stars")
    stars = (
        reported_stars if type(reported_stars) is int and reported_stars >= 0 else None
    )
    return RankingFeatures(
        matched_query_count=count_current_query_matches(candidate, normalized_queries),
        total_query_count=len(normalized_queries),
        raw_hit_count=candidate.provenance.raw_hit_count,
        evidence_record_count=len(evidence),
        match_counts_by_location=tuple(
            LocationMatchCount(location=location, count=count)
            for location, count in sorted(counts.items())
        ),
        stars=stars,
    )
