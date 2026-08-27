"""Migration regression tests."""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa

from tests.conftest import build_test_database_url, migrate_test_database


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
        for column in inspector.get_columns("subscriptions")
    }
    repository_columns = {
        column["name"]
        for column in inspector.get_columns("repositories")
    }
    checkpoint_columns = {
        column["name"]
        for column in inspector.get_columns("repository_checkpoints")
    }

    assert "topic_description" not in subscription_columns
    assert "query_terms_json" not in subscription_columns
    assert "repository_id" in subscription_columns
    assert "selected_query" in subscription_columns
    assert not inspector.has_table("subscription_repository_matches")
    assert inspector.has_table("repositories")
    assert "repository_id" in repository_columns
    assert "full_name" in repository_columns
    assert inspector.has_table("repository_checkpoints")
    assert "repository_id" in checkpoint_columns
    assert inspector.has_table("users")
    assert inspector.has_table("oauth_accounts")
    assert inspector.has_table("user_sessions")
    assert inspector.has_table("explore_search_events")
    assert inspector.has_table("feed_events")

    with engine.connect() as connection:
        version = connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    assert version == "0007_feed_events"
