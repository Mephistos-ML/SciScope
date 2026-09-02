# SciScope Architecture

## System Shape

SciScope is a structured monolith with one backend application, one frontend application, one database, and background monitoring inside the backend process.

The system centres on topic-driven discovery, repositories, subscriptions, and Feed events.

## End-to-End Flows

### Explore

`topic description -> AI query plan -> local catalog retrieval -> external fallback when coverage is low -> candidate merge -> admission -> ranking -> results`

Ownership:

- `services/ai/`: builds a concise query plan from one topic description
- `services/search/catalog.py`: maps catalog records into standard retrieval candidates and persists admitted external discoveries
- `services/search/retrieval/`: coordinates source lanes, deadlines, merging, evidence, and partial coverage
- `sources/github/search/` and `sources/gitlab/search/`: perform provider-specific repository retrieval and supported code retrieval
- `services/search/admission/`: applies repository-name gates and conservative candidate checks
- `services/search/ranking/`: builds source-independent features and explainable heuristic scores
- `services/search/explore/`: owns job lifecycle and Explore response assembly

Explore is read-only and does not create subscriptions.

### Subscription

`clicked repository -> repository upsert -> subscription create -> baseline sync`

The subscription is an explicit user decision to monitor one repository.

### Monitoring

`subscription watch -> source checkpoints -> releases and default-branch commits -> append-only Feed events`

Ownership:

- `services/subscriptions/`: subscription lifecycle and baseline initialization
- `services/monitoring/`: background scheduler and source polling
- `services/feed/`: Feed-event assembly
- `storage/`: catalog repository profiles, retrieval evidence, checkpoints, subscriptions, and Feed persistence
- `sources/github/` and `sources/gitlab/`: provider monitoring adapters

## Stable Boundaries

### API

Owns FastAPI transport, authentication boundaries, payload validation, and response mapping. It contains no source or persistence logic.

### AI Planning

Owns generation of a search query plan from a topic description. It does not retrieve repositories, create subscriptions, or persist search candidates.

### Search

Owns topic-driven Explore behavior: retrieval orchestration, candidate merge, admission, ranking, asynchronous jobs, partial coverage, and response assembly. It does not persist subscriptions.

### Sources

Own provider-specific external IO: authentication, repository retrieval, supported code retrieval, release and commit monitoring, and checkpoint resolution. Sources do not apply admission or ranking policy.

### Storage

Owns persistence contracts for repositories, subscriptions, checkpoints, Feed events, auth records, and Explore usage. SQLAlchemy records stay under `database/records/` and are used only by storage.

### Monitoring

Owns periodic scans, monitoring control, and the creation of user Feed events from subscribed repositories.

## Search Delivery Policy

Admission runs before ranking. It is deliberately conservative and removes obvious non-software candidates such as paper lists, teaching materials, and repository-name classes excluded by policy.

Ranking uses an explainable heuristic score:

- query coverage with diminishing returns
- strongest match location for each query
- bounded evidence density

Explore results must pass the relevance cutoff. Beta diagnostics show candidates rejected by gates, admission, or the cutoff to configured internal users.

External failures are coverage information, not empty results. Completed candidates remain available when a lane times out or one source is unavailable. Provider rate limits stop further work for the affected lane and surface a retry window when supplied by the provider.

## Domain Model

Core objects:

- `Repository`: canonical identity and current provider metadata for a catalog repository
- `RepositorySearchEvidence`: durable query-specific evidence of where a repository matched
- `Subscription`: one repository watch owned by one user
- `Signal`: canonical provider event shape
- `FeedEvent`: durable per-user delivery record for a discovered release or default-branch commit

## Provider Coverage

GitHub supports repository retrieval, code retrieval, and monitoring.

GitLab supports repository retrieval and monitoring. GitLab.com global code retrieval is disabled because its public API does not provide the required global blob-search capability.

Gitee, GitCode, and GitVerse remain unavailable source modules.

## Dependency Direction

`api -> services -> sources/storage -> database`

`models` and `config` are shared layers. The complete change contract is maintained in [AI_CONTRACT.md](../AI_CONTRACT.md).
