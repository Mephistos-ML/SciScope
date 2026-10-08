# Repository dependencies and runtime ownership

## Composition and entrypoints

`composition/repositories.py` reads deployment configuration and creates one set
of GitHub/GitLab clients. It registers bound profile loaders and monitoring
adapters in read-only mappings. `composition/search.py` receives that set and
binds its clients to the supported retrieval lanes; GitLab lane availability is
resolved from that client's host.

The API builds the set once and injects the resulting capabilities through app
state. The Explore worker builds its own set once when starting its process. A
monitoring invocation and a profile-repair invocation each build their own set.
Search, profile lookup and monitoring within a set use the same provider clients.
Services receive use-case capabilities, not the composition registry.

GitLab credentials and base URL are bound together. Profile validation uses the
explicit base URL, including a self-hosted deployment's path prefix. Changing
configuration does not retarget a client that has already been constructed. A
configuration change takes effect when the entrypoint constructs a new set,
normally after restarting the process.

Repository integrations do not read deployment configuration. Replay fixture
loading also requires an explicit path.

## GitHub installation token cache

A `GitHubAppAuth` instance has immutable credentials for exactly one app and
installation. Its private cache holds a named token/expiration result and its own
lock. A valid token is reused until it enters the 60-second refresh buffer. Cache
reading and exchange are synchronized, so simultaneous requests for that owner
share one successful exchange. Distinct instances never share cached tokens or
refresh coordination.

Only validated, nonempty string tokens with a future, timezone-aware expiration
enter the cache. Token responses are limited to 64 KiB; an invalid response or
failed exchange raises a source error without caching a replacement. A later
caller may attempt the exchange again. This is local cache recovery, not a durable
retry queue or cross-process single-flight guarantee.

The token exchange has a 30-second network timeout and no automatic
retries. The cache lock does not provide an end-to-end search deadline or cancel
an exchange already in progress. Cached credentials disappear on process exit;
the next process obtains its own token. Private keys, bearer tokens and credential
callbacks are excluded from object representations.

## Persistence connections

Application operations that use persistence require `database_url` explicitly.
They do not silently fall back to the deployment database. API and background
entrypoints own connection selection; storage owns transaction behavior. Passing
a connection does not combine otherwise independent operations into a single
transaction.

## Verification

Tests exercise concurrent token exchange, cache isolation, refresh and failed
exchange recovery through the real authentication adapter with HTTP substituted.
JWT signing and signature verification use real RSA keys. Additional checks cover
malformed and oversized token responses, binding different GitLab deployments
within one process, identity rejection before IO, and subscription operations
against two independent databases.

The ordinary suite requires no live GitHub or GitLab access. These tests establish
process-local dependency isolation; they do not establish PostgreSQL lock or
multi-process concurrency guarantees.
