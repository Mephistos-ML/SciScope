"""Add durable Explore search run execution records."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_search_run_observability"
down_revision = "0013_feed_event_opaque_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_runs",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.String(),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("topic_description", sa.Text(), nullable=False),
        sa.Column("topic_hash", sa.String(), nullable=False),
        sa.Column("response_mode", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("planner_mode", sa.String(), nullable=False),
        sa.Column("planner_model", sa.String(), nullable=True),
        sa.Column("ranking_policy_version", sa.String(), nullable=False),
        sa.Column("backend_revision", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("partial", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("response_payload_json", sa.JSON(), nullable=True),
        sa.Column("execution_state_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_search_runs_owner_created", "search_runs", ["owner_user_id", "created_at"])
    op.create_index("ix_search_runs_status_created", "search_runs", ["status", "created_at"])

    op.create_table(
        "search_run_operations",
        sa.Column("operation_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(),
            sa.ForeignKey("search_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_holder_id", sa.String(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_search_run_operations_run_queued",
        "search_run_operations",
        ["run_id", "queued_at"],
    )

    op.create_table(
        "search_run_stages",
        sa.Column(
            "run_id",
            sa.String(),
            sa.ForeignKey("search_runs.run_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("stage_number", sa.Integer(), primary_key=True),
        sa.Column(
            "operation_id",
            sa.String(),
            sa.ForeignKey("search_run_operations.operation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("executed_query_ids_json", sa.JSON(), nullable=False),
        sa.Column("retrieved_candidate_count", sa.Integer(), nullable=False),
        sa.Column("admitted_candidate_count", sa.Integer(), nullable=False),
        sa.Column("visible_candidate_count", sa.Integer(), nullable=False),
        sa.Column("timings_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_search_run_stages_operation", "search_run_stages", ["operation_id"])

    op.create_table(
        "search_run_provider_outcomes",
        sa.Column("outcome_id", sa.String(), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(),
            sa.ForeignKey("search_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "operation_id",
            sa.String(),
            sa.ForeignKey("search_run_operations.operation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage_number", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("query_id", sa.String(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("retry_after_seconds", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_search_run_provider_outcomes_stage",
        "search_run_provider_outcomes",
        ["run_id", "stage_number"],
    )
    op.create_index(
        "ix_search_run_provider_outcomes_source_channel",
        "search_run_provider_outcomes",
        ["source", "channel"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_search_run_provider_outcomes_source_channel",
        table_name="search_run_provider_outcomes",
    )
    op.drop_index(
        "ix_search_run_provider_outcomes_stage",
        table_name="search_run_provider_outcomes",
    )
    op.drop_table("search_run_provider_outcomes")
    op.drop_index("ix_search_run_stages_operation", table_name="search_run_stages")
    op.drop_table("search_run_stages")
    op.drop_index(
        "ix_search_run_operations_run_queued",
        table_name="search_run_operations",
    )
    op.drop_table("search_run_operations")
    op.drop_index("ix_search_runs_status_created", table_name="search_runs")
    op.drop_index("ix_search_runs_owner_created", table_name="search_runs")
    op.drop_table("search_runs")
