"""Persistence failures preserve rollback, stable categories, and diagnostic causes."""

from datetime import UTC, datetime

import psycopg.errors
import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.database.records.auth import UserRecordModel
from app.database.session import get_engine
from app.models.persistence import PersistenceConflictError, PersistenceError, PersistenceUnavailableError
from app.storage.auth.users import create_user, get_user_by_id
from app.storage.transaction import persistence_session
from tests.conftest import build_test_database_url, migrate_test_database


def test_commit_conflict_rolls_back_all_related_writes(tmp_path):
    url = build_test_database_url(tmp_path / "rollback.sqlite3")
    migrate_test_database(url)
    create_user(user_id="existing", email="private@example.test", display_name="Existing", database_url=url)
    now = datetime.now(UTC)
    with pytest.raises(PersistenceConflictError) as failure:
        with persistence_session(url) as session:
            session.add(UserRecordModel(user_id="temporary", email="temporary@example.test", display_name="Temporary", created_at=now, updated_at=now))
            session.flush()
            session.add(UserRecordModel(user_id="duplicate", email="private@example.test", display_name="Duplicate", created_at=now, updated_at=now))
    assert isinstance(failure.value.__cause__, IntegrityError)
    assert "private@example.test" not in str(failure.value)
    assert get_user_by_id("temporary", database_url=url) is None
    assert get_user_by_id("duplicate", database_url=url) is None
    assert get_user_by_id("existing", database_url=url) is not None


@pytest.mark.parametrize("driver_error,category", [
    (psycopg.errors.ConnectionFailure, PersistenceUnavailableError),
    (psycopg.errors.AdminShutdown, PersistenceUnavailableError),
    (psycopg.errors.DeadlockDetected, PersistenceConflictError),
    (psycopg.errors.SerializationFailure, PersistenceConflictError),
    (psycopg.errors.UndefinedTable, PersistenceError),
])
def test_postgres_driver_errors_translate_at_transaction_boundary(tmp_path, driver_error, category):
    # This tests driver-error translation, not PostgreSQL locking/isolation.
    url = build_test_database_url(tmp_path / "driver-errors.sqlite3")
    engine = get_engine(url)
    original = DBAPIError("private SQL", {"secret": "private parameter"}, driver_error("private diagnostics"))
    def fail(*args):
        raise original
    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(category) as failure:
            with persistence_session(url) as session:
                session.execute(text("SELECT 1"))
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert type(failure.value) is category
    assert failure.value.__cause__ is original
    assert "private" not in str(failure.value)


def test_missing_schema_is_not_classified_as_temporary_unavailability(tmp_path):
    url = build_test_database_url(tmp_path / "missing-schema.sqlite3")
    with pytest.raises(PersistenceError) as failure:
        get_user_by_id("missing", database_url=url)
    assert type(failure.value) is PersistenceError
    assert isinstance(failure.value.__cause__, DBAPIError)


def test_application_exception_keeps_its_identity(tmp_path):
    original = ValueError("Invalid domain input")
    with pytest.raises(ValueError) as failure:
        with persistence_session(build_test_database_url(tmp_path / "application.sqlite3")):
            raise original
    assert failure.value is original


def test_pool_checkout_timeout_is_unavailable_and_preserves_cause(tmp_path):
    from sqlalchemy.exc import TimeoutError
    url = build_test_database_url(tmp_path / "pool.sqlite3")
    engine = get_engine(url)
    original = TimeoutError("private connection diagnostics")
    def fail(*args):
        raise original
    event.listen(engine, "checkout", fail)
    try:
        with pytest.raises(PersistenceUnavailableError) as failure:
            with persistence_session(url) as session:
                session.execute(text("SELECT 1"))
    finally:
        event.remove(engine, "checkout", fail)
    assert failure.value.__cause__ is original
    assert "private" not in str(failure.value)
