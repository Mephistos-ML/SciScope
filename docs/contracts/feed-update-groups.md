# Feed update publications

Feed events remain the canonical per-subscription facts. Their IDs, provider
payloads, timestamps, and read state are independent of how Feed cards group them.
A publication identifies an immutable, nonempty group of events for one user,
subscription, and repository. It stores no generated title, colour, summary,
version number, or duplicate read state.

## Identity and membership

`FeedUpdateGroup` is owned by `app.models.feed`. The persistence contract lives
in `app.storage.feed.groups`. `user_feed_update_groups` stores publication
identity, scope, kind, and first-publication time;
`user_feed_update_group_members` stores its explicit event membership.

- A `release` publication contains exactly one release event and may include
  confirmed commit events. A `commits` publication contains only commit events.
- One event belongs to at most one publication. Published membership cannot be
  extended, reassigned, or replaced by retrying publication.
- Group IDs are deterministic UUIDs scoped to subscription, kind, and publication
  key. Release publishers use the release event ID as the key; commit publishers
  use the scan publication identity. Display text and scan frequency are not IDs.
- Retrying an identical group preserves its original creation time and event read
  state. Reusing its ID for different scope, kind, or membership is a conflict.
- Monitoring commits events, groups, profile refreshes, and completed-stream
  checkpoints in one fenced transaction. Fresh event IDs are determined after
  locking the monitoring lease; the application grouping callback is pure and
  performs no external IO while the lock is held.
- Each fresh release gets its own publication. Fresh commits form one publication
  per subscription and scan, identified by the monitoring run ID. Release and
  commit events remain separate until their relationship is confirmed.
- Incomplete scans publish discovered events immediately and retain unfinished
  stream checkpoints. Recovery publishes only newly discovered IDs. Repeated
  facts can refresh event content without regrouping them or resetting read state.
  A scan with no fresh events creates no publication. Losing the lease or failing
  any publication write rolls back events, groups, and checkpoint advancement.
- Composite foreign keys enforce matching user, subscription, and repository
  scopes. Event membership uniqueness prevents two publications claiming the same
  event; a rejected write rolls back its group and any associated event writes.

Card read state is derived from member events. Publication does not reset a
previously read event. Removing a subscription preserves its historical events
and groups. Account deletion removes the owner's groups and events. Event
retention removes memberships and deletes groups left with no members.

## Migration and deployment

Migration `0017_feed_update_groups` creates the publication tables and backfills
existing events in ID-ordered batches of 500. Historical scan boundaries are not
recoverable: each event receives a deterministic singleton publication. No
historical release-to-commit relationship is inferred. Existing event IDs,
content, timestamps, and read state are untouched.

Stop monitoring during the schema migration and start the group-publishing worker
with the new schema. Downgrade removes grouping metadata but preserves all source
events and their read state. Re-upgrade reconstructs singleton groups; it cannot
recover the original multi-event publication boundaries after downgrade.

Group storage does not change the existing event-based HTTP Feed contract.
