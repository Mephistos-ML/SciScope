"""Real PostgreSQL driver failures preserve atomic rollback and error categories."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url

from app.database.records.auth import UserRecordModel
from app.database.session import get_engine, session_scope
from app.models.persistence import PersistenceConflictError, PersistenceError
from app.storage.auth.users import create_user, get_user_by_id
from app.storage.transaction import persistence_session

pytestmark = pytest.mark.postgres


def add_temporary(session, user_id):
    now = datetime.now(UTC)
    session.add(UserRecordModel(user_id=user_id, email=f"{user_id}@example.test", display_name=user_id,
                               created_at=now, updated_at=now))
    session.flush()


@pytest.fixture
def users(postgres_url):
    for user_id in ("left", "right"):
        create_user(user_id=user_id, email=f"{user_id}@example.test", display_name="Original", database_url=postgres_url)
    return postgres_url


def test_row_lock_timeout_translates_and_rolls_back_all_writes(users):
    with session_scope(users) as owner:
        owner.scalar(select(UserRecordModel).where(UserRecordModel.user_id == "left").with_for_update())
        with pytest.raises(PersistenceConflictError) as failure:
            with persistence_session(users) as contender:
                contender.execute(text("SET LOCAL lock_timeout = '100ms'"))
                add_temporary(contender, "temporary")
                contender.execute(text("UPDATE users SET display_name='Contender' WHERE user_id='left'"))
    assert failure.value.__cause__.orig.sqlstate == "55P03"
    assert get_user_by_id("temporary", database_url=users) is None
    assert get_user_by_id("left", database_url=users).display_name == "Original"


def test_deadlock_aborts_one_transaction_without_partial_writes(users):
    ready = Barrier(2)
    def update(index):
        first, second = ("left", "right") if index == 0 else ("right", "left")
        try:
            with persistence_session(users) as session:
                add_temporary(session, f"temporary-{index}")
                session.execute(text("UPDATE users SET display_name=:name WHERE user_id=:id"),
                                {"name": str(index), "id": first})
                ready.wait(timeout=5)
                session.execute(text("UPDATE users SET display_name=:name WHERE user_id=:id"),
                                {"name": str(index), "id": second})
            return None
        except PersistenceConflictError as failure:
            return failure
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, (0, 1)))
    errors = [(index, result) for index, result in enumerate(results) if result is not None]
    assert len(errors) == 1
    loser, failure = errors[0]
    winner = 1 - loser
    assert failure.__cause__.orig.sqlstate == "40P01"
    assert get_user_by_id(f"temporary-{loser}", database_url=users) is None
    assert get_user_by_id(f"temporary-{winner}", database_url=users) is not None
    assert get_user_by_id("left", database_url=users).display_name == str(winner)
    assert get_user_by_id("right", database_url=users).display_name == str(winner)


def test_serialization_failure_is_a_conflict_and_rolls_back_related_writes(users):
    read = Event()
    updated = Event()
    def stale_update():
        with persistence_session(users) as session:
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            session.execute(text("SELECT display_name FROM users WHERE user_id='left'"))
            read.set()
            assert updated.wait(5)
            add_temporary(session, "temporary")
            session.execute(text("UPDATE users SET display_name='Stale' WHERE user_id='left'"))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(stale_update)
        try:
            assert read.wait(5)
            with persistence_session(users) as session:
                session.execute(text("UPDATE users SET display_name='Current' WHERE user_id='left'"))
        finally:
            updated.set()
        with pytest.raises(PersistenceConflictError) as failure:
            future.result(timeout=10)
    assert failure.value.__cause__.orig.sqlstate == "40001"
    assert get_user_by_id("temporary", database_url=users) is None
    assert get_user_by_id("left", database_url=users).display_name == "Current"


def test_application_isolation_does_not_inherit_a_server_default(postgres_url):
    url = make_url(postgres_url).update_query_dict({
        "options": "-c default_transaction_isolation=repeatable\\ read",
    })
    default = create_engine(url)
    try:
        with default.connect() as connection:
            assert connection.scalar(text("SHOW transaction_isolation")) == "repeatable read"
        engine = get_engine(url.render_as_string(hide_password=False))
        try:
            with engine.connect() as connection:
                assert connection.scalar(text("SHOW transaction_isolation")) == "read committed"
        finally:
            engine.dispose()
    finally:
        default.dispose()


def test_missing_schema_is_an_unexpected_failure_and_the_connection_recovers(postgres_url):
    with pytest.raises(PersistenceError) as failure:
        with persistence_session(postgres_url) as session:
            session.execute(text("SELECT * FROM missing_application_table"))
    assert type(failure.value) is PersistenceError
    assert failure.value.__cause__.orig.sqlstate == "42P01"
    with persistence_session(postgres_url) as session:
        assert session.scalar(text("SELECT 1")) == 1
