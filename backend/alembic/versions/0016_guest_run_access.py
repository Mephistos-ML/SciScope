"""Add run access, admission locking, fenced leases, and versioned replay state."""

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

    _version_execution_states()


def downgrade() -> None:
    op.drop_column("search_run_operations", "lease_token")
    op.drop_table("search_access_lock")
    op.drop_column("search_runs", "guest_access_token_hash")


def _version_execution_states() -> None:
    """Convert the unversioned stored shape once; runtime reads only version 1."""
    runs = sa.table(
        "search_runs",
        sa.column("run_id", sa.String()),
        sa.column("execution_state_json", sa.JSON()),
    )
    connection = op.get_bind()
    last_id = None
    while True:
        query = sa.select(runs.c.run_id, runs.c.execution_state_json).where(
            runs.c.execution_state_json.is_not(None),
        ).order_by(runs.c.run_id).limit(500)
        if last_id is not None:
            query = query.where(runs.c.run_id > last_id)
        batch = connection.execute(query).all()
        if not batch:
            break
        for run_id, state in batch:
            if not isinstance(state, dict) or "schemaVersion" in state:
                continue
            state = {**state, "schemaVersion": 1}
            retrieved = state.get("retrieved")
            if isinstance(retrieved, dict):
                # The old reader restored no lane outcomes. Preserve known facts
                # and represent the previously omitted information as empty.
                state["retrieved"] = {"laneOutcomes": [], **retrieved}
            connection.execute(sa.update(runs).where(runs.c.run_id == run_id).values(
                execution_state_json=state,
            ))
        last_id = batch[-1].run_id
