"""Rename subscription query strategy to search scope."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_ai_search_plan_foundation"
down_revision = "0003_auth_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        column["name"]
        for column in inspector.get_columns("subscriptions")
    }

    if "query_strategy" in columns and "search_scope" not in columns:
        op.alter_column(
            "subscriptions",
            "query_strategy",
            new_column_name="search_scope",
            existing_type=sa.String(),
        )
        op.execute(
            sa.text(
                """
                UPDATE subscriptions
                SET search_scope = :search_scope
                WHERE search_scope IN (:pending_ai, :profile_terms)
                """
            ).bindparams(
                search_scope="repositories",
                pending_ai="pending_ai",
                profile_terms="profile_terms",
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        column["name"]
        for column in inspector.get_columns("subscriptions")
    }

    if "search_scope" in columns and "query_strategy" not in columns:
        op.execute(
            sa.text(
                """
                UPDATE subscriptions
                SET search_scope = :query_strategy
                WHERE search_scope IN (:repositories, :all_scope)
                """
            ).bindparams(
                query_strategy="profile_terms",
                repositories="repositories",
                all_scope="all",
            )
        )
        op.alter_column(
            "subscriptions",
            "search_scope",
            new_column_name="query_strategy",
            existing_type=sa.String(),
        )
