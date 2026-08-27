# Backend

SciScope backend is the API, auth, persistence, and monitoring layer behind `https://sciscope.uk/`.

## Responsibility

The backend owns:

- public Explore search
- Google-authenticated subscriptions
- repository persistence
- monitoring checkpoints
- durable user feed events
- background monitoring control

## Service Model

The backend is repository-first:

- Explore returns repository candidates
- subscriptions store explicit repository watches
- monitoring polls subscribed repositories for releases and default-branch commits
- feed delivery is append-only per user

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

Feed entries are created only for events discovered after subscription time.

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

`topic description -> AI query plan -> external retrieval -> admission -> result payload`

Main modules:

- `app/services/search/`
- `app/sources/github/search/`
- `app/sources/gitlab/search/`

### Subscription Flow

`clicked repository -> repository upsert -> subscription create -> baseline sync`

Main modules:

- `app/api/routes/subscriptions.py`
- `app/services/subscriptions/`
- `app/services/monitoring/`
- `app/storage/repositories/`
- `app/storage/subscriptions/`

### Monitoring Flow

`subscription watch -> source checkpoints -> releases and commits -> feed events`

Main modules:

- `app/services/runtime.py`
- `app/services/monitoring/`
- `app/services/feed/`
- `app/sources/github/monitor.py`
- `app/sources/gitlab/monitor.py`
- `app/storage/feed/`

## Persistence

Primary persistence areas:

- `repositories`
- `subscriptions`
- `repository_checkpoints`
- `feed_events`
- auth tables for users, oauth accounts, and sessions

Persistence stack:

- SQLAlchemy
- Postgres
- Alembic migrations in `backend/alembic/versions/`

## Architecture Contract

Current backend boundaries are enforced by convention through [AI_CONTRACT.md](/Users/ernestborysenko/git/SciScope/AI_CONTRACT.md).

Core direction:

- `api -> services -> sources/storage -> database`
- `models` and `config` are shared layers
- source adapters do external IO only
- persistence logic stays in `storage`
- orchestration lives in `services`
