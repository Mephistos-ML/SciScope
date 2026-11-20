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


def assert_scientific_domain_upgrade(database_url):
    """A nullable context addition preserves historical and queued run facts."""
    from app.database.session import get_engine
    from app.storage.search_runs import get_search_run

    migrate_test_database(database_url, "0018_repository_profile_fields")
    engine = get_engine(database_url)
    runs = sa.Table("search_runs", sa.MetaData(), autoload_with=engine)
    operations = sa.Table("search_run_operations", sa.MetaData(), autoload_with=engine)
    state = {"schemaVersion": 2, "preserved": ["evidence"]}
    with engine.begin() as connection:
        connection.execute(runs.insert(), {
            "run_id": "legacy-domain", "topic_description": "Scientific software",
            "topic_hash": "hash", "status": "queued", "planner_mode": "bootstrap",
            "ranking_policy_version": "policy", "backend_revision": "revision",
            "created_at": datetime(2026, 11, 20, tzinfo=UTC), "partial": False,
            "execution_state_json": state,
        })
        connection.execute(operations.insert(), {
            "operation_id": "pending-domain", "run_id": "legacy-domain",
            "kind": "initial", "status": "queued",
            "queued_at": datetime(2026, 11, 20, tzinfo=UTC),
        })
    migrate_test_database(database_url)
    run = get_search_run("legacy-domain", database_url=database_url)
    assert run.scientific_domain is None
    assert run.topic_description == "Scientific software"
    assert run.execution_state == state
    with engine.connect() as connection:
        assert connection.scalar(sa.select(operations.c.status)) == "queued"
