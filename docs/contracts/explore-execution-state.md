# Explore Execution State

`search_runs.execution_state_json` is the replay baseline for an asynchronous
Explore run. Its contract is owned by `app/services/search/explore/execution.py`.
It describes committed search progress, independently of the HTTP response and
provider payload formats. `serialize_execution` and `deserialize_execution` use
one validator and accept only the current schema.

## Version 1

The root contains exactly these fields:

| Field | Meaning |
| --- | --- |
| `schemaVersion` | Integer `1`; a boolean, string, or missing value is invalid |
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
outcomes. Structural changes require a schema-version change and an explicit data
migration, rather than permissive field defaults or a permanent legacy reader.

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
