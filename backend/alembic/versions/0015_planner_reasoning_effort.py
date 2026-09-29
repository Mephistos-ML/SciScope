"""Store the reasoning policy used to plan an Explore search run."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_planner_reasoning_effort"
down_revision = "0014_search_run_observability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "search_runs",
        sa.Column("planner_reasoning_effort", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("search_runs", "planner_reasoning_effort")
