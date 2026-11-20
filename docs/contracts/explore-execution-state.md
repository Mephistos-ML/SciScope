# Explore Execution State

`search_runs.execution_state_json` is the replay baseline for an asynchronous
Explore run. Its contract is owned by `app/services/search/explore/execution.py`.
It describes committed search progress, independently of the HTTP response and
provider payload formats. `serialize_execution` and `deserialize_execution` use
one validator. Writers emit schema 2; readers accept schema 2 and explicitly
upgrade the historical schema-1 vocabulary in memory.

## Versions 1 and 2

The root contains exactly these fields:

| Field | Meaning |
| --- | --- |
| `schemaVersion` | Integer `1` (historical) or `2` (current); other versions, booleans, strings, or missing values are rejected |
| `plan` | Plan status and ordered queries |
| `executedQueries` | The executed prefix of that ordered plan |
| `retrieved` | Candidates, source statuses, successful-source count, partial coverage, warnings, and lane outcomes |
| `attempts` | Query attempts, outcomes, durations, and candidate counts |

Candidate snapshots retain repository identity, signal facts, and retrieval
provenance, including individual match evidence. Repository IDs must agree with
signal item IDs, and the candidate collection must contain no duplicate IDs.
Counters are integers with appropriate nonnegative or positive bounds; booleans
are not counters. Match alignment is finite and between zero and one. Published
timestamps are ISO 8601 strings with an offset, or null. Enum values, required
fields, and list/object types are checked without coercion. Unknown structural
fields are rejected. Signal payloads and source-status objects are explicit JSON
extension fields; their contents must remain JSON-compatible and finite.

The [version 1 fixture](../../backend/tests/fixtures/explore_execution_v1.json)
records the exact persisted shape and verifies full round trips, including lane
outcomes. Version 1 permits the original eight match locations. Version 2 adds
`notebook`, `data`, `configuration`, `project_metadata`, and `legal`; its object
shape is unchanged. The reader rejects those additional locations in a v1
payload. A v1 read preserves every fact; the next write emits version 2.

This explicit compatibility transition keeps existing resumable work readable.
Remove the v1 reader only after all still-expandable/replayable states have been
converted or retired under the product's retention policy and that condition has
been verified. Unknown versions remain unsupported. No historical migration is
rewritten, and there is no automatic bulk backfill in this change.

## Retry and partial-result policy

New executions run each planned query once. Safe HTTP GET retries belong to the
provider clients; the application does not repeat an entire query or its already
successful lanes after the transport budget is exhausted. A timeout can advance
to a different saved query, merging earlier observations. Each distinct query
retains the existing bounded soft/hard and lane deadlines. A new query is a
separate search expression, not a retry of the preceding request.

GitHub allows at most three transport attempts, with exponential backoff and
jitter for transient transport, malformed-JSON, HTTP 408 and 5xx failures. Retry
windows must fit the remaining deadline; an HTTP-request backoff over 30 seconds
is surfaced rather than slept through. Valid `Retry-After`/reset hints are not
shortened. Access denial and rate limits are returned without automatic HTTP
retries. Unexpected errors are recorded at the lane isolation boundary.

Validated code-search page prefixes survive later classified IO failures and
enter the normal merge/ranking path. Coverage truncation produces `partial` even
when every HTTP request succeeded. Failure before any usable observation remains
unavailable, and a validated empty result remains successful. Work not delivered
by a lane before the coordinator's deadline is not part of the published result;
remaining socket work stays bounded by the propagated deadline.

The persisted schema stays at version 2: lane status/error strings were already
open fields, and no serialized fields were added. Readers continue accepting
historical attempts numbered above one; old runs are not rewritten or replayed
merely because the automatic retry policy changed.

## Recovery Behavior

Expansion validates the replay baseline before external verification or admission,
and again within admission's locked transaction. Invalid state returns a lifecycle
conflict without consuming an attempt or scheduling work.

A worker validates the baseline before invoking expansion. Missing, invalid, and
unsupported state produce distinct durable codes: `execution_state_missing`,
`execution_state_invalid`, and `execution_state_unsupported`. The run and operation
fail together while the previous response, stored state, and reports remain
available for diagnosis. Error messages identify a contract field without echoing
its contents. An unknown version is never guessed, reset, or interpreted as an
empty result.

Attempt callbacks validate new state before collecting it. Publication remains
fenced and atomic with the result and report; crashes before publication replay
from the preceding committed baseline.

## Data Migration

Migration `0016_guest_run_access` converts unversioned records to version 1 in
batches of 500. It preserves stored facts and marks previously omitted lane
outcomes as empty. Already versioned records and malformed non-object values are
preserved; malformed records remain subject to runtime rejection. Downgrade does
not erase execution JSON or its version information.

Apply this data conversion before running the current reader. An already-applied
private copy of `0016` does not rerun when its file is amended; such a development
database needs the data conversion separately or a fresh migration path. A schema
downgrade alone does not restore an earlier application contract.
