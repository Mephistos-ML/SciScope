"""Flatten repository-only persistence schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_repository_schema_cleanup"
down_revision = "0005_repository_only_cleanup"
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


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

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
            if _has_column(inspector, "repository_checkpoints", "repository_id"):
                batch_op.alter_column(
                    "repository_id",
                    new_column_name="entity_id",
                    existing_type=sa.String(),
                )
        inspector = sa.inspect(bind)
        if not _has_index(
            inspector,
            "repository_checkpoints",
            "ix_entity_checkpoints_subscription",
        ):
            op.create_index(
                "ix_entity_checkpoints_subscription",
                "repository_checkpoints",
                ["subscription_id"],
            )
        if not _has_table(inspector, "entity_checkpoints"):
            op.rename_table("repository_checkpoints", "entity_checkpoints")
        inspector = sa.inspect(bind)

    if _has_table(inspector, "subscription_repository_matches"):
        if _has_index(
            inspector,
            "subscription_repository_matches",
            "ix_subscription_repository_matches_subscription",
        ):
            op.drop_index(
                "ix_subscription_repository_matches_subscription",
                table_name="subscription_repository_matches",
            )
        if _has_index(
            inspector,
            "subscription_repository_matches",
            "ix_subscription_repository_matches_source",
        ):
            op.drop_index(
                "ix_subscription_repository_matches_source",
                table_name="subscription_repository_matches",
            )
        with op.batch_alter_table("subscription_repository_matches") as batch_op:
            if not _has_column(
                inspector,
                "subscription_repository_matches",
                "excluded_terms_json",
            ):
                batch_op.add_column(
                    sa.Column(
                        "excluded_terms_json",
                        sa.JSON(),
                        nullable=False,
                        server_default="[]",
                    )
                )
            if not _has_column(inspector, "subscription_repository_matches", "active"):
                batch_op.add_column(
                    sa.Column(
                        "active",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.true(),
                    )
                )
            if _has_column(
                inspector,
                "subscription_repository_matches",
                "repository_id",
            ):
                batch_op.alter_column(
                    "repository_id",
                    new_column_name="entity_id",
                    existing_type=sa.String(),
                )
        inspector = sa.inspect(bind)
        if not _has_index(
            inspector,
            "subscription_repository_matches",
            "ix_subscription_entity_matches_subscription",
        ):
            op.create_index(
                "ix_subscription_entity_matches_subscription",
                "subscription_repository_matches",
                ["subscription_id"],
            )
        if not _has_index(
            inspector,
            "subscription_repository_matches",
            "ix_subscription_entity_matches_source",
        ):
            op.create_index(
                "ix_subscription_entity_matches_source",
                "subscription_repository_matches",
                ["source"],
            )
        if not _has_table(inspector, "subscription_entity_matches"):
            op.rename_table(
                "subscription_repository_matches",
                "subscription_entity_matches",
            )
        inspector = sa.inspect(bind)

    if _has_table(inspector, "repositories"):
        if _has_index(inspector, "repositories", "ix_repositories_source"):
            op.drop_index("ix_repositories_source", table_name="repositories")
        if _has_index(inspector, "repositories", "ix_repositories_full_name"):
            op.drop_index("ix_repositories_full_name", table_name="repositories")
        with op.batch_alter_table("repositories") as batch_op:
            if not _has_column(inspector, "repositories", "entity_type"):
                batch_op.add_column(
                    sa.Column(
                        "entity_type",
                        sa.String(),
                        nullable=False,
                        server_default="repository",
                    )
                )
            if _has_column(inspector, "repositories", "full_name"):
                batch_op.alter_column(
                    "full_name",
                    new_column_name="canonical_name",
                    existing_type=sa.String(),
                )
            if _has_column(inspector, "repositories", "repository_id"):
                batch_op.alter_column(
                    "repository_id",
                    new_column_name="entity_id",
                    existing_type=sa.String(),
                )
        inspector = sa.inspect(bind)
        if not _has_index(inspector, "repositories", "ix_entities_source_entity_type"):
            op.create_index(
                "ix_entities_source_entity_type",
                "repositories",
                ["source", "entity_type"],
            )
        if not _has_index(inspector, "repositories", "ix_entities_canonical_name"):
            op.create_index(
                "ix_entities_canonical_name",
                "repositories",
                ["canonical_name"],
            )
        if not _has_table(inspector, "entities"):
            op.rename_table("repositories", "entities")
