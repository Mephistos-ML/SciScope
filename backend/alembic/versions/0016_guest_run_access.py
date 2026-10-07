"""Store guest access token hashes for Explore search runs."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016_guest_run_access"
down_revision = "0015_planner_reasoning_effort"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "search_runs",
        sa.Column("guest_access_token_hash", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("search_runs", "guest_access_token_hash")
