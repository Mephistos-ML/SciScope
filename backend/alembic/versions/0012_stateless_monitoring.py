"""Add durable state for stateless repository monitoring jobs."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_stateless_monitoring"
down_revision = "0011_feed_read_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repository_monitoring_cursors",
        sa.Column("repository_id", sa.String(), primary_key=True),
        sa.Column("checkpoint_key", sa.String(), primary_key=True),
        sa.Column("checkpoint_value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "monitoring_job_leases",
        sa.Column("job_name", sa.String(), primary_key=True),
        sa.Column("holder_id", sa.String(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "monitoring_runs",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("scanned_repository_count", sa.Integer(), nullable=False),
        sa.Column("failed_repository_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
    )
    op.create_index("ix_monitoring_runs_started_at", "monitoring_runs", ["started_at"])
    op.create_table(
        "repository_monitoring_checks",
        sa.Column("repository_id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_repository_monitoring_checks_repository_checked", "repository_monitoring_checks", ["repository_id", "checked_at"])


def downgrade() -> None:
    op.drop_index("ix_repository_monitoring_checks_repository_checked", table_name="repository_monitoring_checks")
    op.drop_table("repository_monitoring_checks")
    op.drop_index("ix_monitoring_runs_started_at", table_name="monitoring_runs")
    op.drop_table("monitoring_runs")
    op.drop_table("monitoring_job_leases")
    op.drop_table("repository_monitoring_cursors")
