"""Add durable per-user feed events for monitored repository updates."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_feed_events"
down_revision = "0006_explore_usage_events"
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

    if not _has_table(inspector, "feed_events"):
        op.create_table(
            "feed_events",
            sa.Column("event_id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("subscription_id", sa.String(), nullable=False),
            sa.Column("repository_id", sa.String(), nullable=False),
            sa.Column("repository_full_name", sa.String(), nullable=False),
            sa.Column("repository_source", sa.String(), nullable=False),
            sa.Column("repository_url", sa.Text(), nullable=False),
            sa.Column("selected_query", sa.Text(), nullable=True),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("item_id", sa.String(), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("url", sa.Text(), nullable=False),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("normalized_text", sa.Text(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("event_id"),
        )
        inspector = sa.inspect(bind)

    indexes = (
        ("ix_feed_events_user_created_at", ["user_id", "created_at"]),
        ("ix_feed_events_user_published_at", ["user_id", "published_at"]),
        ("ix_feed_events_subscription_created_at", ["subscription_id", "created_at"]),
        ("ix_feed_events_repository_created_at", ["repository_id", "created_at"]),
    )
    for index_name, columns in indexes:
        if _has_index(inspector, "feed_events", index_name):
            continue
        op.create_index(index_name, "feed_events", list(columns))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "feed_events"):
        return

    for index_name in (
        "ix_feed_events_repository_created_at",
        "ix_feed_events_subscription_created_at",
        "ix_feed_events_user_published_at",
        "ix_feed_events_user_created_at",
    ):
        if _has_index(inspector, "feed_events", index_name):
            op.drop_index(index_name, table_name="feed_events")
    op.drop_table("feed_events")
