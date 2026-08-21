"""Add durable explore usage events for abuse protection."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_explore_usage_events"
down_revision = "0005_direct_repo_subscriptions"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _has_index(
    inspector: sa.Inspector,
    table_name: str,
    index_name: str,
) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "explore_search_events"):
        op.create_table(
            "explore_search_events",
            sa.Column("event_id", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("user_id", sa.String(), nullable=True),
            sa.Column("subject_type", sa.String(), nullable=False),
            sa.Column("subject_key", sa.String(), nullable=False),
            sa.Column("ip_hash", sa.String(), nullable=True),
            sa.Column("topic_hash", sa.String(), nullable=False),
            sa.Column("outcome", sa.String(), nullable=False),
            sa.Column("retry_after_seconds", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("event_id"),
        )
        inspector = sa.inspect(bind)

    if not _has_index(
        inspector,
        "explore_search_events",
        "ix_explore_search_events_subject_created_at",
    ):
        op.create_index(
            "ix_explore_search_events_subject_created_at",
            "explore_search_events",
            ["subject_type", "subject_key", "created_at"],
        )
    if not _has_index(
        inspector,
        "explore_search_events",
        "ix_explore_search_events_outcome_created_at",
    ):
        op.create_index(
            "ix_explore_search_events_outcome_created_at",
            "explore_search_events",
            ["outcome", "created_at"],
        )
    if not _has_index(
        inspector,
        "explore_search_events",
        "ix_explore_search_events_created_at",
    ):
        op.create_index(
            "ix_explore_search_events_created_at",
            "explore_search_events",
            ["created_at"],
        )
    if not _has_index(
        inspector,
        "explore_search_events",
        "ix_explore_search_events_user_id_created_at",
    ):
        op.create_index(
            "ix_explore_search_events_user_id_created_at",
            "explore_search_events",
            ["user_id", "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "explore_search_events"):
        if _has_index(
            inspector,
            "explore_search_events",
            "ix_explore_search_events_user_id_created_at",
        ):
            op.drop_index(
                "ix_explore_search_events_user_id_created_at",
                table_name="explore_search_events",
            )
        if _has_index(
            inspector,
            "explore_search_events",
            "ix_explore_search_events_created_at",
        ):
            op.drop_index(
                "ix_explore_search_events_created_at",
                table_name="explore_search_events",
            )
        if _has_index(
            inspector,
            "explore_search_events",
            "ix_explore_search_events_outcome_created_at",
        ):
            op.drop_index(
                "ix_explore_search_events_outcome_created_at",
                table_name="explore_search_events",
            )
        if _has_index(
            inspector,
            "explore_search_events",
            "ix_explore_search_events_subject_created_at",
        ):
            op.drop_index(
                "ix_explore_search_events_subject_created_at",
                table_name="explore_search_events",
            )
        op.drop_table("explore_search_events")
