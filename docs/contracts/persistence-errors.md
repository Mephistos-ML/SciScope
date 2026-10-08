# Persistence failure contract

`app/models/persistence.py` owns the application failure categories.
`app/storage/transaction.py` translates SQLAlchemy/driver failures around the
complete transaction, including acquisition, execution, flush, and commit. The
underlying database session performs rollback and cleanup before translation.
The original exception remains the cause for internal diagnostics; public
messages never include SQL, parameters, credentials, or driver text.

| Category | Meaning | HTTP response |
| --- | --- | --- |
| `PersistenceUnavailableError` | Connection loss, resource exhaustion, pool timeout, or unavailable database | 503, `persistence_unavailable` |
| `PersistenceConflictError` | Constraint violation or transaction contention | 409, `persistence_conflict` |
| `PersistenceError` | Unexpected persistence defect, including invalid SQL or missing schema | 500, `persistence_failed` |

HTTP responses retain the existing `error` field and add the stable `code` field.
SQLAlchemy exceptions remain internal to persistence. Domain validation and
lease-ownership exceptions are not reclassified by the transaction boundary.
Startup connection checks are composition operations, outside this request
failure contract.

Classification uses driver codes rather than parsing error messages:
PostgreSQL serialization failure, deadlock, and lock-not-available are contention;
connection/resource failures and server shutdown are unavailable. SQL/schema
errors remain unexpected defects. SQLite extended error codes are reduced to
their primary class; busy/locked are contention and IO/open/full errors are
unavailable. An operational/interface failure without a driver code is treated
as unavailable. Classification does not add retries.

Application use cases choose recovery:

- Catalog and semantic retrieval can fall back after unavailable/conflict errors.
  Catalog ingestion is optional and logs those errors without failing search.
  Unexpected persistence defects and invalid domain inputs propagate rather than
  becoming empty results or successful ingestion.
- Required search-run persistence failures propagate. An attempt cannot publish a
  terminal failure merely because its durable state is unavailable. Its committed
  baseline remains available for replay; worker restart/lease recovery follows the
  existing ownership contract. Unexpected persistence defects require repair before
  successful replay. The adapter does not run a retry loop.
- HTTP maps categories without exposing infrastructure diagnostics. A conflict
  response alone does not prove that repeating an arbitrary operation is safe.

## Idempotent subscription creation

`create_subscription` inserts against the existing unique `(user_id,
repository_id)` key with `ON CONFLICT DO NOTHING`, then reads that watch within
the same transaction. Concurrent/repeated creation returns the committed watch,
including its original ID, creation time, and selected query. A repeat does not
edit the winning watch. Different users have independent watches. Conflicts on
other constraints propagate; they are not mistaken for a duplicate watch.
Application PostgreSQL engines explicitly select READ COMMITTED isolation. Higher isolation can
surface transaction conflicts; this operation does not retry them automatically.

No schema migration is needed: the unique key already exists. SQLite tests cover
parallel creation and rollback; injected psycopg exceptions cover classification.
The [PostgreSQL suite](postgresql-correctness.md) additionally verifies concurrent
watch creation and rollback/classification against actual driver failures.

## References

- [PostgreSQL SQLSTATE codes](https://www.postgresql.org/docs/current/errcodes-appendix.html)
- [SQLAlchemy 2.0 exception contracts](https://docs.sqlalchemy.org/en/20/core/exceptions.html)
