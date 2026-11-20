"""Add optional, immutable scientific context to durable search runs.

Existing rows remain null. Apply before deploying the new reader/writer.
"""

from alembic import op
import sqlalchemy as sa

revision = "0019_search_scientific_domain"
down_revision = "0018_repository_profile_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("search_runs", sa.Column("scientific_domain", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("search_runs", "scientific_domain")
