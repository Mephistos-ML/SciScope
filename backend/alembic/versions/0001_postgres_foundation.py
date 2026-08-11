"""Initial Postgres foundation schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_postgres_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("seen_signals"):
        op.create_table(
            "seen_signals",
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("item_id", sa.String(), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("url", sa.Text(), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("source", "item_id"),
        )
        inspector = sa.inspect(bind)
    _create_index_if_missing(
        inspector,
        "seen_signals",
        "ix_seen_signals_source",
        ["source"],
    )

    if not inspector.has_table("entities"):
        op.create_table(
            "entities",
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
        inspector = sa.inspect(bind)
    _create_index_if_missing(
        inspector,
        "entities",
        "ix_entities_source_entity_type",
        ["source", "entity_type"],
    )
    _create_index_if_missing(
        inspector,
        "entities",
        "ix_entities_canonical_name",
        ["canonical_name"],
    )

    if not inspector.has_table("subscription_entity_matches"):
        op.create_table(
            "subscription_entity_matches",
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
        inspector = sa.inspect(bind)
    _create_index_if_missing(
        inspector,
        "subscription_entity_matches",
        "ix_subscription_entity_matches_subscription",
        ["subscription_id"],
    )
    _create_index_if_missing(
        inspector,
        "subscription_entity_matches",
        "ix_subscription_entity_matches_source",
        ["source"],
    )

    if not inspector.has_table("entity_checkpoints"):
        op.create_table(
            "entity_checkpoints",
            sa.Column("subscription_id", sa.String(), nullable=False),
            sa.Column("entity_id", sa.String(), nullable=False),
            sa.Column("checkpoint_key", sa.String(), nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("checkpoint_value", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("subscription_id", "entity_id", "checkpoint_key"),
        )
        inspector = sa.inspect(bind)
    _create_index_if_missing(
        inspector,
        "entity_checkpoints",
        "ix_entity_checkpoints_subscription",
        ["subscription_id"],
    )

    if not inspector.has_table("subscriptions"):
        op.create_table(
            "subscriptions",
            sa.Column("subscription_id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("topic_description", sa.Text(), nullable=False),
            sa.Column("manual_keywords_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("subscription_id"),
        )
        inspector = sa.inspect(bind)
    _create_index_if_missing(
        inspector,
        "subscriptions",
        "ix_subscriptions_user_id_created_at",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_subscriptions_user_id_created_at", table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index("ix_entity_checkpoints_subscription", table_name="entity_checkpoints")
    op.drop_table("entity_checkpoints")

    op.drop_index(
        "ix_subscription_entity_matches_source",
        table_name="subscription_entity_matches",
    )
    op.drop_index(
        "ix_subscription_entity_matches_subscription",
        table_name="subscription_entity_matches",
    )
    op.drop_table("subscription_entity_matches")

    op.drop_index("ix_entities_canonical_name", table_name="entities")
    op.drop_index("ix_entities_source_entity_type", table_name="entities")
    op.drop_table("entities")

    op.drop_index("ix_seen_signals_source", table_name="seen_signals")
    op.drop_table("seen_signals")


def _create_index_if_missing(
    inspector: sa.Inspector,
    table_name: str,
    index_name: str,
    columns: list[str],
) -> None:
    existing_index_names = {
        index["name"]
        for index in inspector.get_indexes(table_name)
        if isinstance(index.get("name"), str)
    }
    if index_name not in existing_index_names:
        op.create_index(index_name, table_name, columns)
