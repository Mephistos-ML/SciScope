"""Migration-safety tests for production-like upgrade paths."""

from __future__ import annotations

import sqlalchemy as sa

from tests.conftest import build_test_database_url, migrate_test_database


def test_migrations_upgrade_legacy_schema_without_duplicate_table_failures(
    tmp_path,
) -> None:
    database_url = build_test_database_url(tmp_path / "legacy-schema.sqlite3")
    engine = sa.create_engine(database_url)
    metadata = sa.MetaData()

    sa.Table(
        "seen_signals",
        metadata,
        sa.Column("source", sa.String(), nullable=False, primary_key=True),
        sa.Column("item_id", sa.String(), nullable=False, primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    sa.Table(
        "entities",
        metadata,
        sa.Column("entity_id", sa.String(), nullable=False, primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("canonical_name", sa.String(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    sa.Table(
        "subscription_entity_matches",
        metadata,
        sa.Column("subscription_id", sa.String(), nullable=False, primary_key=True),
        sa.Column("entity_id", sa.String(), nullable=False, primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("matched_terms_json", sa.JSON(), nullable=False),
        sa.Column("excluded_terms_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    sa.Table(
        "entity_checkpoints",
        metadata,
        sa.Column("subscription_id", sa.String(), nullable=False, primary_key=True),
        sa.Column("entity_id", sa.String(), nullable=False, primary_key=True),
        sa.Column("checkpoint_key", sa.String(), nullable=False, primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("checkpoint_value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    sa.Table(
        "subscriptions",
        metadata,
        sa.Column("subscription_id", sa.String(), nullable=False, primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("topic_description", sa.Text(), nullable=False),
        sa.Column("manual_keywords_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    metadata.create_all(engine)

    migrate_test_database(database_url)

    inspector = sa.inspect(engine)
    subscription_columns = {
        column["name"] for column in inspector.get_columns("subscriptions")
    }
    assert "query_terms_json" in subscription_columns
    assert "query_strategy" in subscription_columns
    assert "manual_keywords_json" not in subscription_columns

    with engine.connect() as connection:
        version = connection.execute(sa.text("SELECT version_num FROM alembic_version"))
        assert version.scalar_one() == "0002_subscription_query_terms"
