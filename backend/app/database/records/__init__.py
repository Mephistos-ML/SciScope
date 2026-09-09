"""SQLAlchemy persistence record models for SciScope."""

from app.database.records.auth import (
    OAuthAccountRecordModel,
    UserRecordModel,
    UserSessionRecordModel,
)
from app.database.records.explore import ExploreSearchEventRecordModel
from app.database.records.feed import FeedEventRecordModel
from app.database.records.monitoring import (
    MonitoringJobLeaseRecordModel,
    MonitoringRunRecordModel,
    RepositoryMonitoringCheckRecordModel,
    RepositoryMonitoringCursorRecordModel,
)
from app.database.records.repositories import (
    RepositoryCheckpointRecordModel,
    RepositoryRecordModel,
    RepositorySearchEvidenceRecordModel,
    SubscriptionRecordModel,
)
from app.database.records.ranking_dataset import (
    RankingDatasetExampleRecordModel,
    RankingDatasetRunRecordModel,
)

__all__ = [
    "ExploreSearchEventRecordModel",
    "FeedEventRecordModel",
    "MonitoringJobLeaseRecordModel",
    "MonitoringRunRecordModel",
    "OAuthAccountRecordModel",
    "RepositoryCheckpointRecordModel",
    "RepositoryMonitoringCheckRecordModel",
    "RepositoryMonitoringCursorRecordModel",
    "RepositoryRecordModel",
    "RepositorySearchEvidenceRecordModel",
    "RankingDatasetExampleRecordModel",
    "RankingDatasetRunRecordModel",
    "SubscriptionRecordModel",
    "UserRecordModel",
    "UserSessionRecordModel",
]
