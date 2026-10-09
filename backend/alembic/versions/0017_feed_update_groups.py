"""Add immutable Feed publications with explicitly scoped event membership."""

from uuid import UUID, uuid5

from alembic import op
import sqlalchemy as sa

revision = "0017_feed_update_groups"
down_revision = "0016_guest_run_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ux_user_feed_events_group_scope", "user_feed_events",
                    ["event_id", "user_id", "subscription_id", "repository_id"], unique=True)
    groups = op.create_table(
        "user_feed_update_groups",
        sa.Column("group_id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("subscription_id", sa.String(), nullable=False),
        sa.Column("repository_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('release', 'commits')", name="ck_feed_update_group_kind"),
    )
    op.create_index("ux_feed_update_groups_scope", groups.name,
                    ["group_id", "user_id", "subscription_id", "repository_id"], unique=True)
    op.create_index("ix_feed_update_groups_user_created", groups.name, ["user_id", "created_at", "group_id"])
    op.create_index("ix_feed_update_groups_subscription_created", groups.name, ["subscription_id", "created_at", "group_id"])
    members = op.create_table(
        "user_feed_update_group_members",
        sa.Column("event_id", sa.String(), primary_key=True),
        sa.Column("group_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("subscription_id", sa.String(), nullable=False),
        sa.Column("repository_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id", "user_id", "subscription_id", "repository_id"],
            ["user_feed_update_groups.group_id", "user_feed_update_groups.user_id",
             "user_feed_update_groups.subscription_id", "user_feed_update_groups.repository_id"],
            ondelete="CASCADE", name="fk_feed_group_member_group_scope",
        ),
        sa.ForeignKeyConstraint(
            ["event_id", "user_id", "subscription_id", "repository_id"],
            ["user_feed_events.event_id", "user_feed_events.user_id",
             "user_feed_events.subscription_id", "user_feed_events.repository_id"],
            ondelete="CASCADE", name="fk_feed_group_member_event_scope",
        ),
    )
    op.create_index("ix_feed_update_group_members_group", members.name, ["group_id"])
    _preserve_event_publications(groups, members)


def _preserve_event_publications(groups, members) -> None:
    # Historical scan boundaries are unknown. Preserve each event as a singleton,
    # keeping its identity, timestamp, payload, and read state untouched.
    events = sa.table("user_feed_events", sa.column("event_id", sa.String()),
                      sa.column("user_id", sa.String()), sa.column("subscription_id", sa.String()),
                      sa.column("repository_id", sa.String()), sa.column("kind", sa.String()),
                      sa.column("created_at", sa.DateTime(timezone=True)))
    connection = op.get_bind()
    after = None
    # Frozen persisted identity algorithm; never import the evolving application.
    namespace = UUID("fc1663e6-3c3d-4b77-8adc-70fbffb44c93")
    while True:
        query = sa.select(events).order_by(events.c.event_id).limit(500)
        if after is not None:
            query = query.where(events.c.event_id > after)
        page = connection.execute(query).mappings().all()
        if not page:
            break
        group_rows, member_rows = [], []
        for row in page:
            if row["kind"] not in {"release", "commit"}:
                raise ValueError("Feed group migration requires release or commit events.")
            kind = "release" if row["kind"] == "release" else "commits"
            key = row["event_id"] if kind == "release" else f"historical:{row['event_id']}"
            group_id = str(uuid5(namespace, "\x1f".join((row["subscription_id"], kind, key))))
            scope = {name: row[name] for name in ("user_id", "subscription_id", "repository_id")}
            group_rows.append({**scope, "group_id": group_id, "kind": kind, "created_at": row["created_at"]})
            member_rows.append({**scope, "group_id": group_id, "event_id": row["event_id"]})
        connection.execute(groups.insert(), group_rows)
        connection.execute(members.insert(), member_rows)
        after = page[-1]["event_id"]


def downgrade() -> None:
    op.drop_table("user_feed_update_group_members")
    op.drop_table("user_feed_update_groups")
    op.drop_index("ux_user_feed_events_group_scope", table_name="user_feed_events")
