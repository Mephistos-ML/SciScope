"""Switch subscriptions to direct repository watches."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_direct_repository_subscriptions"
down_revision = "0006_repository_schema_cleanup"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


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

    if _has_table(inspector, "subscription_repository_matches"):
        op.drop_table("subscription_repository_matches")
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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("subscription_id"),
    )
    op.create_index(
        "ix_subscriptions_user_id_created_at",
        "subscriptions",
        ["user_id", "created_at"],
    )

    op.create_table(
        "subscription_repository_matches",
        sa.Column("subscription_id", sa.String(), nullable=False),
        sa.Column("repository_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("matched_terms_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("subscription_id", "repository_id"),
    )
    op.create_index(
        "ix_subscription_repository_matches_subscription",
        "subscription_repository_matches",
        ["subscription_id"],
    )
    op.create_index(
        "ix_subscription_repository_matches_source",
        "subscription_repository_matches",
        ["source"],
    )
