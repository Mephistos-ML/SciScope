"""Rename application tables to product-oriented names."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_product_table_names"
down_revision = "0008_repository_catalog"
branch_labels = None
depends_on = None


_TABLE_RENAMES = (
    ("oauth_accounts", "user_identities"),
    ("explore_search_events", "search_access_events"),
    ("feed_events", "user_feed_events"),
    ("repository_search_evidence", "repository_query_evidence"),
    ("repository_checkpoints", "subscription_scan_cursors"),
    ("subscriptions", "repository_subscriptions"),
)

_INDEX_RENAMES = (
    ("ix_oauth_accounts_user_id_provider", "ix_user_identities_user_id_provider"),
    ("ux_oauth_accounts_provider_subject", "ux_user_identities_provider_subject"),
    ("ix_explore_search_events_subject_created_at", "ix_search_access_events_subject_created_at"),
    ("ix_explore_search_events_outcome_created_at", "ix_search_access_events_outcome_created_at"),
    ("ix_explore_search_events_created_at", "ix_search_access_events_created_at"),
    ("ix_explore_search_events_user_id_created_at", "ix_search_access_events_user_id_created_at"),
    ("ix_feed_events_user_created_at", "ix_user_feed_events_user_created_at"),
    ("ix_feed_events_user_published_at", "ix_user_feed_events_user_published_at"),
    ("ix_feed_events_subscription_created_at", "ix_user_feed_events_subscription_created_at"),
    ("ix_feed_events_repository_created_at", "ix_user_feed_events_repository_created_at"),
    ("ix_repository_search_evidence_query", "ix_repository_query_evidence_query"),
    ("ix_repository_search_evidence_repository", "ix_repository_query_evidence_repository"),
    ("ix_repository_checkpoints_subscription", "ix_subscription_scan_cursors_subscription"),
    ("ix_subscriptions_user_id_created_at", "ix_repository_subscriptions_user_id_created_at"),
    ("ux_subscriptions_user_repository", "ux_repository_subscriptions_user_repository"),
)


def upgrade() -> None:
    for old_name, new_name in _TABLE_RENAMES:
        op.rename_table(old_name, new_name)
    _rename_postgres_indexes(_INDEX_RENAMES)
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


def downgrade() -> None:
    op.drop_index(
        "ix_ranking_dataset_examples_run_rank",
        table_name="ranking_dataset_examples",
    )
    op.drop_table("ranking_dataset_examples")
    op.drop_index(
        "ix_ranking_dataset_runs_user_created_at",
        table_name="ranking_dataset_runs",
    )
    op.drop_table("ranking_dataset_runs")
    _rename_postgres_indexes(tuple((new, old) for old, new in _INDEX_RENAMES))
    for old_name, new_name in reversed(_TABLE_RENAMES):
        op.rename_table(new_name, old_name)


def _rename_postgres_indexes(index_renames: tuple[tuple[str, str], ...]) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for old_name, new_name in index_renames:
        op.execute(f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"')
