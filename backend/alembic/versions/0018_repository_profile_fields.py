"""Remove the retired repository popularity field.

Coordinate API/worker cutover before applying: prior binaries select this column.
Downgrade restores the shape with unknown historical values represented as zero;
restoring the former values requires a database backup.
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_repository_profile_fields"
down_revision = "0017_feed_update_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Canonical profile metadata is current product state, unlike immutable run
    # reports. Remove retired keys there while preserving unrelated extension data.
    bind = op.get_bind()
    profiles = sa.table("repositories", sa.column("repository_id", sa.String()),
                        sa.column("metadata_json", sa.JSON()))
    last_id = None
    while True:
        query = sa.select(profiles.c.repository_id, profiles.c.metadata_json).order_by(profiles.c.repository_id).limit(500)
        if last_id is not None:
            query = query.where(profiles.c.repository_id > last_id)
        rows = bind.execute(query).all()
        if not rows:
            break
        for repository_id, metadata in rows:
            if not isinstance(metadata, dict):
                continue
            cleaned = {key: value for key, value in metadata.items()
                       if key not in {"stars", "star_count", "stargazers_count"}}
            if cleaned != metadata:
                bind.execute(profiles.update().where(profiles.c.repository_id == repository_id)
                             .values(metadata_json=cleaned))
        last_id = rows[-1][0]
    op.drop_column("repositories", "stars")


def downgrade() -> None:
    op.add_column("repositories", sa.Column("stars", sa.Integer(), nullable=False, server_default="0"))
