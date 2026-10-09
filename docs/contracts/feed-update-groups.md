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
- Each fresh release gets its own publication. Fresh commits uniquely confirmed for a fresh release become its members.
  Remaining fresh commits form one publication per subscription and scan,
  identified by the monitoring run ID. Overlapping release comparisons leave
  ambiguous fresh commits in the scan batch; no release is chosen arbitrarily.
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

## Grouped HTTP Feed

The authenticated grouped contract is exposed alongside the event contract:

| Operation | Endpoint | Result |
| --- | --- | --- |
| List cards | `GET /api/feed/groups` | `items`, `nextCursor`, `hasMore`, `unreadCount` |
| Open a card or load more commits | `GET /api/feed/groups/{group_id}` | Card fields, `release`, `commits`, `nextCursor`, `hasMore` |
| Mark a card read | `PATCH /api/feed/groups/{group_id}` | Updated card fields |

Lists default to 20 cards; details default to 10 commits. Both accept `limit`
from 1 to 50 and an opaque `cursor`. Lists also accept `state=all|unread` and
`subscription_id`. Invalid limits, states, cursor versions, or cursor shapes
return 422. A commit cursor is bound to its group and cannot be used for another
card or for list pagination. Unauthenticated requests return 401; absent and
foreign-owned cards both return 404.

Cards are grouped in SQL before applying the page limit. A release is ordered
by its release timestamp; a commit batch by its latest member commit timestamp.
Undated cards follow dated cards. Publication time and group ID break ties;
the cursor preserves full timestamp precision. Newer publications arriving while
loading older pages do not shift the cursor position. Like event-based pagination,
this is a live feed, not a snapshot across edits, retention, or read-state changes.

Each card exposes `groupId`, subscription and repository identity/profile,
`kind=release|commits`, derived title, summary and URL, `publishedAt`, `createdAt`,
`eventCount`, `commitCount`, `unreadEventCount`, and `isRead`. `publishedAt` is
provider activity time; `createdAt` is publication time, not a substitute activity
date. Commit-batch display text and repository URL are derived, never stored as
synthetic release facts.

`unreadCount` counts cards with at least one unread member across the user's
whole Feed, independent of list filters. `unreadEventCount` is the count within
one card, counting publication members. Read state remains authoritative in events: reading an individual
event affects its card; marking a card read updates every unread member in one
transaction. Already-read timestamps are preserved. Opening details is read-only.
The existing `POST /api/feed/read-all` updates all user events and therefore all
cards; its `updatedCount` continues to count events.

Details return the canonical release description and metadata, if this is a
release card, plus a bounded page of commit previews. `commitCount` counts currently retained commits available for the card, including
confirmed references to earlier publications. `totalCommitCount` is the known
provider range count, or null when unknown. `commitDetailsStatus` is `complete`,
`partial`, or `unavailable`; unavailable counts are null, not a fabricated zero.
`hasMore` describes pagination of retained facts and is independent of coverage. No provider IO occurs
when listing cards or opening stored details.

The event-based endpoints remain compatible for independently deployed clients.
The frontend transition to grouped cards uses the grouped endpoints; individual
events remain the authoritative facts for reading and detail access.


## Confirmed release comparisons

`RepositoryMonitor.load_release_commit_details` compares a release tag with the
unambiguous release published immediately before it. Adapters require a complete
catalogue within three pages of 100 releases, ignore drafts, and decline ambiguous
predecessors. Both tags are resolved to immutable commit SHAs before comparing.
GitHub requires an ancestral merge base and pages the pinned comparison; GitLab
verifies ancestry with a reverse comparison before reading the direct range.
A first release, missing tag, divergent history, ambiguous or oversized catalogue,
provider failure, or exhausted budget leaves useful release content and its link
available with `unavailable` comparison coverage.

Monitoring attempts comparisons for up to five fresh releases per repository,
prioritizing the newest, under one shared 15-second request budget. Each comparison
retains at most 500 mapped commits; confirmed partial results remain usable.
Comparison responses are capped at 8 MiB each before JSON parsing. Client
request timeouts and retry backoff respect the remaining budget. Optional
comparison coverage does not control the release or main-commit stream checkpoints.
HTTP Feed reads perform no comparison IO. Aggregate enrichment logs record attempts,
coverage counts, and duration per repository.

Release events store `release_commit_details` in their existing canonical metadata.
Its version-1 schema contains `status`, pinned `baseSha` and `headSha`, `eventIds`,
and optional `totalCount`. It contains no copied commit bodies or read state.
All referenced facts are written or verified in the same publication transaction
and must be commits in the same user, subscription, and repository scope.
Supplemental comparison facts are inserted only if unseen; they do not overwrite
previously published commit content. The first successful publication freezes the
comparison snapshot. Later provider refreshes can update release text without
replacing the snapshot or extending published groups. Historical events without
comparison metadata are explicitly unavailable and are not reconstructed.

A reference can identify a commit in an earlier publication. That earlier group
keeps its membership and read state. Reading a release card marks its own members;
earlier referenced events keep their original publication's read state. The
account-wide read action still operates on all canonical events.

Retention may remove referenced facts. Both card summaries and details count only
retained, scope-matching commits; missing references make coverage partial while
preserving the original provider count. Detail pagination can end while coverage
is still partial. Unknown metadata versions or invalid snapshot shapes are data
contract failures, not empty complete results. Version-1 readers must remain in
place while these snapshots are retained.

This contract uses the existing JSON metadata column; no schema revision is needed.
A coordinated rollback must keep a reader for retained version-1 snapshots. A
pre-feature worker can overwrite these metadata values during release refreshes,
so stop monitoring when rolling back and preserve snapshots before restarting it.

Provider protocol references:
[GitHub compare commits](https://docs.github.com/en/rest/commits/commits#compare-two-commits)
and [GitLab repository comparisons](https://docs.gitlab.com/api/repositories/#compare-branches-tags-or-commits).

## Browser behavior and rollout

Feed and subscription previews use the grouped endpoints. Cards disclose stored
commit previews on request, initially ten at a time. Loading more commits retains
the current page; collapsing preserves loaded details. Closing or leaving a card
cancels its pending detail request and ignores late responses. Failed pages offer
retry without discarding confirmed commits. Missing provider dates remain unknown;
publication time is not displayed as activity time.

Opening details and following provider links leave read state untouched. Explicit
Mark read updates that card's members. Mark all read applies across the account,
including cards outside the current filter. Global and subscription unread badges
count publications with unread members. `GET /api/subscriptions` exposes
`unreadGroupCount`; its existing `unreadEventCount` remains event-based for released
clients. Read actions refresh counts from the server while preserving loaded cards.

All/Unread keeps the selected repository scope. Leaving a repository-filtered
Feed restores the global list; obsolete list responses cannot replace a newer
scope or restore a pre-read snapshot. Coverage is visible independently of local
pagination: unavailable details have no numeric zero, while partial details explain
that retained commits are only part of the range.

Deploy the schema and group-publishing backend before the grouped client. A client
rollback can use the preserved event endpoints with the same canonical read state;
it does not require a database downgrade. Worker rollback has the snapshot
constraints described above. Browser journeys use real API responses and a
migrated disposable PostgreSQL database to verify this behavior.
