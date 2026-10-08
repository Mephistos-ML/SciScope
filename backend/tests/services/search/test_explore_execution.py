"""Tests for durable Explore execution snapshots."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from app.services.search.explore.execution import (
    ExploreExecutionStateError,
    deserialize_execution,
    serialize_execution,
)


@pytest.fixture
def snapshot():
    path = Path(__file__).parents[2] / "fixtures" / "explore_execution_v1.json"
    return json.loads(path.read_text())


def test_current_snapshot_round_trips_every_persisted_fact(snapshot):
    restored = deserialize_execution(snapshot)
    assert restored.pending_queries == ("second",)
    assert len(restored.retrieved.lane_outcomes) == 1
    assert restored.retrieved.lane_outcomes[0].query == "first"
    assert serialize_execution(restored) == snapshot


@pytest.mark.parametrize("version", [0, 2, -1, 999])
def test_unknown_integer_versions_are_not_guessed(snapshot, version):
    snapshot["schemaVersion"] = version
    with pytest.raises(ExploreExecutionStateError) as error:
        deserialize_execution(snapshot)
    assert error.value.code == "execution_state_unsupported"


@pytest.mark.parametrize("version", [None, True, "1", 1.0, []])
def test_version_types_are_strict(snapshot, version):
    snapshot["schemaVersion"] = version
    with pytest.raises(ExploreExecutionStateError) as error:
        deserialize_execution(snapshot)
    assert error.value.code == "execution_state_invalid"


def test_unversioned_state_requires_data_migration(snapshot):
    del snapshot["schemaVersion"]
    with pytest.raises(ExploreExecutionStateError) as error:
        deserialize_execution(snapshot)
    assert error.value.code == "execution_state_invalid"


@pytest.mark.parametrize("state,code", [(None, "execution_state_missing"), ([], "execution_state_invalid"), ("secret", "execution_state_invalid")])
def test_missing_and_invalid_roots_are_distinct(state, code):
    with pytest.raises(ExploreExecutionStateError) as error:
        deserialize_execution(state)
    assert error.value.code == code
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("path,value", [
    (("plan", "status"), "unknown"),
    (("plan", "queries"), "first"),
    (("plan", "queries"), [1]),
    (("executedQueries",), ["second"]),
    (("executedQueries",), ["first", "second", "extra"]),
    (("retrieved", "candidates"), {}),
    (("retrieved", "partial"), "false"),
    (("retrieved", "successfulSourceCount"), True),
    (("retrieved", "successfulSourceCount"), -1),
    (("retrieved", "warnings"), "warning"),
    (("retrieved", "sourceStatuses"), ["secret"]),
    (("retrieved", "candidates", 0, "repositoryId"), "wrong-id"),
    (("retrieved", "candidates", 0, "signal", "publishedAt"), "secret-date"),
    (("retrieved", "candidates", 0, "signal", "publishedAt"), "2026-10-07T00:00:00"),
    (("retrieved", "candidates", 0, "signal", "payload"), []),
    (("retrieved", "candidates", 0, "signal", "payload"), {"value": float("nan")}),
    (("retrieved", "candidates", 0, "provenance", "hitCount"), 1.5),
    (("retrieved", "candidates", 0, "provenance", "bestRankByChannel"), {"code_search": 0}),
    (("retrieved", "candidates", 0, "provenance", "matchEvidence", 0, "alignment"), float("inf")),
    (("retrieved", "candidates", 0, "provenance", "matchEvidence", 0, "alignment"), True),
    (("retrieved", "candidates", 0, "provenance", "matchEvidence", 0, "alignment"), 10 ** 400),
    (("retrieved", "candidates", 0, "provenance", "matchEvidence", 0, "origin"), "unknown-provider"),
    (("retrieved", "candidates", 0, "provenance", "matchEvidence", 0, "location"), "unknown-location"),
    (("retrieved", "candidates", 0, "provenance", "matchEvidence", 0, "retrieval_rank"), -1),
    (("retrieved", "laneOutcomes", 0, "duration_ms"), "22"),
    (("retrieved", "laneOutcomes", 0, "retry_after_seconds"), -1),
    (("attempts", 0, "query"), "unplanned"),
    (("attempts", 0, "attempt"), 0),
    (("attempts", 0, "status"), "running"),
    (("attempts", 0, "candidate_count"), False),
])
def test_malformed_state_is_rejected_without_coercion(snapshot, path, value):
    target = snapshot
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ExploreExecutionStateError) as error:
        deserialize_execution(snapshot)
    assert error.value.code == "execution_state_invalid"
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate_candidate"])
def test_incomplete_or_ambiguous_contract_is_rejected(snapshot, change):
    if change == "missing":
        del snapshot["retrieved"]["laneOutcomes"]
    elif change == "extra":
        snapshot["unexpectedField"] = "ignored data"
    else:
        snapshot["retrieved"]["candidates"].append(deepcopy(snapshot["retrieved"]["candidates"][0]))
    with pytest.raises(ExploreExecutionStateError):
        deserialize_execution(snapshot)


def test_serializer_rejects_invalid_domain_progress_before_persistence(snapshot):
    execution = deserialize_execution(snapshot)
    invalid = replace(execution, executed_queries=("second",))
    with pytest.raises(ExploreExecutionStateError) as error:
        serialize_execution(invalid)
    assert error.value.code == "execution_state_invalid"
