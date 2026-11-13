"""Shared migration behavior checked on SQLite and supported PostgreSQL."""

from datetime import UTC, datetime
import sqlalchemy as sa
from tests.fixtures.database import migrate_test_database


def verify_profile_metadata_migration(database_url: str) -> None:
    migrate_test_database(database_url, "0017_feed_update_groups")
    engine = sa.create_engine(database_url)
    profiles = sa.Table("repositories", sa.MetaData(), autoload_with=engine)
    now = datetime(2026, 11, 13, tzinfo=UTC)
    metadata = {"repo": "science/tool", "custom": {"keep": True}, "stars": 12,
                "star_count": 12, "stargazers_count": 12}
    values = {"repository_id": "github:repo:1", "source": "github", "full_name": "science/tool",
              "url": "https://github.com/science/tool", "provider_repository_id": "1",
              "metadata_json": metadata, "stars": 12}
    for column in profiles.columns:
        if not column.nullable and column.name not in values:
            if isinstance(column.type, sa.DateTime):
                values[column.name] = now
            elif isinstance(column.type, sa.JSON):
                values[column.name] = []
            elif isinstance(column.type, sa.Integer):
                values[column.name] = 0
            else:
                values[column.name] = ""
    with engine.begin() as connection:
        connection.execute(profiles.insert().values(**values))
    migrate_test_database(database_url)
    current = sa.Table("repositories", sa.MetaData(), autoload_with=engine)
    with engine.connect() as connection:
        row = connection.execute(sa.select(current)).mappings().one()
    engine.dispose()
    assert row["repository_id"] == "github:repo:1"
    assert row["full_name"] == "science/tool"
    assert row["metadata_json"] == {"repo": "science/tool", "custom": {"keep": True}}
