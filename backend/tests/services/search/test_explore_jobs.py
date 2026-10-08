"""Tests for durable Explore search job creation."""

from app import config
from app.composition.search import build_explore_dependencies
from app.models.explore_access import ExploreActor, ExploreAdmission, ExploreTier
from app.services.search.explore.jobs import create_explore_search_run
from app.storage.search_runs import get_search_run
from tests.conftest import build_test_database_url, migrate_test_database


def test_openai_run_persists_planner_model_and_reasoning_effort(tmp_path, monkeypatch) -> None:
    database_url = build_test_database_url(tmp_path / "planner-metadata.sqlite3")
    migrate_test_database(database_url)
    monkeypatch.setattr(config, "AI_PLANNER_MODE", "openai")
    monkeypatch.setattr(config, "OPENAI_MODEL", "gpt-6-luna")
    monkeypatch.setattr(config, "OPENAI_REASONING_EFFORT", "low")
    created = create_explore_search_run(
        topic_description="Paramagnetic NMR fitting",
        admission=ExploreAdmission(ExploreActor(ExploreTier.GUEST, "guest_ip", "test-guest")),
        database_url=database_url,
        dependencies=build_explore_dependencies(),
    )
    stored = get_search_run(created["runId"], database_url=database_url)

    assert stored is not None
    assert stored.planner_model == "gpt-6-luna"
    assert stored.planner_reasoning_effort == "low"
