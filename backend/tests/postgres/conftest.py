"""Dedicated databases, real migrations and bounded concurrent database work."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from app.database.session import get_engine
from tests.conftest import migrate_test_database


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
