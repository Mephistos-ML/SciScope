"""Drop subscription search scope for repository-only mode."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_repository_only_cleanup"
down_revision = "0004_ai_search_plan_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        column["name"]
        for column in inspector.get_columns("subscriptions")
    }

    if "search_scope" in columns:
        with op.batch_alter_table("subscriptions") as batch_op:
            batch_op.drop_column("search_scope")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        column["name"]
        for column in inspector.get_columns("subscriptions")
    }

    if "search_scope" not in columns:
        with op.batch_alter_table("subscriptions") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "search_scope",
                    sa.String(),
                    nullable=False,
                    server_default="repositories",
                )
            )
