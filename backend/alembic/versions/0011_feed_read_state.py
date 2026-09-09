"""Add Feed read state and chronological query indexes."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_feed_read_state"
down_revision = "0010_semantic_catalog"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "user_feed_events", "read_at"):
        op.add_column(
            "user_feed_events",
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        )

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "user_feed_events", "ix_user_feed_events_user_read_at"):
        op.create_index(
            "ix_user_feed_events_user_read_at",
            "user_feed_events",
            ["user_id", "read_at"],
        )

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "user_feed_events", "ix_user_feed_events_user_chronological"):
        op.create_index(
            "ix_user_feed_events_user_chronological",
            "user_feed_events",
            ["user_id", "published_at", "created_at", "event_id"],
        )

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "user_feed_events", "ix_user_feed_events_user_read_chronological"):
        op.create_index(
            "ix_user_feed_events_user_read_chronological",
            "user_feed_events",
            ["user_id", "read_at", "published_at", "created_at", "event_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_index(inspector, "user_feed_events", "ix_user_feed_events_user_read_chronological"):
        op.drop_index("ix_user_feed_events_user_read_chronological", table_name="user_feed_events")
    if _has_index(inspector, "user_feed_events", "ix_user_feed_events_user_chronological"):
        op.drop_index("ix_user_feed_events_user_chronological", table_name="user_feed_events")
    if _has_index(inspector, "user_feed_events", "ix_user_feed_events_user_read_at"):
        op.drop_index("ix_user_feed_events_user_read_at", table_name="user_feed_events")
    if _has_column(inspector, "user_feed_events", "read_at"):
        op.drop_column("user_feed_events", "read_at")
