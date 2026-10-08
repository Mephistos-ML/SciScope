# Repository Monitoring

Feed events and completed-stream checkpoints are committed in one database
transaction per repository. A write or commit failure rolls back both, including
updates to existing events. Retried scans remain idempotent and preserve read
status. Partial scans may persist collected events, but only completed streams
advance their checkpoints in that same transaction.

`subscription watch -> source checkpoints -> releases and default-branch commits -> append-only Feed events`

Adapters report completeness separately for releases and commits. Only a fully
read stream may advance its checkpoint; incomplete streams retain their previous
boundary and make the monitoring check `partial`. Already read events are saved
idempotently, so retries preserve event identities and read state.

Release reads use pages of 100 entries, capped at 10 pages per repository per scan.
GitHub reads to the end of the list; GitLab requests descending `released_at`
order and may stop after passing the checkpoint. Entries exactly on the checkpoint
are read again and deduplicated. A page error or exhausted page budget retains
already read releases while leaving the release checkpoint unchanged. Repositories
whose required history exceeds this budget remain partial until the interval can
be fully read.

Commit monitoring stores `latest_main_commit_sha` in the existing cursor table.
A first scan without this SHA backfills by the previous timestamp (or subscription
start), using committer dates and a pinned default-branch HEAD. Only a complete
read establishes the SHA. Later scans compare the stored SHA with a pinned new
HEAD and deliver newly reachable commits even when their dates predate the
subscription. GitHub comparison is paginated; GitLab uses complete direct
comparison commit arrays and a reverse comparison to verify ancestry. Reads are
limited to 1,000 commits; incomplete reads, a missing old SHA, or rewritten history
retain the previous checkpoint and report `partial`. The legacy timestamp never
moves backwards and is only a bootstrap boundary once a SHA exists. Missing or
rewritten history requires investigation; the monitor does not automatically
reset its checkpoint and discard the unread interval. Commit dates remain the
original provider dates in Feed.

The scheduled entrypoint is `app.jobs.scan_subscriptions`; the scan use case lives
in `app/services/monitoring/scan.py`. See the [backend overview](../../backend/README.md)
for the process and module map.
