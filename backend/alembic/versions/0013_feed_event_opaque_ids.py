"""Replace provider-derived Feed event IDs with opaque UUIDv5 values."""

from __future__ import annotations

from uuid import UUID, uuid5

from alembic import op
import sqlalchemy as sa


revision = "0013_feed_event_opaque_ids"
down_revision = "0012_stateless_monitoring"
branch_labels = None
depends_on = None


FEED_EVENT_ID_NAMESPACE = UUID("e71b2aec-1284-582c-a932-f86ef904d44c")


def _build_event_id(subscription_id: str, source: str, item_id: str) -> str:
    return str(uuid5(FEED_EVENT_ID_NAMESPACE, "\x1f".join((subscription_id, source, item_id))))


def upgrade() -> None:
    feed_events = sa.table(
        "user_feed_events",
        sa.column("event_id", sa.String()),
        sa.column("subscription_id", sa.String()),
        sa.column("source", sa.String()),
        sa.column("item_id", sa.String()),
    )
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(
            feed_events.c.event_id,
            feed_events.c.subscription_id,
            feed_events.c.source,
            feed_events.c.item_id,
        )
    ).mappings()
    for row in rows:
        bind.execute(
            feed_events.update()
            .where(feed_events.c.event_id == row["event_id"])
            .values(
                event_id=_build_event_id(
                    row["subscription_id"],
                    row["source"],
                    row["item_id"],
                )
            )
        )


def downgrade() -> None:
    feed_events = sa.table(
        "user_feed_events",
        sa.column("event_id", sa.String()),
        sa.column("subscription_id", sa.String()),
        sa.column("source", sa.String()),
        sa.column("item_id", sa.String()),
    )
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(
            feed_events.c.event_id,
            feed_events.c.subscription_id,
            feed_events.c.source,
            feed_events.c.item_id,
        )
    ).mappings()
    for row in rows:
        bind.execute(
            feed_events.update()
            .where(feed_events.c.event_id == row["event_id"])
            .values(event_id=":".join((row["subscription_id"], row["source"], row["item_id"])))
        )
