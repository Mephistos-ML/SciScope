# Backend

SciScope backend is the API, auth, search, persistence, and monitoring layer behind `https://sciscope.uk/`.

## Responsibility

The backend owns:

- public asynchronous Explore search
- AI query planning, local catalog retrieval, external fallback, admission, and heuristic ranking
- Google-authenticated subscriptions
- repository persistence and monitoring checkpoints
- durable, append-only user Feed events
- search access controls, quotas, and observability
- background monitoring control

Core domain objects:

- `Repository`
- `Subscription`
- `Signal`
- `FeedEvent`

## API Areas

### Explore

- `POST /api/explore/search`
- `POST /api/explore/search-runs`
- `GET /api/explore/search-runs/{id}`
- `POST /api/explore/search-runs/{id}/expand`

Signed-in runs can be read or expanded only by their owner. Guest run creation
returns a `guestAccessToken`; clients must retain it and send it in the
`X-Search-Run-Token` header when reading or expanding that run. The token is
returned only on creation; only its SHA-256 hash is stored. An inaccessible run
returns the same 404 as a missing run. Guest runs created before token support
are inaccessible. Internal reports retain their separate owner and feature checks.

Each expansion consumes an attempt under the same cooldown, actor quota, global
capacity, and Turnstile rules as initial search. Send an optional `turnstileToken`
in the expansion JSON body. Admission checks and usage recording share a locked
transaction across processes; the singleton `search_access_lock` row must exist.

### Auth

- `GET /api/me`
- `GET /api/auth/google/start`
- `GET /api/auth/google/callback`
- `POST /api/logout`

### Feed

- `GET /api/feed`
- `GET /api/feed/{id}`

Feed events are created only for activity discovered after subscription time. Removing a subscription does not delete earlier Feed events.

### Subscriptions

- `GET /api/subscriptions`
- `POST /api/subscriptions`
- `DELETE /api/subscriptions/{id}`

### Monitoring

- `POST /api/start`
- `POST /api/stop`
- `GET /api/status`

## Request Flows

### Explore Flow

`topic description -> AI query plan -> local catalog retrieval -> parallel external fallback lanes when coverage is low -> candidate merge -> admission -> heuristic ranking -> result payload`

Main modules:

- `app/services/search/retrieval/`
- `app/services/search/admission/`
- `app/services/search/ranking/`
- `app/services/search/explore/`
- `app/sources/github/search/`
- `app/sources/gitlab/search/`

Explore runs as an asynchronous job. Repository and code-search lanes have separate source and timeout budgets. A source failure or code-query timeout returns completed candidates with partial coverage. GitHub code search stops after a rate-limit response and reports the provider retry time.

Admission removes obvious non-software candidates. Ranking scores the retained pool from query coverage, source-independent match location, and bounded evidence density. The relevance cutoff controls Explore delivery. Search diagnostics can expose the full evaluated pool for configured internal users.

### Subscription Flow

`clicked repository ID -> canonical catalog profile (provider lookup if missing) -> subscription create`

`POST /api/subscriptions` accepts `repository: {"itemId": "github:repo:123"}`
and an optional `selectedQuery`. Existing clients may still send `source`,
`fullName`, and `url`; names and URLs never update the catalog. A supplied
source must agree with the canonical ID. Missing profiles are fetched by the
numeric GitHub repository or GitLab project ID, verified, and inserted only if
another discovery has not already created the profile. Provider failures return
503 without creating a subscription. Existing profiles do not require provider IO.

### Repairing Existing Catalog Profiles

The repair command defaults to a read-only preview, makes provider requests,
and returns JSON with before/after fields. Run it inside the configured backend
environment:

```sh
python -m scripts.repair_repository_profiles --dry-run --limit 100
```

Default selection targets profiles whose metadata contains
`query`, with empty owner, description, language, topics and provider timestamp,
and zero stars. This is a candidate signal, not proof of corruption. Legitimately
sparse profiles without that signature are skipped. To inspect a specific catalog
record regardless of that signature, use `--repository-id` (repeatable).

After reviewing the preview, apply only the selected IDs:

```sh
python -m scripts.repair_repository_profiles --apply --repository-id github:repo:123
```

The default cap is 100 provider lookups. Run reports classify each selected profile
as `would_update`, `updated`, `unchanged`, `skipped_changed`, or `failed`. Apply
uses a conditional update against the revision read before fetching the provider:
a concurrent catalog update is preserved and reported as `skipped_changed`.
Provider errors are isolated per profile. Exit code 1 indicates failed or skipped
profiles; review the report before retrying. Repository IDs, subscriptions,
query evidence, monitoring cursors and historical Feed events are preserved.
If semantic catalog retrieval is enabled, run the semantic backfill after repair
to refresh changed embeddings.

### Monitoring Flow

`subscription watch -> source checkpoints -> releases and default-branch commits -> append-only Feed events`

Main modules:

- `app/services/subscriptions/`
- `app/services/monitoring/`
- `app/services/feed/`
- `app/storage/repositories/`
- `app/storage/subscriptions/`
- `app/storage/feed/`

## Persistence

Primary persistence areas:

- repository catalog profiles and query-specific retrieval evidence
- subscriptions
- repository checkpoints
- feed events
- Explore usage records
- users, OAuth accounts, and sessions

Search execution state is runtime-local. Admitted external candidates are persisted as compact catalog profiles and query-specific retrieval evidence; SciScope does not crawl or mirror whole repository hosts.

Persistence uses SQLAlchemy and Postgres. Alembic migrations live in `alembic/versions/`.

## Operations

Important environment variables:

- `APP_LOG_LEVEL`: structured search-event log level; use `INFO` in deployed environments
- `AI_PLANNER_MODE`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_REASONING_EFFORT`, `OPENAI_TIMEOUT_SECONDS`: query-planning configuration. Use `gpt-6-luna` with `low` reasoning as the production latency/quality baseline; benchmark `none` before adopting it.
- `SEMANTIC_CATALOG_ENABLED`, `SEMANTIC_EMBEDDING_MODEL`, `SEMANTIC_CATALOG_MIN_SIMILARITY`: opt-in pgvector hybrid catalog retrieval. After the migration, run `python backend/scripts/backfill_semantic_catalog.py` once in the deployed backend environment.
- `EXPLORE_SEARCH_SOFT_TIMEOUT_SECONDS`, `EXPLORE_SEARCH_HARD_TIMEOUT_SECONDS`: async job budgets
- `EXPLORE_SEARCH_REPOSITORY_LANE_TIMEOUT_SECONDS`, `EXPLORE_SEARCH_CODE_LANE_TIMEOUT_SECONDS`: retrieval lane budgets
- `EXPLORE_ADMISSION_MODE`, `EXPLORE_SEARCH_RELEVANCE_CUTOFF`: canonical result policy
- External discovery runs for every Explore search and is merged with local catalog candidates before source-agnostic admission and ranking.
- `SEARCH_DIAGNOSTICS_USER_EMAILS`: restricted diagnostic access
- `SEARCH_QUOTA_BYPASS_USER_EMAILS`: restricted bypass for SciScope product quotas only; it does not bypass provider limits

Provider authentication, rate limits, and unavailable search capabilities are handled in `sources/` and exposed through source statuses.

## Architecture Contract

[AGENTS.md](../AGENTS.md) defines the backend boundaries.

Core direction:

- `api -> services -> sources/storage -> database`
- `models` and `config` are shared layers
- source adapters perform provider IO only
- persistence logic stays in `storage`
- orchestration lives in `services`
