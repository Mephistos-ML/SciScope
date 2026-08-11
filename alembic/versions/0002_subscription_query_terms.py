"""Rename subscription query storage to query_terms_json."""

from __future__ import annotations

from alembic import op

revision = "0002_subscription_query_terms"
down_revision = "0001_postgres_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "subscriptions",
        "manual_keywords_json",
        new_column_name="query_terms_json",
        existing_type=None,
    )


def downgrade() -> None:
    op.alter_column(
        "subscriptions",
        "query_terms_json",
        new_column_name="manual_keywords_json",
        existing_type=None,
    )
