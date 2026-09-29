"""Add durable Explore search run execution records."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_search_run_observability"
down_revision = "0013_feed_event_opaque_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_ranking_dataset_examples_run_rank", table_name="ranking_dataset_examples")
    op.drop_table("ranking_dataset_examples")
    op.drop_index("ix_ranking_dataset_runs_user_created_at", table_name="ranking_dataset_runs")
    op.drop_table("ranking_dataset_runs")
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
    op.create_table(
        "search_run_ranking_candidates",
        sa.Column(
            "run_id",
            sa.String(),
            sa.ForeignKey("search_runs.run_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("stage_number", sa.Integer(), primary_key=True),
        sa.Column("repository_id", sa.String(), primary_key=True),
        sa.Column("repository_source", sa.String(), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("candidate_facts_json", sa.JSON(), nullable=False),
        sa.Column("retrieval_facts_json", sa.JSON(), nullable=False),
        sa.Column("admission_facts_json", sa.JSON(), nullable=False),
        sa.Column("ranking_features_json", sa.JSON(), nullable=False),
        sa.Column("score_breakdown_json", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_search_run_ranking_candidates_run_stage_rank",
        "search_run_ranking_candidates",
        ["run_id", "stage_number", "rank_position"],
    )
    op.create_index(
        "ix_search_run_ranking_candidates_repository",
        "search_run_ranking_candidates",
        ["repository_id"],
    )
    op.create_table(
        "search_run_ranking_labels",
        sa.Column(
            "run_id",
            sa.String(),
            sa.ForeignKey("search_runs.run_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("repository_id", sa.String(), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("stage_number", sa.Integer(), nullable=False),
        sa.Column("label", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_search_run_ranking_labels_run_stage",
        "search_run_ranking_labels",
        ["run_id", "stage_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_search_run_ranking_labels_run_stage",
        table_name="search_run_ranking_labels",
    )
    op.drop_table("search_run_ranking_labels")
    op.drop_index(
        "ix_search_run_ranking_candidates_repository",
        table_name="search_run_ranking_candidates",
    )
    op.drop_index(
        "ix_search_run_ranking_candidates_run_stage_rank",
        table_name="search_run_ranking_candidates",
    )
    op.drop_table("search_run_ranking_candidates")
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
    op.create_table(
        "ranking_dataset_runs",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("search_job_id", sa.String(), nullable=False, unique=True),
        sa.Column("topic_description", sa.Text(), nullable=False),
        sa.Column("generated_queries_json", sa.JSON(), nullable=False),
        sa.Column("ranking_policy_version", sa.String(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_ranking_dataset_runs_user_created_at",
        "ranking_dataset_runs",
        ["user_id", "created_at"],
    )
    op.create_table(
        "ranking_dataset_examples",
        sa.Column(
            "run_id",
            sa.String(),
            sa.ForeignKey("ranking_dataset_runs.run_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("repository_id", sa.String(), primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.Column("ranking_score", sa.Float(), nullable=False),
        sa.Column("candidate_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("features_json", sa.JSON(), nullable=False),
        sa.Column("manual_label", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_ranking_dataset_examples_run_rank",
        "ranking_dataset_examples",
        ["run_id", "rank_position"],
    )
