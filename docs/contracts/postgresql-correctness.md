# PostgreSQL correctness

Application engines explicitly use READ COMMITTED. Admission serializes quota
decisions through the durable admission-lock row; subsequent statements see the
previous owner's committed usage. Subscription insertion targets the watch's
unique key and reads the winning watch in a later statement.

Explore workers select claimable operations with `FOR UPDATE SKIP LOCKED`, ordered
by enqueue time and operation ID. A locked operation does not block unrelated ready
work. This allows ordering to relax under contention; it is not strict FIFO.
Claims retain conditional writes and fresh fencing tokens. Lease checks use the
database's wall clock, including after lock waits and result flushes. These are
durable ownership guarantees, not exactly-once guarantees for external IO.

## Verification

The independent PostgreSQL CI job uses PostgreSQL 18 and pgvector 0.8.7. SQLite
tests remain the fast default; they do not establish PostgreSQL concurrency or
vector guarantees. The PostgreSQL suite checks:

- concurrent admission, cooldown, quota bypass, and atomic scheduling rollback;
- duplicate expansion and watch creation, including unrelated constraint errors;
- parallel worker claims, locked queue heads, stale-owner fencing, and atomic
  results/report publication;
- actual deadlock, lock timeout, serialization failure and SQL/schema error paths;
- clean migrations, batched `0015 → 0016` conversion and downgrade/re-upgrade;
- vector schema/index creation, cosine retrieval, cache invalidation and rollback.

Concurrent tests use independent connections and barriers/events. Tests requiring
a lock wait observe it in `pg_stat_activity`; arbitrary sleeps do not establish
that contention occurred. Database statement and lock timeouts bound failed work.

## Local execution

Use a dedicated disposable test server with pgvector installed. Never supply
production credentials. The role needs permission to create/drop databases and
install the vector extension. Each test migrates a newly generated database and
drops only that database on teardown; the connection URL's database is used only
for administrative connections.

From the repository root:

```sh
docker run --rm --name sciscope-test-postgres \
  -e POSTGRES_USER=sciscope_test -e POSTGRES_PASSWORD=sciscope_test \
  -e POSTGRES_DB=postgres -p 127.0.0.1:55432:5432 \
  pgvector/pgvector:0.8.7-pg18-trixie
```

After the server reports readiness, in another terminal:

```sh
SCISCOPE_TEST_POSTGRES_URL='postgresql+psycopg://sciscope_test:sciscope_test@127.0.0.1:55432/postgres' \
  python -m pytest backend/tests/postgres --postgres -q
docker stop sciscope-test-postgres
```

`--postgres` without the explicit URL fails configuration. Without that flag,
PostgreSQL tests are skipped. The CI job always supplies both, so unavailable
PostgreSQL or a missing extension fails the job rather than silently skipping it.
