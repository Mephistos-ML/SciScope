# Backend

SciScope backend is the API, auth, search, persistence, and monitoring layer behind `https://sciscope.uk/`.

## Responsibility

The backend owns:

- public asynchronous Explore search
- AI query planning, external retrieval, admission, and heuristic ranking
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
- `POST /api/explore/search-jobs`
- `GET /api/explore/search-jobs/{id}`

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

`topic description -> AI query plan -> parallel retrieval lanes -> candidate merge -> admission -> heuristic ranking -> result payload`

Main modules:

- `app/services/search/retrieval/`
- `app/services/search/admission/`
- `app/services/search/ranking/`
- `app/services/search/explore/`
- `app/sources/github/search/`
- `app/sources/gitlab/search/`

Explore runs as an asynchronous job. Repository and code-search lanes are isolated by source and timeout budget. A source failure or code-query timeout produces partial coverage while retaining completed candidates. GitHub code search stops after a rate-limit response and reports a provider retry window when available.

Admission removes obvious non-software candidates. Ranking scores the retained pool from query coverage, source-independent match location, and bounded evidence density. The configurable relevance cutoff controls normal Explore delivery; restricted beta diagnostics can expose the full evaluated pool.

### Subscription Flow

`clicked repository -> repository upsert -> subscription create -> baseline sync`

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

- repositories
- subscriptions
- repository checkpoints
- feed events
- Explore usage records
- users, OAuth accounts, and sessions

Search execution state is runtime-local. Repository candidates are persisted only after a subscription; SciScope does not crawl or mirror whole repository hosts.

Persistence uses SQLAlchemy and Postgres. Alembic migrations live in `alembic/versions/`.

## Operations

Important environment variables:

- `APP_LOG_LEVEL`: structured search-event log level; use `INFO` in deployed environments
- `AI_PLANNER_MODE`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TIMEOUT_SECONDS`: query-planning configuration
- `EXPLORE_SEARCH_SOFT_TIMEOUT_SECONDS`, `EXPLORE_SEARCH_HARD_TIMEOUT_SECONDS`: async job budgets
- `EXPLORE_SEARCH_REPOSITORY_LANE_TIMEOUT_SECONDS`, `EXPLORE_SEARCH_CODE_LANE_TIMEOUT_SECONDS`: retrieval lane budgets
- `EXPLORE_ADMISSION_MODE`, `EXPLORE_SEARCH_RELEVANCE_CUTOFF`: canonical result policy
- `BETA_USER_EMAILS`: restricted diagnostic access
- `SEARCH_QUOTA_BYPASS_USER_EMAILS`: restricted bypass for SciScope product quotas only; it does not bypass provider limits

Provider authentication, rate limits, and unavailable search capabilities are handled in `sources/` and exposed through source statuses rather than hidden as empty results.

## Architecture Contract

[AI_CONTRACT.md](../AI_CONTRACT.md) defines the backend boundaries.

Core direction:

- `api -> services -> sources/storage -> database`
- `models` and `config` are shared layers
- source adapters perform provider IO only
- persistence logic stays in `storage`
- orchestration lives in `services`
