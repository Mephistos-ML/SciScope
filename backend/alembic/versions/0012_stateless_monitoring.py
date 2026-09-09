"""Add durable state for stateless repository monitoring jobs."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_stateless_monitoring"
down_revision = "0011_feed_read_state"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if _has_table(inspector, "subscription_scan_cursors"):
        if _has_index(
            inspector,
            "subscription_scan_cursors",
            "ix_subscription_scan_cursors_subscription",
        ):
            op.drop_index(
                "ix_subscription_scan_cursors_subscription",
                table_name="subscription_scan_cursors",
            )
        op.drop_table("subscription_scan_cursors")
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
    op.create_table(
        "subscription_scan_cursors",
        sa.Column("subscription_id", sa.String(), primary_key=True),
        sa.Column("repository_id", sa.String(), primary_key=True),
        sa.Column("checkpoint_key", sa.String(), primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("checkpoint_value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_subscription_scan_cursors_subscription",
        "subscription_scan_cursors",
        ["subscription_id"],
    )
