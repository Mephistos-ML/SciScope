"""Migration regression tests."""

from __future__ import annotations

from pathlib import Path
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from tests.fixtures.database import BACKEND_ROOT, build_test_database_url, migrate_test_database


def test_migrations_upgrade_legacy_schema_without_alembic_history(tmp_path: Path) -> None:
    database_url = build_test_database_url(tmp_path / "legacy.sqlite3")
    engine = sa.create_engine(database_url)
    metadata = sa.MetaData()

    sa.Table(
        "seen_signals",
        metadata,
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("item_id", sa.String(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("source", "item_id"),
    )
    sa.Table(
        "entities",
        metadata,
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("canonical_name", sa.String(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("entity_id"),
    )
    sa.Table(
        "subscription_entity_matches",
        metadata,
        sa.Column("subscription_id", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("matched_terms_json", sa.JSON(), nullable=False),
        sa.Column("excluded_terms_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("subscription_id", "entity_id"),
    )
    sa.Table(
        "entity_checkpoints",
        metadata,
        sa.Column("subscription_id", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("checkpoint_key", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("checkpoint_value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("subscription_id", "entity_id", "checkpoint_key"),
    )
    sa.Table(
        "subscriptions",
        metadata,
        sa.Column("subscription_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("topic_description", sa.Text(), nullable=False),
        sa.Column("manual_keywords_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("subscription_id"),
    )

    metadata.create_all(engine)

    migrate_test_database(database_url)

    inspector = sa.inspect(engine)
    subscription_columns = {
        column["name"]
        for column in inspector.get_columns("repository_subscriptions")
    }
    repository_columns = {
        column["name"]
        for column in inspector.get_columns("repositories")
    }
    assert "topic_description" not in subscription_columns
    assert "query_terms_json" not in subscription_columns
    assert "repository_id" in subscription_columns
    assert "selected_query" in subscription_columns
    assert not inspector.has_table("subscription_repository_matches")
    assert inspector.has_table("repositories")
    assert "repository_id" in repository_columns
    assert "full_name" in repository_columns
    assert "provider_repository_id" in repository_columns
    assert "search_text" in repository_columns
    assert inspector.has_table("repository_query_evidence")
    assert not inspector.has_table("subscription_scan_cursors")
    assert inspector.has_table("users")
    assert inspector.has_table("user_identities")
    assert inspector.has_table("user_sessions")
    assert inspector.has_table("search_access_events")
    assert inspector.has_table("user_feed_events")
    feed_columns = {
        column["name"] for column in inspector.get_columns("user_feed_events")
    }
    assert "read_at" in feed_columns
    feed_indexes = {index["name"] for index in inspector.get_indexes("user_feed_events")}
    assert "ix_user_feed_events_user_chronological" in feed_indexes
    assert "ix_user_feed_events_user_read_chronological" in feed_indexes
    assert "ix_user_feed_events_user_subscription_chronological" in feed_indexes
    assert not inspector.has_table("ranking_dataset_runs")
    assert not inspector.has_table("ranking_dataset_examples")
    assert inspector.has_table("search_run_ranking_candidates")
    assert inspector.has_table("search_run_ranking_labels")
    assert inspector.has_table("repository_query_embeddings")
    assert inspector.has_table("repository_profile_embeddings")
    assert inspector.has_table("repository_monitoring_cursors")
    assert inspector.has_table("monitoring_job_leases")
    assert inspector.has_table("monitoring_runs")
    assert inspector.has_table("repository_monitoring_checks")
    assert not inspector.has_table("seen_signals")

    with engine.connect() as connection:
        version = connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    assert version == "0017_feed_update_groups"
    assert inspector.has_table("user_feed_update_groups")
    assert inspector.has_table("user_feed_update_group_members")
    assert inspector.has_table("search_runs")
    assert inspector.has_table("search_run_operations")
    assert inspector.has_table("search_run_stages")
    assert inspector.has_table("search_run_provider_outcomes")
    search_run_columns = {
        column["name"] for column in inspector.get_columns("search_runs")
    }
    assert "planner_reasoning_effort" in search_run_columns
    assert "guest_access_token_hash" in search_run_columns
    assert "lease_token" in {column["name"] for column in inspector.get_columns("search_run_operations")}
    assert inspector.has_table("search_access_lock")
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT lock_id FROM search_access_lock")).scalars().all() == [1]


def test_feed_event_migration_replaces_provider_derived_ids(tmp_path: Path) -> None:
    database_url = build_test_database_url(tmp_path / "feed-event-ids.sqlite3")
    migrate_test_database(database_url, "0012_stateless_monitoring")
    engine = sa.create_engine(database_url)
    feed_events = sa.Table("user_feed_events", sa.MetaData(), autoload_with=engine)
    legacy_event_id = "sub_1:github:owner/repository:commit:abc123"

    with engine.begin() as connection:
        connection.execute(
            feed_events.insert().values(
                event_id=legacy_event_id,
                user_id="user_1",
                subscription_id="sub_1",
                repository_id="github:repo:owner/repository",
                repository_full_name="owner/repository",
                repository_source="github",
                repository_url="https://github.com/owner/repository",
                selected_query=None,
                source="github",
                kind="commit",
                item_id="owner/repository:commit:abc123",
                title="One commit",
                url="https://github.com/owner/repository/commit/abc123",
                published_at=datetime(2026, 9, 10, tzinfo=UTC),
                raw_text="One commit",
                normalized_text="One commit",
                metadata_json={},
                created_at=datetime(2026, 9, 10, tzinfo=UTC),
                read_at=None,
            )
        )

    migrate_test_database(database_url)

    with engine.connect() as connection:
        event_id = connection.execute(sa.select(feed_events.c.event_id)).scalar_one()

    assert event_id != legacy_event_id
    assert "/" not in event_id
    assert UUID(event_id).version == 5


def test_guest_access_migration_preserves_legacy_runs_without_granting_tokens(tmp_path: Path) -> None:
    database_url = build_test_database_url(tmp_path / "legacy-runs.sqlite3")
    migrate_test_database(database_url, "0015_planner_reasoning_effort")
    engine = sa.create_engine(database_url)
    runs = sa.Table("search_runs", sa.MetaData(), autoload_with=engine)
    operations = sa.Table("search_run_operations", sa.MetaData(), autoload_with=engine)
    now = datetime(2026, 10, 7, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO users (user_id, email, display_name, created_at, updated_at) "
            "VALUES (:id, :email, :name, :now, :now)"
        ), {"id": "owner", "email": "owner@example.com", "name": "Owner", "now": now.isoformat()})
        for run_id, owner in (("legacy-guest", None), ("legacy-owned", "owner")):
            connection.execute(runs.insert().values(
                run_id=run_id, owner_user_id=owner,
                topic_description="Preserved topic", topic_hash="topic-hash",
                status="completed", planner_mode="bootstrap", planner_model=None,
                planner_reasoning_effort=None, ranking_policy_version="heuristic-v1",
                backend_revision="known", created_at=now, partial=False,
                response_payload_json={"items": [{"itemId": "github:repo:123"}]},
            ))
        for status in ("queued", "running", "completed"):
            connection.execute(operations.insert().values(
                operation_id=f"legacy-{status}", run_id="legacy-owned", kind="initial",
                status=status, queued_at=now,
                lease_holder_id="legacy-worker" if status == "running" else None,
                lease_expires_at=now if status == "running" else None,
            ))
    migrate_test_database(database_url)
    upgraded_operations = sa.Table("search_run_operations", sa.MetaData(), autoload_with=engine)
    with engine.connect() as connection:
        operation_rows = connection.execute(sa.select(upgraded_operations)).mappings().all()
    assert {row["status"] for row in operation_rows} == {"queued", "running", "completed"}
    assert all(row["lease_token"] is None for row in operation_rows)
    assert next(row for row in operation_rows if row["status"] == "running")["lease_holder_id"] == "legacy-worker"
    upgraded = sa.Table("search_runs", sa.MetaData(), autoload_with=engine)
    with engine.connect() as connection:
        rows = connection.execute(sa.select(upgraded).order_by(upgraded.c.run_id)).mappings().all()
    assert [row["run_id"] for row in rows] == ["legacy-guest", "legacy-owned"]
    assert [row["owner_user_id"] for row in rows] == [None, "owner"]
    assert all(row["guest_access_token_hash"] is None for row in rows)
    assert all(row["topic_description"] == "Preserved topic" for row in rows)
    assert all(row["response_payload_json"] == {"items": [{"itemId": "github:repo:123"}]} for row in rows)


def test_guest_access_migration_downgrade_and_reupgrade(tmp_path: Path, monkeypatch) -> None:
    database_url = build_test_database_url(tmp_path / "guest-access-roundtrip.sqlite3")
    migrate_test_database(database_url)
    alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.downgrade(alembic_config, "0015_planner_reasoning_effort")
    engine = sa.create_engine(database_url)
    assert not sa.inspect(engine).has_table("search_access_lock")
    assert "guest_access_token_hash" not in {c["name"] for c in sa.inspect(engine).get_columns("search_runs")}
    assert "lease_token" not in {c["name"] for c in sa.inspect(engine).get_columns("search_run_operations")}
    migrate_test_database(database_url)
    assert "lease_token" in {c["name"] for c in sa.inspect(engine).get_columns("search_run_operations")}
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT lock_id FROM search_access_lock")).scalar_one() == 1


def test_execution_state_migration_converts_data_without_a_runtime_legacy_reader(tmp_path: Path, monkeypatch):
    import json

    from app.services.search.explore.execution import deserialize_execution

    snapshot = json.loads((BACKEND_ROOT / "tests/fixtures/explore_execution_v1.json").read_text())
    unversioned = {key: value for key, value in snapshot.items() if key != "schemaVersion"}
    unversioned["retrieved"] = {key: value for key, value in snapshot["retrieved"].items() if key != "laneOutcomes"}
    future = {**snapshot, "schemaVersion": 99}
    database_url = build_test_database_url(tmp_path / "versioned-execution.sqlite3")
    migrate_test_database(database_url, "0015_planner_reasoning_effort")
    engine = sa.create_engine(database_url)
    runs = sa.Table("search_runs", sa.MetaData(), autoload_with=engine)
    states = {"current": snapshot, "future": future, "missing": None, "malformed": "unreadable"}
    states.update({f"unversioned-{index:04}": unversioned for index in range(501)})
    with engine.begin() as connection:
        connection.execute(runs.insert(), [{
            "run_id": run_id, "owner_user_id": None,
            "topic_description": "Preserved topic", "topic_hash": "hash", "status": "completed",
            "planner_mode": "bootstrap", "ranking_policy_version": "heuristic-v1",
            "backend_revision": "fixture", "created_at": datetime(2026, 10, 7, tzinfo=UTC),
            "partial": False, "response_payload_json": {"items": ["preserved"]},
            "execution_state_json": state,
        } for run_id, state in states.items()])
    migrate_test_database(database_url)
    with engine.connect() as connection:
        rows = connection.execute(sa.select(runs)).mappings().all()
    assert len(rows) == len(states)
    expected = {**unversioned, "schemaVersion": 1,
                "retrieved": {**unversioned["retrieved"], "laneOutcomes": []}}
    for row in rows:
        assert row["response_payload_json"] == {"items": ["preserved"]}
        assert row["status"] == "completed"
        state = row["execution_state_json"]
        if row["run_id"].startswith("unversioned-"):
            assert state == expected
            assert deserialize_execution(state).pending_queries == ("second",)
        else:
            assert state == states[row["run_id"]]

    # A schema round trip must not erase the newly preserved execution facts.
    expected_states = {row["run_id"]: row["execution_state_json"] for row in rows}
    alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.downgrade(alembic_config, "0015_planner_reasoning_effort")
    migrate_test_database(database_url)
    with engine.connect() as connection:
        restored = connection.execute(sa.select(runs.c.run_id, runs.c.execution_state_json)).all()
    assert dict(restored) == expected_states
