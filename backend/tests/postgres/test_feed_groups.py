"""Production-database migration, ownership constraints, and publication races."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from threading import Barrier

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa

from app.database.session import get_engine
from app.models.feed import build_feed_update_group_id
from app.models.persistence import PersistenceConflictError
from app.storage.feed.events import upsert_feed_events
from app.storage.feed.groups import publish_feed_update_groups
from tests.fixtures.database import BACKEND_ROOT, migrate_test_database
from tests.fixtures.feed import feed_event, feed_group

pytestmark = pytest.mark.postgres


def test_0017_backfills_multiple_pages_without_changing_event_facts_or_read_state(postgres_database_url, monkeypatch):
    url = postgres_database_url
    migrate_test_database(url, "0016_guest_run_access")
    engine = get_engine(url)
    table = sa.Table("user_feed_events", sa.MetaData(), autoload_with=engine)
    events = [feed_event(f"item:{index}", kind="release" if index % 2 == 0 else "commit") for index in range(501)]
    events[0] = replace(events[0], read_at=events[0].created_at)
    rows = []
    for event in events:
        values = asdict(event)
        values["metadata_json"] = values.pop("metadata")
        rows.append(values)
    with engine.begin() as connection:
        connection.execute(table.insert(), rows)
        before = connection.execute(sa.select(table).order_by(table.c.event_id)).mappings().all()
    migrate_test_database(url)
    with engine.connect() as connection:
        assert connection.execute(sa.select(table).order_by(table.c.event_id)).mappings().all() == before
        publications = connection.execute(sa.text("""
            SELECT g.group_id, g.kind, g.created_at, m.event_id
            FROM user_feed_update_groups g JOIN user_feed_update_group_members m USING (group_id)
            ORDER BY m.event_id
        """)).mappings().all()
        assert len(publications) == 501
        for stored, event in zip(publications, before, strict=True):
            kind = "release" if event["kind"] == "release" else "commits"
            key = event["event_id"] if kind == "release" else f"historical:{event['event_id']}"
            assert stored["group_id"] == build_feed_update_group_id(event["subscription_id"], kind, key)
            assert stored["kind"] == kind and stored["created_at"] == event["created_at"]
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    monkeypatch.setenv("DATABASE_URL", url)
    command.downgrade(config, "0016_guest_run_access")
    assert not sa.inspect(engine).has_table("user_feed_update_groups")
    with engine.connect() as connection:
        assert connection.execute(sa.select(table).order_by(table.c.event_id)).mappings().all() == before
    migrate_test_database(url)
    with engine.connect() as connection:
        assert connection.execute(sa.text("""
            SELECT g.group_id, g.kind, g.created_at, m.event_id
            FROM user_feed_update_groups g JOIN user_feed_update_group_members m USING (group_id)
            ORDER BY m.event_id
        """)).mappings().all() == publications


def test_database_rejects_membership_crossing_user_subscription_or_repository(postgres_url):
    engine = get_engine(postgres_url)
    own = feed_event()
    group = feed_group(own)
    publish_feed_update_groups((own,), (group,), database_url=postgres_url)
    for scope in ("user_id", "subscription_id", "repository_id"):
        foreign = replace(feed_event(f"foreign:{scope}"), **{scope: "other"})
        upsert_feed_events((foreign,), database_url=postgres_url)
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as connection:
                connection.execute(sa.text("""
                    INSERT INTO user_feed_update_group_members
                    (event_id, group_id, user_id, subscription_id, repository_id)
                    VALUES (:event_id, :group_id, :user_id, :subscription_id, :repository_id)
                """), {"event_id": foreign.event_id, "group_id": group.group_id,
                         "user_id": group.user_id, "subscription_id": group.subscription_id,
                         "repository_id": group.repository_id})
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT count(*) FROM user_feed_update_group_members")) == 1


def test_concurrent_publications_cannot_claim_the_same_event_or_leave_an_empty_group(postgres_url):
    engine = get_engine(postgres_url)
    event = feed_event()
    upsert_feed_events((event,), database_url=postgres_url)
    groups = [feed_group(event, publication_key=key) for key in ("scan-1", "scan-2")]
    barrier = Barrier(2)

    def synchronize(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO user_feed_update_group_members"):
            barrier.wait(timeout=10)

    sa.event.listen(engine, "before_cursor_execute", synchronize)

    def publish(group):
        try:
            publish_feed_update_groups((), (group,), database_url=postgres_url)
            return "published"
        except PersistenceConflictError:
            return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(publish, groups))
    finally:
        sa.event.remove(engine, "before_cursor_execute", synchronize)
    assert sorted(outcomes) == ["conflict", "published"]
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT count(*) FROM user_feed_update_groups")) == 1
        assert connection.scalar(sa.text("SELECT count(*) FROM user_feed_update_group_members")) == 1
        assert connection.scalar(sa.text("SELECT count(*) FROM user_feed_events")) == 1
