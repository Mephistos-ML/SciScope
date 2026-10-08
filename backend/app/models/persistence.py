"""Stable persistence failure categories exposed to application callers."""


class PersistenceError(RuntimeError):
    """An unexpected persistence failure; preserve diagnostics in the exception cause."""


class PersistenceUnavailableError(PersistenceError):
    """Persistence cannot currently accept or complete the operation."""


class PersistenceConflictError(PersistenceError):
    """A constraint or concurrent transaction prevented the operation."""
