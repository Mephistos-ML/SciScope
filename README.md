# SciScope

SciScope is a live service for discovering and monitoring domain-specific scientific software.

Public service: `https://sciscope.uk/`

`topic description -> AI query plan -> external retrieval -> admission -> ranking -> results -> explicit subscribe -> monitoring -> feed`

## What The Service Does

- accepts a free-form scientific topic description
- generates a concise AI-assisted query plan
- retrieves repository and, where supported, code-search candidates from GitHub and GitLab
- merges duplicate candidates and records source-independent match evidence
- removes obvious non-software repositories through conservative admission gates
- ranks retained repositories with an explainable heuristic score and configurable cutoff
- runs searches asynchronously and returns completed work when a source is slow, rate-limited, or unavailable
- lets signed-in users subscribe to repositories
- monitors subscribed repositories for releases and default-branch commits
- delivers new activity through an append-only personal Feed

## User Flow

1. A user enters a topic description in Explore.
2. SciScope generates a small set of distinct search queries.
3. External retrieval lanes collect repository candidates.
4. SciScope deduplicates candidates, applies admission, and ranks the retained pool.
5. The normal Explore response shows repositories above the relevance cutoff.
6. The user explicitly subscribes to repositories worth monitoring.
7. New releases and default-branch commits appear in the user's Feed.

Explore does not require sign-in. Subscriptions and Feed access require Google sign-in because they are user-owned.

## Ranking

SciScope currently uses a transparent heuristic baseline rather than a learned model. The score combines:

- query coverage, with diminishing returns for additional matching queries
- match location, where repository metadata is stronger evidence than an incidental code match
- bounded evidence density, so repetitive hits cannot dominate the result

The formula and relevance cutoff are versionable product policy. They will be tuned against a verified evaluation set before a future learning-to-rank stage.

## Source Coverage

Active:

- GitHub repository and code retrieval
- GitHub release and default-branch commit monitoring
- GitLab repository retrieval
- GitLab release and default-branch commit monitoring

GitLab.com global code search is disabled because its public API does not provide the required global blob-search capability. GitLab repository retrieval and monitoring remain active.

## Architecture

SciScope is a structured monolith with a React + TypeScript frontend, FastAPI backend, and Postgres persistence layer.

Main backend areas:

- `backend/app/api/`: FastAPI transport, auth, and request validation
- `backend/app/services/ai/`: AI query planning
- `backend/app/services/search/`: retrieval, admission, ranking, async jobs, and observability
- `backend/app/services/subscriptions/`: repository subscriptions
- `backend/app/services/monitoring/`: repository monitoring and Feed creation
- `backend/app/sources/`: GitHub and GitLab provider adapters
- `backend/app/storage/`: persistence contracts
- `backend/app/database/records/`: SQLAlchemy records used only by storage
- `backend/alembic/`: database migrations

The core dependency direction is `api -> services -> sources/storage -> database`. Details are recorded in [AI_CONTRACT.md](AI_CONTRACT.md) and [docs/architecture.md](docs/architecture.md).

## API Surfaces

- `POST /api/explore/search`
- `POST /api/explore/search-jobs`
- `GET /api/explore/search-jobs/{id}`
- `GET /api/subscriptions`
- `POST /api/subscriptions`
- `DELETE /api/subscriptions/{id}`
- `GET /api/feed`
- `GET /api/feed/{id}`
- `POST /api/start`
- `POST /api/stop`

## Operations

- External provider failures and timeouts degrade search coverage rather than discarding completed work.
- GitHub code retrieval stops after a provider rate-limit response and reports a retry window when the provider supplies one.
- Search emits structured events for planning, retrieval, admission, ranking, and completion.
- Public search quotas and abuse controls are configured through environment variables.
- Restricted beta diagnostics are available only to configured internal users.

## Development

- Python backend: `>=3.11`
- Frontend: Vite, React, and TypeScript
- Database: Postgres with SQLAlchemy and Alembic

Backend setup and operations are documented in [backend/README.md](backend/README.md).

## Author

SciScope is an independent product designed and built end-to-end by Ernest Borysenko.
