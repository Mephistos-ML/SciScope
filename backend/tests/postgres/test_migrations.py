"""Real PostgreSQL migration paths preserve persisted run and replay facts."""

from datetime import UTC, datetime
import json

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from tests.fixtures.database import BACKEND_ROOT, migrate_test_database
from app.database.session import get_engine
from app.services.search.explore.execution import deserialize_execution

pytestmark = pytest.mark.postgres


def test_clean_upgrade_creates_real_vector_schema_and_coordination_state(postgres_url):
    engine = get_engine(postgres_url)
    inspector = sa.inspect(engine)
    assert inspector.has_table("search_access_lock")
    assert inspector.has_table("repository_monitoring_cursors")
    assert inspector.has_table("repository_subscriptions")
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == "0016_guest_run_access"
        assert connection.execute(sa.text("SELECT lock_id FROM search_access_lock")).scalars().all() == [1]
        assert connection.scalar(sa.text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        columns = dict(connection.execute(sa.text("""
            SELECT table_name, udt_name FROM information_schema.columns
            WHERE table_name IN ('repository_query_embeddings', 'repository_profile_embeddings')
              AND column_name='embedding'
        """)).all())
        assert columns == {"repository_query_embeddings": "vector", "repository_profile_embeddings": "vector"}
        for table in columns:
            definitions = connection.execute(sa.text("SELECT indexdef FROM pg_indexes WHERE tablename=:table"),
                                             {"table": table}).scalars().all()
            assert any("USING hnsw" in definition and "vector_cosine_ops" in definition for definition in definitions)


def test_0016_upgrade_batches_data_and_roundtrip_preserves_run_facts(postgres_database_url, monkeypatch):
    url = postgres_database_url
    migrate_test_database(url, "0015_planner_reasoning_effort")
    engine = get_engine(url)
    runs = sa.Table("search_runs", sa.MetaData(), autoload_with=engine)
    operations = sa.Table("search_run_operations", sa.MetaData(), autoload_with=engine)
    snapshot = json.loads((BACKEND_ROOT / "tests/fixtures/explore_execution_v1.json").read_text())
    unversioned = {key: value for key, value in snapshot.items() if key != "schemaVersion"}
    unversioned["retrieved"] = {key: value for key, value in snapshot["retrieved"].items() if key != "laneOutcomes"}
    states = {"current": snapshot, "future": {**snapshot, "schemaVersion": 99}, "missing": None, "malformed": "unreadable"}
    states.update({f"legacy-{n:04}": unversioned for n in range(501)})
    now = datetime(2026, 10, 7, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(runs.insert(), [{
            "run_id": run_id, "owner_user_id": None, "topic_description": "Preserved topic",
            "topic_hash": "hash", "status": "completed", "planner_mode": "bootstrap",
            "ranking_policy_version": "heuristic-v1", "backend_revision": "fixture", "created_at": now,
            "partial": False, "response_payload_json": {"items": ["preserved"]}, "execution_state_json": state,
        } for run_id, state in states.items()])
        connection.execute(operations.insert(), [{
            "operation_id": f"operation-{status}", "run_id": "current", "kind": "initial", "status": status,
            "queued_at": now, "lease_holder_id": "legacy-worker" if status == "running" else None,
            "lease_expires_at": now if status == "running" else None,
        } for status in ("queued", "running", "completed")])
    migrate_test_database(url)
    expected_states = {}
    with engine.connect() as connection:
        rows = connection.execute(sa.text("SELECT run_id, status, response_payload_json, guest_access_token_hash, execution_state_json FROM search_runs")).mappings().all()
        for row in rows:
            assert row["guest_access_token_hash"] is None
            assert row["status"] == "completed" and row["response_payload_json"] == {"items": ["preserved"]}
            state = row["execution_state_json"]
            if row["run_id"].startswith("legacy-"):
                assert state == {**unversioned, "schemaVersion": 1, "retrieved": {**unversioned["retrieved"], "laneOutcomes": []}}
                assert deserialize_execution(state).pending_queries == ("second",)
            else:
                assert state == states[row["run_id"]]
            expected_states[row["run_id"]] = state
        assert len(rows) == len(states)
        operation_rows = connection.execute(sa.text("SELECT status, lease_holder_id, lease_token FROM search_run_operations")).mappings().all()
        assert {row["status"] for row in operation_rows} == {"queued", "running", "completed"}
        assert all(row["lease_token"] is None for row in operation_rows)
        assert next(row for row in operation_rows if row["status"] == "running")["lease_holder_id"] == "legacy-worker"
    alembic = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    monkeypatch.setenv("DATABASE_URL", url)
    command.downgrade(alembic, "0015_planner_reasoning_effort")
    assert not sa.inspect(engine).has_table("search_access_lock")
    assert "lease_token" not in {column["name"] for column in sa.inspect(engine).get_columns("search_run_operations")}
    migrate_test_database(url)
    with engine.connect() as connection:
        restored = dict(connection.execute(sa.select(runs.c.run_id, runs.c.execution_state_json)).all())
        assert restored == expected_states
        assert connection.scalar(sa.text("SELECT count(*) FROM search_access_lock")) == 1
