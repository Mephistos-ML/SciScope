"""Immutable manually labelled ranking-dataset records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RankingDatasetRun:
    run_id: str
    user_id: str
    search_job_id: str
    topic_description: str
    generated_queries: tuple[str, ...]
    ranking_policy_version: str
    candidate_count: int
    created_at: datetime


@dataclass(frozen=True)
class RankingDatasetExample:
    run_id: str
    repository_id: str
    source: str
    full_name: str
    url: str
    rank_position: int
    ranking_score: float
    candidate_snapshot: dict[str, Any]
    features: dict[str, Any]
    manual_label: int | None
    created_at: datetime
