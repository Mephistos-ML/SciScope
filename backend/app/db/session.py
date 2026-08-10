"""SQLAlchemy engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import DATABASE_URL
from app.db.base import Base
from app.db import models as _models

_ENGINE_CACHE: dict[str, Engine] = {}
_SESSION_FACTORY_CACHE: dict[str, sessionmaker[Session]] = {}
_INITIALIZED_URLS: set[str] = set()


def resolve_database_url(database_url: str | None = None) -> str:
    """Resolve an explicit database URL or fall back to the configured default."""

    return database_url or DATABASE_URL


def get_engine(database_url: str | None = None) -> Engine:
    """Return a cached SQLAlchemy engine for the given database URL."""

    resolved_url = resolve_database_url(database_url)
    engine = _ENGINE_CACHE.get(resolved_url)
    if engine is not None:
        return engine

    _prepare_sqlite_directory(resolved_url)
    engine_kwargs: dict[str, object] = {"future": True}
    if resolved_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(resolved_url, **engine_kwargs)
    _ENGINE_CACHE[resolved_url] = engine
    return engine


def init_database(database_url: str | None = None) -> None:
    """Create the configured schema when it does not exist yet."""

    resolved_url = resolve_database_url(database_url)
    if resolved_url in _INITIALIZED_URLS:
        return

    Base.metadata.create_all(get_engine(resolved_url))
    _INITIALIZED_URLS.add(resolved_url)


def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    """Return a cached session factory for one database URL."""

    resolved_url = resolve_database_url(database_url)
    session_factory = _SESSION_FACTORY_CACHE.get(resolved_url)
    if session_factory is not None:
        return session_factory

    session_factory = sessionmaker(
        bind=get_engine(resolved_url),
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )
    _SESSION_FACTORY_CACHE[resolved_url] = session_factory
    return session_factory


def _prepare_sqlite_directory(database_url: str) -> None:
    if not database_url.startswith("sqlite"):
        return

    url = make_url(database_url)
    if url.database in (None, "", ":memory:"):
        return

    db_path = Path(url.database)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)


def check_database_connection(database_url: str | None = None) -> None:
    """Verify that the configured database accepts a simple query."""

    resolved_url = resolve_database_url(database_url)
    with get_engine(resolved_url).connect() as connection:
        connection.execute(text("SELECT 1"))


@contextmanager
def session_scope(database_url: str | None = None) -> Iterator[Session]:
    """Open one SQLAlchemy session with commit/rollback handling."""

    resolved_url = resolve_database_url(database_url)
    init_database(resolved_url)
    session = get_session_factory(resolved_url)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
