"""Turn watched repositories into a searchable global catalog."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_repository_catalog"
down_revision = "0007_feed_events"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns: tuple[tuple[str, sa.Column[object]], ...] = (
        ("provider_repository_id", sa.Column("provider_repository_id", sa.String(), nullable=True)),
        ("owner_login", sa.Column("owner_login", sa.String(), nullable=True)),
        ("description", sa.Column("description", sa.Text(), nullable=True)),
        ("language", sa.Column("language", sa.String(), nullable=True)),
        ("stars", sa.Column("stars", sa.Integer(), nullable=True)),
        ("topics_json", sa.Column("topics_json", sa.JSON(), nullable=True)),
        ("search_text", sa.Column("search_text", sa.Text(), nullable=True)),
        ("first_seen_at", sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True)),
        ("last_seen_at", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)),
        ("last_retrieved_at", sa.Column("last_retrieved_at", sa.DateTime(timezone=True), nullable=True)),
        ("provider_updated_at", sa.Column("provider_updated_at", sa.DateTime(timezone=True), nullable=True)),
    )
    with op.batch_alter_table("repositories") as batch_op:
        for name, column in columns:
            if not _has_column(inspector, "repositories", name):
                batch_op.add_column(column)

    op.execute(
        sa.text(
            """
            UPDATE repositories
            SET provider_repository_id = COALESCE(NULLIF(provider_repository_id, ''), repository_id),
                owner_login = COALESCE(owner_login, ''),
                description = COALESCE(description, ''),
                language = COALESCE(language, ''),
                stars = COALESCE(stars, 0),
                topics_json = COALESCE(topics_json, '[]'),
                search_text = COALESCE(search_text, full_name),
                first_seen_at = COALESCE(first_seen_at, created_at),
                last_seen_at = COALESCE(last_seen_at, updated_at),
                last_retrieved_at = COALESCE(last_retrieved_at, updated_at)
            """
        )
    )
    with op.batch_alter_table("repositories") as batch_op:
        for name, type_ in (
            ("provider_repository_id", sa.String()),
            ("owner_login", sa.String()),
            ("description", sa.Text()),
            ("language", sa.String()),
            ("stars", sa.Integer()),
            ("topics_json", sa.JSON()),
            ("search_text", sa.Text()),
            ("first_seen_at", sa.DateTime(timezone=True)),
            ("last_seen_at", sa.DateTime(timezone=True)),
            ("last_retrieved_at", sa.DateTime(timezone=True)),
        ):
            batch_op.alter_column(name, existing_type=type_, nullable=False)

    inspector = sa.inspect(bind)
    if not _has_index(
        inspector,
        "repositories",
        "ux_repositories_source_provider_repository_id",
    ):
        op.create_index(
            "ux_repositories_source_provider_repository_id",
            "repositories",
            ["source", "provider_repository_id"],
            unique=True,
        )

    if not inspector.has_table("repository_search_evidence"):
        op.create_table(
            "repository_search_evidence",
            sa.Column("repository_id", sa.String(), nullable=False),
            sa.Column("query_normalized", sa.String(), nullable=False),
            sa.Column("channel", sa.String(), nullable=False),
            sa.Column("match_location", sa.String(), nullable=False),
            sa.Column("matched_path", sa.String(), nullable=False, server_default=""),
            sa.Column("matched_excerpt", sa.Text(), nullable=False, server_default=""),
            sa.Column("provider_rank", sa.Integer(), nullable=True),
            sa.Column("hit_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint(
                "repository_id",
                "query_normalized",
                "channel",
                "match_location",
                "matched_path",
            ),
        )
        op.create_index(
            "ix_repository_search_evidence_query",
            "repository_search_evidence",
            ["query_normalized"],
        )
        op.create_index(
            "ix_repository_search_evidence_repository",
            "repository_search_evidence",
            ["repository_id"],
        )

    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX ix_repositories_search_text_fts ON repositories "
            "USING gin (to_tsvector('simple', search_text))"
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_repositories_search_text_fts")
    if inspector.has_table("repository_search_evidence"):
        op.drop_table("repository_search_evidence")
    if _has_index(inspector, "repositories", "ux_repositories_source_provider_repository_id"):
        op.drop_index("ux_repositories_source_provider_repository_id", table_name="repositories")
    with op.batch_alter_table("repositories") as batch_op:
        for name in (
            "provider_updated_at",
            "last_retrieved_at",
            "last_seen_at",
            "first_seen_at",
            "search_text",
            "topics_json",
            "stars",
            "language",
            "description",
            "owner_login",
            "provider_repository_id",
        ):
            batch_op.drop_column(name)
