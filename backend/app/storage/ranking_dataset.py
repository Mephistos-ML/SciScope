"""Persistence for immutable internal ranking-dataset snapshots."""

from __future__ import annotations

from collections.abc import Sequence

from app.database.records.ranking_dataset import RankingDatasetExampleRecordModel, RankingDatasetRunRecordModel
from app.database.session import session_scope
from app.models.ranking_dataset import RankingDatasetExample, RankingDatasetRun


def create_ranking_dataset_run(run: RankingDatasetRun, examples: Sequence[RankingDatasetExample], *, database_url: str) -> None:
    with session_scope(database_url) as session:
        session.add(RankingDatasetRunRecordModel(
            run_id=run.run_id, user_id=run.user_id, search_job_id=run.search_job_id,
            topic_description=run.topic_description, generated_queries_json=list(run.generated_queries),
            ranking_policy_version=run.ranking_policy_version, candidate_count=run.candidate_count,
            created_at=run.created_at,
        ))
        session.add_all(RankingDatasetExampleRecordModel(
            run_id=item.run_id, repository_id=item.repository_id, source=item.source,
            full_name=item.full_name, url=item.url, rank_position=item.rank_position,
            ranking_score=item.ranking_score, candidate_snapshot_json=item.candidate_snapshot,
            features_json=item.features, manual_label=item.manual_label, created_at=item.created_at,
        ) for item in examples)
