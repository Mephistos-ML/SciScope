# Backend Recovery

Run backend commands from `/app` inside the configured container, or from the
repository root in an installed local environment. Configuration comes from the
environment; application imports do not load `.env` files. Do not print connection
credentials, guest/session tokens or lease tokens during diagnosis.

## Diagnose

Production images now require a source SHA build argument. Use
`python scripts/deploy_backend.py --dry-run` to inspect the command from a clean
checkout, then `python scripts/deploy_backend.py` to deploy when authorized.
Direct builds need `--build-arg APP_REVISION=<full-source-sha>`. Missing or invalid
identity fails early; do not label an image with an unrelated SHA. See
[versioning and provenance](../contracts/versioning-and-provenance.md).

| Symptom | Check |
| --- | --- |
| API unavailable | `/health`, Machine/process state and logs |
| API live, `/ready` failing | Database/network/configuration |
| Queued runs do not advance | Worker logs and queued operations |
| Run remains running | Operation lease against DB time; worker heartbeat logs |
| Stale Feed | Scheduler, monitoring lease, scan summaries and repository checks |
| Terminal failed run | Error code; restart does not requeue terminal work |

## Scientific domain schema rollout

Apply revision `0019_search_scientific_domain` before deploying backend code that
reads the optional run context. See the [domain contract](../contracts/scientific-domain.md)
for overlap, worker compatibility and rollback limits. The existing coordinated
`0018` cutover below still applies when upgrading from an earlier schema.

## Log-match ranking rollout and recovery

The current ranking policy is `location_weighted_log_matches_v4`. Deploy the diagnostic
frontend first: it understands historical unversioned 0--100 snapshots, version-2
per-location breakdowns using `points`, and version-3 breakdowns using
`contribution`, plus the current version-5 breakdowns.
The earlier UI would mislabel an unsupported format as a score
out of 100. Version 3 renames diagnostic fields without changing numeric scores.

Remove `EXPLORE_SEARCH_RELEVANCE_CUTOFF` from API and worker configuration when
deploying the new backend; a nonempty retired setting prevents startup. Use
`EXPLORE_SEARCH_LOG_MATCH_CUTOFF=0` initially to disable the additional score
filter while retaining admission. A nonzero threshold requires evaluation on the
new scale. Reconstruct dependencies/restart processes after changing the setting.

Coordinate the API and worker upgrade to avoid different ranking policies being
selected by workers in the same deployment. Previously completed responses and
reports stay unchanged. Existing queued work and resumed/expanded runs use their
stored retrieval evidence with the new formula when evaluated; new per-stage
breakdowns identify that policy even when a run's creation metadata is older.

No database migration or backfill is required. If rolling back backend code,
restore the former deployment's cutoff configuration and restart API/workers
together. The new UI can remain deployed because it reads both score formats.
Rollback does not revert results or snapshots already delivered by the new
formula; preserve them for audit rather than rewriting scores.

### Taxonomy v2 cutover

The expanded file taxonomy writes execution schema 2 and accepts historical
schema 1 through an explicit read upgrade. Stop/drain old workers before enabling
the new writer, and upgrade API and workers together. Old code does not understand
schema 2 or the new location vocabulary. New workers can resume v1 states and
publish them as v2 atomically through the existing fenced completion path.

New file categories inherit weight 0.25; separate logarithmic aggregation can
still increase scores. Root-level documents newly recognized as documentation
use the existing documentation weight 0.55. Re-evaluate any nonzero cutoff.
Completed scores and reports are not recomputed; cached path evidence is
classified under the active policy when a new evaluation runs.

After schema-2 states or new catalog locations exist, backend rollback requires
code that understands that vocabulary and schema; a rollback to the old reader
alone is unsafe. Prefer a forward fix. Do not discard or relabel durable user
state to force an old reader to accept it. No table migration/backfill is needed.

### Ranking/profile cutover

The current backend writes ranking breakdown schema 5, policy v4 and configuration
schema 2. Deploy the frontend reader first; unsupported historical schema 4 remains
explicitly unsupported rather than being reinterpreted. Stored reports are not rewritten.

Revision `0018_repository_profile_fields` removes a retired repository column and
its redundant keys from current profile JSON, preserving unrelated metadata. JSON
cleanup uses keyset batches of 500 within the migration transaction; duration and
row locking scale with the catalog size. Historical run reports are not rewritten.
Quiesce the API and workers before applying it: previous binaries select that
column, and the new binaries cannot insert into the prior NOT NULL schema. Take
a recoverable backup, migrate, then start the new binaries together. Fly's default
release-command overlap alone is not a safe coordinated cutover for this revision.
No production migration was executed as part of this patch. Downgrade restores the
column shape with zero defaults, not the former values; restore from backup to
recover those facts. Prefer a tested forward fix.

Inside the API container:

```sh
curl --fail --show-error http://127.0.0.1:8000/health
curl --fail --show-error http://127.0.0.1:8000/ready
```

Expected: `ok`, then `{"status":"ok"}`. Readiness proves DB connectivity only.
From the operator workstation:

```sh
fly machine list --app sciscope-api
fly logs --app sciscope-api --no-tail
fly ssh console --app sciscope-api --select
```

Record the affected Machine/image and run/operation IDs. Worker error logs use
operation IDs; structured search events use run IDs. Monitoring checks are in DB.

### PostgreSQL state

This read-only, bounded diagnostic prints operational facts without payloads or
tokens. Missing tables indicate a schema problem; empty lists are valid on an unused DB.

```sh
python - <<'PY'
from sqlalchemy import text
from app.config import DATABASE_URL
from app.database.session import get_engine

queries = {
    "schema": "SELECT version_num FROM alembic_version",
    "operation_counts": "SELECT status, count(*) AS count FROM search_run_operations GROUP BY status ORDER BY status",
    "active_operations": """
        SELECT o.operation_id, o.run_id, o.kind, o.status, r.status AS run_status,
               o.queued_at, o.lease_expires_at, r.error_code,
               CASE WHEN o.status = 'running' THEN
                   o.lease_expires_at IS NULL OR o.lease_expires_at <= clock_timestamp()
               ELSE false END AS reclaimable
        FROM search_run_operations o JOIN search_runs r ON r.run_id = o.run_id
        WHERE o.status IN ('queued', 'running')
        ORDER BY o.queued_at, o.operation_id LIMIT 20
    """,
    "monitoring_lease": "SELECT job_name, lease_expires_at, lease_expires_at <= clock_timestamp() AS expired FROM monitoring_job_leases",
    "recent_scans": """
        SELECT run_id, started_at, finished_at, status,
               scanned_repository_count, failed_repository_count
        FROM monitoring_runs ORDER BY started_at DESC LIMIT 10
    """,
    "recent_checks": """
        SELECT repository_id, run_id, checked_at, status, error_code
        FROM repository_monitoring_checks ORDER BY checked_at DESC LIMIT 20
    """,
}
engine = get_engine(DATABASE_URL)
try:
    with engine.begin() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        connection.execute(text("SET LOCAL statement_timeout = '5s'"))
        for name, statement in queries.items():
            print(name, [dict(row) for row in connection.execute(text(statement)).mappings()])
finally:
    engine.dispose()
PY
```

## Recover Explore Work

Restore DB/configuration and confirm schema compatibility before restarting a
worker. A running operation with an expired/null lease is claimable; a future
expiry alone does not prove a healthy worker. Counts can change between statements.

For a stuck supervised worker, restart the affected Machine after resolving its
fault; replace `MACHINE_ID` with the ID observed above:

```sh
fly machine restart MACHINE_ID --app sciscope-api
```

This interrupts API traffic and monitoring too. Supervisor has no configured
control socket. Locally, start the worker in its own terminal:

```sh
python -m app.jobs.process_search_runs
```

It processes all claimable work. A killed attempt becomes eligible after its last
lease expires (default 300 seconds); normal release may permit an earlier retry.
Idle polling defaults to 1 second. Replay starts from committed execution state
and can repeat external calls. Direct searches are not resumed after API restart.
Verify advancing operation states and an owner-authorized run poll. A lost guest
token cannot be reconstructed from its stored hash.

Terminal failures are not automatically retried. For `execution_state_missing`,
`execution_state_invalid` or `execution_state_unsupported`, preserve the baseline
and resolve reader/migration compatibility. Do not reset JSON or manually mark
success. Unrecoverable state requires a new search under normal admission.

## Recover Monitoring

When deploying migration 0016, stop monitoring invocations before migration and
restart them with the new application code. Existing lease rows without tokens
are claimable by the new worker. Older binaries do not enforce fencing, so do not
run them alongside the new monitoring implementation.

Check the latest scan **and** per-repository checks. No new events can be a valid
complete scan. Repository failures can produce `partial` and a normal CLI exit.
Crashes leave committed repository results intact but can leave their scan summary
`running`; later scans do not finalize that abandoned summary.

Before a manual retry, establish that the previous scan has stopped on every
replica, then wait for lease expiry or normal release. The 1,800-second monitoring
lease renews every 600 seconds. Expired or superseded tokens cannot publish results;
a stale `running` summary does not prove that a scan still owns its lease. If
necessary, restart the affected runtime and account for its other processes being
interrupted.

Allow the next two-hour UTC schedule, or run once in the configured backend:

```sh
python -m app.jobs.scan_subscriptions
```

Verify a **new** scan row, its final status and repository checks. An occupied
lease returns without scanning and can exit successfully. Retries preserve Feed
identity/read state and resume completed-stream cursors.

For persistent `incomplete_interval`, inspect provider access, read budgets and
commit ancestry. Do not move cursors to current time/HEAD to hide missing activity.
There is no supported automatic cursor reset/reconciliation command; unresolved
history needs a reviewed repair with explicit backfill/data-loss decisions.
See [Repository Monitoring](repository-monitoring.md) for stream limits.

## Restore Database / Apply Migrations

Restore connectivity/capacity first, then check `/ready` and background progress
separately. Required Explore persistence failures leave unpublished work retryable;
optional catalog failures can fall back. A persistence conflict is not permission
to retry arbitrary effects. Missing schema requires repair, not restart loops.

Use the deployed/new artifact and its configured DB:

```sh
alembic -c backend/alembic.ini heads
alembic -c backend/alembic.ini current
```

Expected: one code head and DB at that head. An unversioned existing schema needs
inspection, not automatic treatment as a fresh DB.

For an approved deployment/repair, establish a recoverable backup and quiesce
incompatible writers. Apply schema/data conversion before starting new readers:

```sh
alembic -c backend/alembic.ini upgrade head
alembic -c backend/alembic.ini current
```

Fly uses this upgrade as its release command, while old Machines may still be
alive. Incompatible readers/writers require coordinated cutover. On failure,
inspect revision/schema/data and fix the cause; do not bypass it with `stamp head`.

Amending an applied private migration does not rerun it. Use a fresh disposable
development DB or an explicit reviewed conversion. Do not force replay by
downgrading shared state. Published/shared migration history stays immutable.

Rollback code only if it can read the remaining schema and persisted JSON.
Downgrade does not undo external effects or guarantee data restoration. Prefer a
compatible forward fix; rehearse any backup restoration on a copy with a defined
acceptable data-loss window. See [execution-state migration](../contracts/explore-execution-state.md).

## Catalog Maintenance

[Catalog repair](catalog-repair.md) previews bounded provider-backed refreshes
before apply. Preview does not write profiles, but still makes provider requests.

`python -m scripts.backfill_semantic_catalog` embeds missing or changed catalog documents,
makes paid embedding calls and writes vector batches. There is no dry-run/per-ID
CLI option; a later failure can leave earlier batches committed. Run deliberately
when semantic retrieval is enabled, verify completion and semantic search, and
account for repeat provider work on retry.

## Command References

- [Fly Machine restart](https://docs.fly.io/flyctl/cmd/fly_machine_restart)
- [Fly SSH console](https://docs.fly.io/flyctl/cmd/fly_ssh_console)
- [Alembic commands](https://alembic.sqlalchemy.org/en/latest/api/commands.html)
