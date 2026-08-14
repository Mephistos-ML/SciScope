# SciScope

SciScope is a live repository discovery and monitoring service for narrow research workflows.

Public service:

- `https://sciscope.uk/`

SciScope turns a research topic description into a monitored repository watchlist:

`topic description -> AI search queries -> repository results -> explicit subscribe -> release monitoring`

## Product Snapshot

- Explore is public and search-driven
- subscriptions are explicit per-repository watches
- Feed does not run initial discovery
- repository hostings are the source family

The service is built around one operational assumption:

- repositories are the monitored object
- source differences belong to hosting adapters
- monitoring starts only after an explicit user subscription

## What The Service Does

- public Explore flow from a free-form topic description
- AI-generated repository search queries
- repository discovery on GitHub and GitLab
- per-result `Subscribe` actions in Explore
- Google sign-in for saved subscriptions
- direct repository subscriptions in Postgres
- repository release checkpoints per subscription
- background monitoring loop for subscribed repositories
- signal storage and signal APIs backed by one shared `Signal` model

User flow:

1. User enters a topic description in Explore.
2. SciScope generates repository search queries.
3. GitHub and GitLab return candidate repositories.
4. User explicitly subscribes to selected repositories.
5. Backend stores repository watches and initializes monitoring checkpoints.
6. Monitoring loads release signals for subscribed repositories.

Runtime rules:

- Explore does not require sign-in.
- Feed requires Google sign-in because subscriptions are user-owned.
- Monitoring is repository-first and does not persist topic descriptions.
- The frontend does not expose `Start` / `Stop`; the monitoring loop is controlled through backend endpoints.

## Engineering Signals

- live public product at `sciscope.uk`
- typed frontend and backend codebase
- persistent relational storage with Alembic-managed schema
- Google OAuth for user-owned subscriptions
- explicit source adapters for GitHub and GitLab
- background monitoring with persisted release checkpoints
- one canonical `Signal` model across ingestion, matching, storage, and delivery
- backend signal and subscription APIs separated from the web UI
- repository-level subscriptions instead of implicit watchlists
- test-backed backend code in the repository

## Core Concepts

### Explore

Explore is a read-only discovery surface.

- input: one topic description
- output: ranked repository results
- sources: GitHub and GitLab
- persistence: none

### Subscription

A subscription is one explicit repository watch.

Stored fields:

- `subscription_id`
- `user_id`
- `repository_id`
- `selected_query`
- `created_at`

`selected_query` is only a snapshot of the query that produced the clicked result. The subscription itself is repository-centric.

### Signal

SciScope uses one canonical `Signal` model.

It contains:

- source identity
- signal kind
- item id
- title
- url
- published time
- raw text
- normalized text
- payload

The backend uses a single `Signal` type that carries both raw and normalized text.

## Architecture

SciScope is a structured monolith with a split frontend/backend workspace.

System shape:

- React + TypeScript frontend
- FastAPI backend
- Postgres persistence
- SQLAlchemy + Alembic for data access and migrations
- background monitoring inside the backend service

Backend shape:

Main backend areas:

- `backend/app/api/`
  - FastAPI transport and route wiring
- `backend/app/services/ai/`
  - AI query planning from topic descriptions
- `backend/app/services/search/`
  - Explore search and deterministic matching
- `backend/app/services/subscriptions/`
  - create/list/delete direct repository subscriptions
- `backend/app/services/runtime.py`
  - monitoring orchestration and signal views
- `backend/app/sources/`
  - repository-hosting adapters and replay fixtures
- `backend/app/storage/`
  - repositories, subscriptions, seen signals, auth
- `backend/alembic/`
  - database migrations

Key domain objects:

- `Repository`
- `Subscription`
- `Signal`
- `SignalMatch`

## Source Coverage

Active:

- GitHub repository discovery
- GitHub release monitoring
- GitLab repository discovery
- GitLab release monitoring

Unavailable source modules:

- Gitee
- GitCode
- GitVerse

## Service Surfaces

### Web App

- public Explore interface
- Google-authenticated subscription and Feed interface
- repository result pages rendered through the frontend app

### Backend API

- Explore search endpoints
- subscription endpoints
- signal endpoints
- monitoring control endpoints
- Google OAuth session endpoints

## Scope Boundaries

The repository excludes:

- non-repository source families such as papers, conferences, or social feeds
- automatic subscription creation from Explore results
- persistent topic objects in the runtime path
- ranking beyond deterministic term matching
- a finished Feed UI for rendering monitored signals
- notifications or digests

## Useful API Endpoints

- `POST /api/explore/search`
- `GET /api/subscriptions`
- `POST /api/subscriptions`
- `DELETE /api/subscriptions/{id}`
- `GET /api/signals`
- `GET /api/signals/{id}`
- `POST /api/start`
- `POST /api/stop`

## Development Notes

- Python backend: `>=3.11`
- Frontend: Vite + React + TypeScript
- Persistent state runs through Postgres via SQLAlchemy + Alembic
- Google OAuth gates user-owned subscriptions
- Architecture notes live in [docs/architecture.md](/Users/ernestborysenko/git/SciScope/docs/architecture.md)

## Author

SciScope is an independent product designed and built end-to-end by Ernest Borysenko.
