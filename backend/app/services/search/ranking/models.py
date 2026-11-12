# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Data structures for heuristic repository ranking."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from app.services.search.retrieval import RepositoryCandidate
from app.services.search.retrieval.models import RetrievalMatchLocation


RANKING_POLICY_VERSION: Literal["location_weighted_log_matches_v3"] = (
    "location_weighted_log_matches_v3"
)


@dataclass(frozen=True)
class PopularityBoostParameters:
    """An absolute bonus cap and a fixed star-count saturation reference."""

    max_bonus: float = 0.0
    reference_stars: int = 1000

    def __post_init__(self) -> None:
        if (
            type(self.max_bonus) not in (int, float)
            or not isfinite(self.max_bonus)
            or self.max_bonus < 0
        ):
            raise ValueError("Popularity max_bonus must be finite and nonnegative")
        if type(self.reference_stars) is not int or self.reference_stars <= 0:
            raise ValueError("Popularity reference_stars must be a positive integer")


@dataclass(frozen=True)
class LocationMatchCount:
    """Number of distinct observed matches in one repository location."""

    location: RetrievalMatchLocation
    count: int

    def __post_init__(self) -> None:
        if type(self.count) is not int or self.count < 0:
            raise ValueError("Match count must be a nonnegative integer")


@dataclass(frozen=True)
class RankingFeatures:
    """Source-agnostic evidence used to score one repository candidate."""

    matched_query_count: int
    total_query_count: int
    raw_hit_count: int
    evidence_record_count: int
    match_counts_by_location: tuple[LocationMatchCount, ...]
    stars: int | None = None


@dataclass(frozen=True)
class LocationScoreContribution:
    """An observed count, its policy weight and its unrounded score contribution."""

    location: RetrievalMatchLocation
    count: int
    weight: float
    contribution: float


@dataclass(frozen=True)
class PopularityScoreContribution:
    """Observed stars, fixed parameters, normalized signal, and bounded bonus."""

    stars: int | None
    reference_stars: int
    max_bonus: float
    normalized_popularity: float
    contribution: float


@dataclass(frozen=True)
class RankingScoreBreakdown:
    """Versioned snapshot of the formula and per-location contributions.

    Unversioned persisted breakdowns belong to the historical 0-100 heuristic.
    Version 2 used ``points``; version 3 names the same value ``contribution``.
    Version 4 adds the bounded popularity contribution and its parameters.
    """

    locations: tuple[LocationScoreContribution, ...]
    popularity: PopularityScoreContribution
    schema_version: Literal[4] = 4
    formula: Literal["location_weighted_log_matches_v3"] = RANKING_POLICY_VERSION


@dataclass(frozen=True)
class RankedRepositoryCandidate:
    """One candidate with its computed relevance evidence and score."""

    candidate: RepositoryCandidate
    features: RankingFeatures
    score: float
    score_breakdown: RankingScoreBreakdown


@dataclass(frozen=True)
class RankingResult:
    """Repository candidates ordered by their computed ranking scores."""

    ranked_candidates: tuple[RankedRepositoryCandidate, ...]
