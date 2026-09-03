"""Add vector-backed semantic retrieval for the repository catalog."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_semantic_catalog"
down_revision = "0009_product_table_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        embedding_type = sa.Text()
    else:
        embedding_type = sa.JSON()

    op.create_table(
        "repository_query_embeddings",
        sa.Column("query_normalized", sa.String(), primary_key=True),
        sa.Column("embedding", embedding_type, nullable=False),
        sa.Column("embedding_model", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "repository_profile_embeddings",
        sa.Column("repository_id", sa.String(), primary_key=True),
        sa.Column("embedding", embedding_type, nullable=False),
        sa.Column("embedding_model", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE repository_query_embeddings "
            "ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector"
        )
        op.execute(
            "ALTER TABLE repository_profile_embeddings "
            "ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector"
        )
        op.execute(
            "CREATE INDEX ix_repository_query_embeddings_cosine "
            "ON repository_query_embeddings USING hnsw (embedding vector_cosine_ops)"
        )
        op.execute(
            "CREATE INDEX ix_repository_profile_embeddings_cosine "
            "ON repository_profile_embeddings USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_repository_profile_embeddings_cosine")
        op.execute("DROP INDEX IF EXISTS ix_repository_query_embeddings_cosine")
    op.drop_table("repository_profile_embeddings")
    op.drop_table("repository_query_embeddings")
