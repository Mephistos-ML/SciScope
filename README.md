# SciScope

<p align="center">
  <img src="frontend/src/assets/brand/sciscope-logo.svg" alt="SciScope logo" width="188">
</p>

Discover scientific software for your research topic and follow repository updates in one feed.

**[Try SciScope](https://sciscope.uk/)** · [Architecture](docs/architecture.md) · [Development](backend/README.md)

[![CI](https://github.com/Mephistos-ML/SciScope/actions/workflows/test.yml/badge.svg)](https://github.com/Mephistos-ML/SciScope/actions/workflows/test.yml)
[![GitHub release](https://img.shields.io/github/v/release/Mephistos-ML/SciScope)](https://github.com/Mephistos-ML/SciScope/releases)
[![Backend coverage](https://codecov.io/gh/Mephistos-ML/SciScope/branch/main/graph/badge.svg?flag=backend)](https://codecov.io/gh/Mephistos-ML/SciScope)

## See it in action

https://github.com/user-attachments/assets/29c90665-9847-4a54-a493-ed8516fa1a54

## From a research topic to software you can follow

Scientific software is spread across repositories, and finding relevant tools often requires several searches with different terminology.

SciScope searches GitHub and GitLab from a description of your research topic. You can review the results, subscribe to useful repositories, and follow their releases and code updates in a personal feed.

1. **Describe your topic.** Enter a research area or task, such as `paramagnetic NMR tools`. Optionally choose a scientific domain to clarify the context.
2. **Explore repositories.** SciScope generates search queries, combines results, and ranks candidates by relevance.
3. **Follow useful tools.** Subscribe to the repositories you want to monitor.
4. **Review updates.** Browse release cards and grouped commits, expand their details, and mark updates as read.

Explore is available without an account. Google sign-in enables subscriptions and your personal feed.

## Repository updates

Each new release appears as a feed card with its description and an expandable list of confirmed commits.

Other newly discovered commits are grouped by monitoring scan. Commit entries link directly to the provider, so you can inspect the original changes.

Opening a card does not mark it as read. Read actions are explicit, and incomplete release commit coverage is shown in the interface.

## How it works

SciScope is a structured monolith built with React, TypeScript, FastAPI, and PostgreSQL.

```mermaid
flowchart LR
    User[Browser] --> API[FastAPI]
    API --> DB[(PostgreSQL)]
    Worker[Search worker] --> DB
    Worker --> Providers[GitHub / GitLab]
    Worker --> AI[AI query planning]
    Monitor[Scheduled monitoring] --> Providers
    Monitor --> DB
```

AI assists with query planning. Repository relevance is scored using an explainable heuristic based on query coverage, match location, and evidence density.

The API, search worker, and scheduled monitoring run as separate processes sharing PostgreSQL.

## Reliability and verification

- Searches run asynchronously and preserve results delivered before their deadline.
- Search requests use bounded time budgets; code-search pages also have a response-size limit.
- Feed publications and monitoring checkpoints commit atomically.
- Release publication waits for static checks, backend and PostgreSQL tests, frontend checks, and browser journeys.
- PostgreSQL tests cover database-specific transactions and concurrency.
- Browser tests exercise search, subscriptions, grouped feed updates, and read-state behavior.

## Current scope

SciScope uses a transparent heuristic ranker. Results depend on question
specificity and provider coverage, so relevant repositories may be missed.
Repository discovery and monitoring cover GitHub and GitLab.

## Development and documentation

- [Backend setup and package structure](backend/README.md)
- [Frontend setup](frontend/README.md)
- [Architecture and transaction guarantees](docs/architecture.md)
- [Recovery instructions](docs/operations/backend-recovery.md)
- [Browser test setup](frontend/e2e/README.md)
- [Engineering contract](AGENTS.md)

## Author

Designed and built end-to-end by **Ernest Borysenko**.

## License

Copyright 2026 Ernest Borysenko.

SciScope's original code and documentation are licensed under the
[Apache License, Version 2.0](LICENSE).

Third-party components and downloaded datasets retain their respective licenses and attribution requirements.
