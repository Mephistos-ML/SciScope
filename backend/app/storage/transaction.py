"""Persistence transaction boundary and infrastructure error translation."""

from collections.abc import Iterator
from contextlib import contextmanager
import sqlite3

from sqlalchemy.exc import (
    DBAPIError,
    DisconnectionError,
    IntegrityError,
    InterfaceError,
    OperationalError,
    SQLAlchemyError,
    TimeoutError,
)
from sqlalchemy.orm import Session

from app.database.session import session_scope
from app.models.persistence import (
    PersistenceConflictError,
    PersistenceError,
    PersistenceUnavailableError,
)


@contextmanager
def persistence_session(database_url: str) -> Iterator[Session]:
    """Translate failures only after the underlying transaction rolls back/closes."""
    try:
        with session_scope(database_url) as session:
            yield session
    except SQLAlchemyError as exc:
        raise _application_failure(exc) from exc


def _application_failure(error: SQLAlchemyError) -> PersistenceError:
    if isinstance(error, IntegrityError):
        return PersistenceConflictError("The operation conflicts with current data.")
    if isinstance(error, (TimeoutError, DisconnectionError)):
        return PersistenceUnavailableError("Persistence is temporarily unavailable.")
    if isinstance(error, DBAPIError):
        # Driver codes, rather than driver text, distinguish contention, outages,
        # and SQL/schema defects. Extended SQLite codes share the low-byte class.
        sqlstate = getattr(error.orig, "sqlstate", None)
        sqlite_code = getattr(error.orig, "sqlite_errorcode", None)
        sqlite_class = sqlite_code & 0xff if isinstance(sqlite_code, int) else None
        if sqlstate in {"40001", "40P01", "55P03"} or sqlite_class in {
            sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED,
        }:
            return PersistenceConflictError("A concurrent operation prevented this update.")
        if (
            error.connection_invalidated
            or isinstance(sqlstate, str) and (
                sqlstate.startswith(("08", "53")) or sqlstate in {"57P01", "57P02", "57P03"}
            )
            or sqlite_class in {sqlite3.SQLITE_CANTOPEN, sqlite3.SQLITE_IOERR, sqlite3.SQLITE_FULL}
        ):
            return PersistenceUnavailableError("Persistence is temporarily unavailable.")
        if sqlstate is None and sqlite_class is None and isinstance(error, (OperationalError, InterfaceError)):
            return PersistenceUnavailableError("Persistence is temporarily unavailable.")
    return PersistenceError("The persistence operation failed unexpectedly.")
