# SciScope

SciScope is a research signal monitoring system for narrow scientific topics.

The long-term goal is simple:

- a researcher describes a niche topic
- SciScope builds a structured research profile
- SciScope monitors multiple messy sources
- SciScope surfaces only the updates that are likely to matter

This repository is the first pNMR-focused proof of concept for that idea.

## Vision

SciScope is not meant to be another generic paper summarizer.

The target product is a research radar that can answer:

- What changed in my field this week?
- Which new software, papers, releases, or community signals are relevant to my topic?
- What should I watch continuously instead of searching manually?

The intended shape is:

`topic -> profile -> discovery -> monitoring -> matching -> dashboard -> digest`

## What Works Now

Current working scope:

- seeded topic: `pnmr`
- seeded research profile for paramagnetic NMR
- GitHub repository discovery from profile terms
- persistent watched repository memory in Postgres
- per-repository release checkpoints
- continuous monitoring loop for GitHub releases
- local dashboard for signals and pipeline debugging

Current proof-of-concept behavior:

1. press `Start`
2. SciScope builds GitHub search queries from pNMR profile terms
3. SciScope discovers candidate repositories
4. relevant repositories are stored as watched entities
5. SciScope monitors those repositories for new GitHub releases
6. matching release signals appear in the dashboard

Important: the current live pipeline is GitHub-first. It does not yet ingest ChemRxiv, conference sites, LinkedIn, or email digests.

## Why This Project Exists

The problem is not finding obvious major papers.

The problem is missing small but important signals:

- niche software releases
- workshop announcements
- community tools
- field-specific repositories
- updates that matter to a narrow research workflow

SciScope is being built for two connected goals:

- help researchers notice fresh niche developments earlier
- help specialised scientific work become more visible to the communities that actually care about it

That means SciScope is not only a monitoring tool for readers. It is also a discoverability layer for authors, tool builders, labs, and technical community work that would otherwise stay hard to find.

## Current Architecture

SciScope is currently a structured monolith with a split frontend/backend workspace.

High-level backend flow:

- `seeds/`
  - current bootstrap topic and profile data
- `services/topic_registry.py`
  - resolves the active topic/profile for the local runtime
- `sources/repositories/runtime.py`
  - coordinates repository-family discovery and monitoring across concrete adapters
- `services/discovery.py`
  - stores relevant repositories as watched entities
- `sources/repositories/github/` and `sources/repositories/gitlab/`
  - implement repository discovery and release monitoring per source
- `services/runtime.py`
  - orchestrates start/stop, scan cycles, status payloads, and signal views
- `storage/`
  - persists watched entities, topic matches, checkpoints, and seen signals

Key domain objects:

- `ResearchTopic`
- `ResearchProfile`
- `Entity`
- `TopicEntityMatch`
- `EntityCheckpoint`
- `RawSignal`
- `NormalizedSignal`

## Current Limits

What this project does not do yet:

- user-created topics
- LLM-generated research profiles in the live path
- multi-source ingestion beyond GitHub
- ranking beyond deterministic term matching
- email digests
- authentication
- subscriptions

This is still a pNMR-tuned engineering proof of concept, not a finished product.

## Run Locally

Backend:

```bash
cd /Users/mephistos/git/SciScope
python3 -m venv .venv
./.venv/bin/pip install -e .
export APP_ENV=development
export APP_HOST=127.0.0.1
export APP_PORT=8000
export CORS_ORIGINS=http://localhost:5173
export DATABASE_URL=postgresql+psycopg://sciscope:sciscope@localhost:5432/sciscope
./.venv/bin/alembic upgrade head
./.venv/bin/python -m app.main
```

Frontend:

```bash
cd /Users/mephistos/git/SciScope/frontend
npm install
cp .env.example .env
npm run dev
```

Open:

```text
http://localhost:5173
```

## What To Look For On The Dashboard

After pressing `Start`, a healthy pipeline should show:

- non-empty `Discovery queries`
- non-empty `Watched repositories`
- non-empty `Release checkpoints`
- a populated `Last discovery result`

If a watched repository publishes a new GitHub release after monitoring starts, SciScope should surface it as a signal on the dashboard.

## Near-Term Milestone

The immediate milestone for this repository is:

> SciScope discovers relevant pNMR repositories from topic terms alone, watches them continuously, and catches a real new GitHub release without repository hardcoding.

## Notes

- Python backend: `>=3.11`
- Frontend: Vite + React + TypeScript
- Persistent state now runs through Postgres via SQLAlchemy + Alembic
- Architecture notes live in [docs/architecture.md](/Users/mephistos/git/SciScope/docs/architecture.md)
