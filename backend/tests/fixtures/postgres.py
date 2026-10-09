"""Isolated migrated PostgreSQL databases and observable contention helpers."""

import os
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from app.database.session import get_engine
from tests.fixtures.database import migrate_test_database


def wait_until_blocked(connection, query_prefix):
    deadline = monotonic() + 5
    while monotonic() < deadline:
        waiting = connection.scalar(text("""
            SELECT count(*) FROM pg_stat_activity
            WHERE datname = current_database() AND wait_event_type = 'Lock'
              AND query LIKE :prefix AND pid <> pg_backend_pid()
        """), {"prefix": query_prefix + "%"})
        if waiting:
            return
        # Server-side bounded yield; correctness depends on observed locking, not sleep duration.
        connection.execute(text("SELECT pg_sleep(0.01)"))
    pytest.fail("The contender never reached the expected PostgreSQL lock wait.")


@pytest.fixture(scope="session")
def postgres_admin():
    url = make_url(os.environ["SCISCOPE_TEST_POSTGRES_URL"])
    if url.drivername != "postgresql+psycopg":
        pytest.fail("SCISCOPE_TEST_POSTGRES_URL must use postgresql+psycopg.")
    engine = create_engine(url, isolation_level="AUTOCOMMIT", poolclass=NullPool,
                           connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            version = int(connection.scalar(text("SHOW server_version_num")))
            if version < 160000:
                pytest.fail("The PostgreSQL correctness suite requires PostgreSQL 16 or newer.")
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def postgres_database_url(postgres_admin):
    # Only this newly generated database is ever migrated or dropped.
    name = f"sciscope_test_{uuid4().hex}"
    with postgres_admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}" TEMPLATE template0'))
    url = postgres_admin.url.set(database=name).update_query_dict({
        "options": "-c statement_timeout=15000 -c lock_timeout=10000",
    }).render_as_string(hide_password=False)
    try:
        yield url
    finally:
        get_engine(url).dispose()
        with postgres_admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))


@pytest.fixture
def postgres_url(postgres_database_url):
    migrate_test_database(postgres_database_url)
    get_engine(postgres_database_url)
    return postgres_database_url
