"""Consolidate repository-only schema into direct repository subscriptions."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_direct_repository_subscriptions"
down_revision = "0004_ai_search_plan_foundation"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _has_column(
    inspector: sa.Inspector,
    table_name: str,
    column_name: str,
) -> bool:
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def _has_index(
    inspector: sa.Inspector,
    table_name: str,
    index_name: str,
) -> bool:
    return index_name in {
        index["name"] for index in inspector.get_indexes(table_name)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "subscriptions") and _has_column(
        inspector,
        "subscriptions",
        "search_scope",
    ):
        with op.batch_alter_table("subscriptions") as batch_op:
            batch_op.drop_column("search_scope")
        inspector = sa.inspect(bind)

    if _has_table(inspector, "entities") and not _has_table(inspector, "repositories"):
        op.rename_table("entities", "repositories")
        inspector = sa.inspect(bind)

    if _has_table(inspector, "repositories"):
        if _has_index(inspector, "repositories", "ix_entities_source_entity_type"):
            op.drop_index("ix_entities_source_entity_type", table_name="repositories")
        if _has_index(inspector, "repositories", "ix_entities_canonical_name"):
            op.drop_index("ix_entities_canonical_name", table_name="repositories")
        inspector = sa.inspect(bind)
        with op.batch_alter_table("repositories") as batch_op:
            if _has_column(inspector, "repositories", "entity_id"):
                batch_op.alter_column(
                    "entity_id",
                    new_column_name="repository_id",
                    existing_type=sa.String(),
                )
            if _has_column(inspector, "repositories", "canonical_name"):
                batch_op.alter_column(
                    "canonical_name",
                    new_column_name="full_name",
                    existing_type=sa.String(),
                )
            if _has_column(inspector, "repositories", "entity_type"):
                batch_op.drop_column("entity_type")
        inspector = sa.inspect(bind)
        if not _has_index(inspector, "repositories", "ix_repositories_source"):
            op.create_index("ix_repositories_source", "repositories", ["source"])
        if not _has_index(inspector, "repositories", "ix_repositories_full_name"):
            op.create_index("ix_repositories_full_name", "repositories", ["full_name"])
        inspector = sa.inspect(bind)

    if _has_table(inspector, "subscription_entity_matches") and not _has_table(
        inspector,
        "subscription_repository_matches",
    ):
        op.rename_table(
            "subscription_entity_matches",
            "subscription_repository_matches",
        )
        inspector = sa.inspect(bind)

    if _has_table(inspector, "subscription_repository_matches"):
        with op.batch_alter_table("subscription_repository_matches") as batch_op:
            if _has_column(
                inspector,
                "subscription_repository_matches",
                "entity_id",
            ):
                batch_op.alter_column(
                    "entity_id",
                    new_column_name="repository_id",
                    existing_type=sa.String(),
                )
            if _has_column(inspector, "subscription_repository_matches", "active"):
                batch_op.drop_column("active")
            if _has_column(
                inspector,
                "subscription_repository_matches",
                "excluded_terms_json",
            ):
                batch_op.drop_column("excluded_terms_json")
        inspector = sa.inspect(bind)
        if _has_index(
            inspector,
            "subscription_repository_matches",
            "ix_subscription_entity_matches_subscription",
        ):
            op.drop_index(
                "ix_subscription_entity_matches_subscription",
                table_name="subscription_repository_matches",
            )
        if _has_index(
            inspector,
            "subscription_repository_matches",
            "ix_subscription_entity_matches_source",
        ):
            op.drop_index(
                "ix_subscription_entity_matches_source",
                table_name="subscription_repository_matches",
            )
        inspector = sa.inspect(bind)
        if not _has_index(
            inspector,
            "subscription_repository_matches",
            "ix_subscription_repository_matches_subscription",
        ):
            op.create_index(
                "ix_subscription_repository_matches_subscription",
                "subscription_repository_matches",
                ["subscription_id"],
            )
        if not _has_index(
            inspector,
            "subscription_repository_matches",
            "ix_subscription_repository_matches_source",
        ):
            op.create_index(
                "ix_subscription_repository_matches_source",
                "subscription_repository_matches",
                ["source"],
            )
        inspector = sa.inspect(bind)
        op.drop_table("subscription_repository_matches")
        inspector = sa.inspect(bind)

    if _has_table(inspector, "entity_checkpoints") and not _has_table(
        inspector,
        "repository_checkpoints",
    ):
        op.rename_table("entity_checkpoints", "repository_checkpoints")
        inspector = sa.inspect(bind)

    if _has_table(inspector, "repository_checkpoints"):
        with op.batch_alter_table("repository_checkpoints") as batch_op:
            if _has_column(inspector, "repository_checkpoints", "entity_id"):
                batch_op.alter_column(
                    "entity_id",
                    new_column_name="repository_id",
                    existing_type=sa.String(),
                )
        inspector = sa.inspect(bind)
        if _has_index(
            inspector,
            "repository_checkpoints",
            "ix_entity_checkpoints_subscription",
        ):
            op.drop_index(
                "ix_entity_checkpoints_subscription",
                table_name="repository_checkpoints",
            )
        inspector = sa.inspect(bind)
        if not _has_index(
            inspector,
            "repository_checkpoints",
            "ix_repository_checkpoints_subscription",
        ):
            op.create_index(
                "ix_repository_checkpoints_subscription",
                "repository_checkpoints",
                ["subscription_id"],
            )
        inspector = sa.inspect(bind)

    if _has_table(inspector, "subscriptions"):
        op.drop_table("subscriptions")
        inspector = sa.inspect(bind)

    op.create_table(
        "subscriptions",
        sa.Column("subscription_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("repository_id", sa.String(), nullable=False),
        sa.Column("selected_query", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("subscription_id"),
    )
    op.create_index(
        "ix_subscriptions_user_id_created_at",
        "subscriptions",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ux_subscriptions_user_repository",
        "subscriptions",
        ["user_id", "repository_id"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "subscriptions"):
        if _has_index(
            inspector,
            "subscriptions",
            "ux_subscriptions_user_repository",
        ):
            op.drop_index(
                "ux_subscriptions_user_repository",
                table_name="subscriptions",
            )
        if _has_index(
            inspector,
            "subscriptions",
            "ix_subscriptions_user_id_created_at",
        ):
            op.drop_index(
                "ix_subscriptions_user_id_created_at",
                table_name="subscriptions",
            )
        op.drop_table("subscriptions")

    op.create_table(
        "subscriptions",
        sa.Column("subscription_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("topic_description", sa.Text(), nullable=False),
        sa.Column("query_terms_json", sa.JSON(), nullable=False),
        sa.Column(
            "search_scope",
            sa.String(),
            nullable=False,
            server_default="repositories",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("subscription_id"),
    )
    op.create_index(
        "ix_subscriptions_user_id_created_at",
        "subscriptions",
        ["user_id", "created_at"],
    )

    op.create_table(
        "subscription_entity_matches",
        sa.Column("subscription_id", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("matched_terms_json", sa.JSON(), nullable=False),
        sa.Column("excluded_terms_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("subscription_id", "entity_id"),
    )
    op.create_index(
        "ix_subscription_entity_matches_subscription",
        "subscription_entity_matches",
        ["subscription_id"],
    )
    op.create_index(
        "ix_subscription_entity_matches_source",
        "subscription_entity_matches",
        ["source"],
    )

    if _has_table(inspector, "repository_checkpoints"):
        if _has_index(
            inspector,
            "repository_checkpoints",
            "ix_repository_checkpoints_subscription",
        ):
            op.drop_index(
                "ix_repository_checkpoints_subscription",
                table_name="repository_checkpoints",
            )
        with op.batch_alter_table("repository_checkpoints") as batch_op:
            batch_op.alter_column(
                "repository_id",
                new_column_name="entity_id",
                existing_type=sa.String(),
            )
        op.create_index(
            "ix_entity_checkpoints_subscription",
            "repository_checkpoints",
            ["subscription_id"],
        )
        op.rename_table("repository_checkpoints", "entity_checkpoints")

    if _has_table(inspector, "repositories"):
        if _has_index(inspector, "repositories", "ix_repositories_source"):
            op.drop_index("ix_repositories_source", table_name="repositories")
        if _has_index(inspector, "repositories", "ix_repositories_full_name"):
            op.drop_index("ix_repositories_full_name", table_name="repositories")
        with op.batch_alter_table("repositories") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "entity_type",
                    sa.String(),
                    nullable=False,
                    server_default="repository",
                )
            )
            batch_op.alter_column(
                "full_name",
                new_column_name="canonical_name",
                existing_type=sa.String(),
            )
            batch_op.alter_column(
                "repository_id",
                new_column_name="entity_id",
                existing_type=sa.String(),
            )
        op.create_index(
            "ix_entities_source_entity_type",
            "repositories",
            ["source", "entity_type"],
        )
        op.create_index(
            "ix_entities_canonical_name",
            "repositories",
            ["canonical_name"],
        )
        op.rename_table("repositories", "entities")
