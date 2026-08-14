# Backend

SciScope backend is the API, auth, persistence, and monitoring layer behind `https://sciscope.uk/`.

## Responsibility

The backend owns:

- public Explore search
- Google-authenticated subscriptions
- repository persistence
- monitoring checkpoints
- release signal ingestion
- signal APIs
- background monitoring control

## Service Model

The backend is built around one repository-first runtime:

- Explore returns repository candidates
- subscriptions store explicit repository watches
- monitoring loads signals for subscribed repositories
- source differences live in hosting adapters

Core domain objects:

- `Repository`
- `Subscription`
- `Signal`
- `SignalMatch`

## API Areas

### Explore

- `POST /api/explore/search`

Input:

- `topicDescription`

Output:

- AI-generated search queries
- matched repository results
- per-source status diagnostics

### Auth

- `GET /api/me`
- `GET /api/auth/google/start`
- `GET /api/auth/google/callback`
- `POST /api/logout`

Auth model:

- Google OAuth
- first-party user sessions
- cookie-backed authenticated requests

### Subscriptions

- `GET /api/subscriptions`
- `POST /api/subscriptions`
- `DELETE /api/subscriptions/{id}`

Subscription payload model:

- repository identity
- repository source
- repository full name
- repository URL
- `selectedQuery`

### Monitoring And Signals

- `POST /api/start`
- `POST /api/stop`
- `GET /api/status`
- `GET /api/signals`
- `GET /api/signals/{id}`

## Request Flows

### Explore Flow

`topic description -> AI query plan -> GitHub/GitLab discovery -> deterministic matching -> result payload`

Main modules:

- `app/services/ai/`
- `app/services/search/explore.py`
- `app/services/search/matching.py`
- `app/sources/github/discovery.py`
- `app/sources/gitlab/discovery.py`

### Subscription Flow

`clicked repository -> repository upsert -> subscription create -> baseline sync`

Main modules:

- `app/api/routes/subscriptions.py`
- `app/services/subscriptions/service.py`
- `app/storage/repositories.py`
- `app/storage/subscriptions.py`
- `app/sources/runtime.py`

### Monitoring Flow

`subscription watch -> source checkpoint -> release fetch -> Signal -> signal view`

Main modules:

- `app/services/runtime.py`
- `app/sources/runtime.py`
- `app/sources/github/monitor.py`
- `app/sources/gitlab/monitor.py`
- `app/storage/seen_signals.py`

## Source Adapter Model

Active source adapters:

- GitHub
- GitLab

Unavailable source modules:

- Gitee
- GitCode
- GitVerse

Adapter rules:

- discovery adapters return repository `Signal` objects
- monitoring adapters return release `Signal` objects
- adapters shape source payloads and keep source-specific metadata
- adapters do not decide subscriptions

## Persistence

Primary persistence areas:

- `repositories`
- `subscriptions`
- `repository_checkpoints`
- `seen_signals`
- auth tables for users, oauth accounts, and sessions

Persistence stack:

- SQLAlchemy
- Postgres
- Alembic migrations in `backend/alembic/versions/`

## Monitoring Model

Monitoring state is scoped to subscribed repositories.

The runtime tracks:

- subscribed repository set
- source-specific release checkpoints
- seen signal ids by `(source, item_id)`
- in-memory signal views for API delivery

## Code Layout

- `backend/app/api/`
  - FastAPI transport
- `backend/app/services/`
  - application logic
- `backend/app/sources/`
  - repository-hosting adapters and replay fixtures
- `backend/app/storage/`
  - persistence contracts
- `backend/app/database/`
  - SQLAlchemy models and sessions
- `backend/app/models/`
  - domain objects
- `backend/tests/`
  - backend test suite

## Engineering Notes

- FastAPI is the HTTP transport
- background monitoring runs inside the backend service
- the runtime uses one shared `Signal` model across ingestion, matching, storage, and delivery
- the schema history is managed through Alembic revision files
