# Repository retrieval

Explore plans queries from the question and optional scientific context; see the
[domain contract](scientific-domain.md). Catalog retrieval and external discovery
consume those queries. Composition binds GitHub repository search, GitHub code
search and GitLab repository search as parallel lanes. Self-hosted GitLab also
retains its existing code-search lane when supported.

Product GitHub code search requests at most three pages of 100 files for each
executed query, stopping at empty/short pages, a known exhausted total or the
remaining deadline. The adapter permits an explicit budget of 1–10 pages for
other callers. GitHub repository search retains 50 items/query, and GitLab
repository search retains 30 items/query. These bounds describe observed
candidates, not exhaustive repository coverage. HTTP retries add attempts beyond
logical page counts.

## Query expressions and file scope

Provider search adapters send each complete query as a quoted phrase. Raw query
text remains the canonical evidence identity; protocol quoting is owned by
`integrations/repositories/common/search_query.py`. Both GitHub channels and both
GitLab channels use this formatter without a broad-query fallback. These
qualifiers govern external retrieval. They do not establish that every
returned fragment contains an exact phrase; provider engine behavior requires
separate evaluation.

GitHub code search alone appends the fixed file-extension suffix owned by
`integrations/repositories/github/search/file_policy.py`. Its public
`build_code_search_query` contract quotes the phrase, appends 59 allowed extensions
and rejects a decoded expression longer than 1000 characters before URL encoding.
The suffix occupies 812 ASCII characters. New AI queries have a 185-character
bound; escaping can still make a complete expression too long, so the adapter's
final validation is required. Overflow raises `ValueError` without truncation,
request splitting or a broad-search fallback. GitHub repository search and GitLab
do not receive this file restriction.

This file scope controls external retrieval eligibility, independently of the
path classifier's location taxonomy. It excludes extensionless README files but
retains README files with allowed extensions. Existing catalog evidence is not
retroactively removed or rewritten. The allowed extensions are owned by the
[GitHub file policy](../../backend/app/integrations/repositories/github/search/file_policy.py).

Product discovery consumes the GitHub adapter's `search_code` batch contract:
validated signals, reported counts, incomplete-coverage reasons and an optional
terminal source error. A later page failure retains the validated prefix. An
empty validated result is distinct from first-page unavailability. Page-budget
termination, provider incompleteness/truncation, unmappable items and missing
coverage metadata all set product `partial`, independently of candidate count.
Malformed page envelopes are classified as source errors; malformed individual
items are skipped and mark coverage incomplete. Optional blob SHA is not used by
product discovery and cannot invalidate a usable file match. Page bodies are
bounded to 2 MiB, page size to 100 and page budget to 10 at the adapter boundary;
production composition selects three pages.

The parallel lane merger retains successful repository-search channels. Source
status can remain `ok` when some observations are usable, while run `partial` and
per-lane `partial`/failure status describe missing coverage. Existing lane outcome
fields retain the first coverage reason as `error_code`, or a terminal IO error
and retry hint; structured lane logs include all observed coverage reasons. These
fields are serialized through the current execution-state contract without
persisting exception objects. Historical reports are not rewritten.

The strict `discover_repository_candidates_from_code` collector is
the contract for current offline callers that calculate coverage from saved pages
and need terminal request failures to preserve interrupted checkpoints. It shares
IO and mapping with `search_code`, and raises the returned terminal error rather
than treating a prefix as a completed collection. Product composition directly
binds the batch API; no second mapping or HTTP implementation is maintained.

When GitHub reports a code-search pool above its retrieval cap, Explore returns
one refinement suggestion through its existing message field. The suggestion
asks for a more specific method, tool or scientific task without displaying
provider names, file counts or API limits. Provider counts travel as discovery
diagnostics independently of candidate signals, including empty responses.
The suggestion does not change scores or redefine the `partial` flag; it is
shown for completed searches as well as partial searches and is preserved in
the existing resumable warning contract.

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

