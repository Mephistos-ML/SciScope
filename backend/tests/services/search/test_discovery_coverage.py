"""Empty, unavailable and incomplete observations retain distinct product meaning."""

import pytest

from app.integrations.repositories.common.models import RepositoryDiscoveryBatch
from app.integrations.repositories.common.source_status import RepositorySourceError
from app.models.ai import AiSearchPlan
from app.services.search.explore.execution import ExploreSearchExecution, deserialize_execution, serialize_execution
from app.services.search.retrieval.models import RetrievalLane
from app.services.search.retrieval.service import run_external_repository_retrieval


@pytest.mark.parametrize("reason", ["page_budget", "provider_incomplete", "provider_truncated", "coverage_unknown", "unmapped_items"])
def test_incomplete_empty_result_survives_durable_replay(reason):
    def discover(queries, *, deadline_monotonic):
        return RepositoryDiscoveryBatch((), (), (reason,))

    result = run_external_repository_retrieval(["science"], lanes=(RetrievalLane("github", "code_search", discover),))
    assert result.partial is True
    assert result.successful_source_count == 1
    assert not result.candidates
    assert result.lane_outcomes[0].status == "partial"
    assert result.lane_outcomes[0].error_code == reason
    execution = ExploreSearchExecution(AiSearchPlan("ready", ("science",)), ("science",), result)
    restored = deserialize_execution(serialize_execution(execution))
    assert restored.retrieved == result


def test_first_page_failure_is_unavailable_not_a_complete_empty_result():
    def discover(queries, *, deadline_monotonic):
        return RepositoryDiscoveryBatch((), error=RepositorySourceError(
            source="github", status="rate_limited", public_message="Unavailable", retry_after_seconds=60,
        ))

    result = run_external_repository_retrieval(["science", "unattempted"], lanes=(RetrievalLane("github", "code_search", discover),))
    assert result.partial is True
    assert result.successful_source_count == 0
    assert result.source_statuses[0]["status"] == "rate_limited"
    assert result.lane_outcomes[0].status == "rate_limited"
    assert result.lane_outcomes[0].retry_after_seconds == 60


def test_complete_empty_result_is_successful_and_not_partial():
    def discover(queries, *, deadline_monotonic):
        return RepositoryDiscoveryBatch((), (0,))

    result = run_external_repository_retrieval(["science"], lanes=(RetrievalLane("github", "code_search", discover),))
    assert not result.partial
    assert result.successful_source_count == 1
    assert result.lane_outcomes[0].status == "ok"
