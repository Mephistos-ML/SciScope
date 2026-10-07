"""Add guest run access and serialize admission and fence worker claims."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016_guest_run_access"
down_revision = "0015_planner_reasoning_effort"
branch_labels = None
depends_on = None


def upgrade() -> None:
    lock = op.create_table(
        "search_access_lock",
        sa.Column("lock_id", sa.Integer(), primary_key=True),
    )
    op.bulk_insert(lock, [{"lock_id": 1}])
    op.add_column(
        "search_runs",
        sa.Column("guest_access_token_hash", sa.String(64), nullable=True),
    )

    op.add_column(
        "search_run_operations",
        sa.Column("lease_token", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("search_run_operations", "lease_token")
    op.drop_table("search_access_lock")
    op.drop_column("search_runs", "guest_access_token_hash")
