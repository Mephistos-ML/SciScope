# SciScope Architecture

## System Shape

SciScope is a structured monolith with one backend application, one frontend application, one PostgreSQL database, a separate Explore worker, and scheduled repository monitoring.

The system centres on topic-driven discovery, repositories, subscriptions, and Feed events.

## End-to-End Flows

### Explore

`topic description -> AI query plan -> catalog and external retrieval -> candidate merge -> admission -> ranking -> results`

Ownership:

- `services/ai/`: builds a concise query plan from one topic description
- `services/search/catalog.py`: maps catalog records into standard retrieval candidates and persists admitted external discoveries
- `services/search/retrieval/`: coordinates source lanes, deadlines, merging, evidence, and partial coverage
- `integrations/repositories/github/search/` and `integrations/repositories/gitlab/search/`: perform provider-specific repository retrieval and supported code retrieval
- `services/search/admission/`: applies repository-name gates and conservative candidate checks
- `services/search/ranking/`: builds source-independent features and explainable heuristic scores
- `services/search/explore/`: owns job lifecycle and Explore response assembly

Explore is read-only and does not create subscriptions.

### Subscription

`clicked repository ID -> canonical catalog profile (provider lookup if missing) -> subscription create`

The subscription is an explicit user decision to monitor one repository. Browser
names and URLs never replace global profiles. The API composition boundary injects
the registered profile-loading capability into the subscription service; provider
payload mapping stays in repository integrations, and insert-if-absent stays in storage.

### Monitoring

`subscription watch -> source checkpoints -> releases and default-branch commits -> append-only Feed events`

Ownership:

- `services/subscriptions/`: subscription lifecycle and canonical profile resolution
- `jobs/scan_subscriptions.py`: monitoring adapter registry wiring
- `services/monitoring/`: scanning through an injected monitoring capability
- `services/feed/`: Feed-event assembly
- `storage/`: catalog repository profiles, retrieval evidence, checkpoints, subscriptions, and Feed persistence
- `integrations/repositories/github/` and `integrations/repositories/gitlab/`: provider monitoring adapters

## Stable Boundaries

### Composition

`app/composition/search.py` selects the configured query planner and registers
supported GitHub/GitLab search lanes. The API and worker entrypoints each assemble
an immutable `ExploreDependencies` value and pass it into search use cases.
Services invoke the supplied capabilities without discovering implementations or
falling back to a default provider registry. All retrieval lanes accept an explicit
monotonic deadline. Planner identity travels with the executable capability;
initial worker execution records that identity under its lease, and expansions
retain the identity of their already committed plan.

### API

Owns FastAPI transport, authentication boundaries, payload validation, and response mapping. It contains no source or persistence logic.

### AI Planning

Application AI modules own planner/embedding capability contracts and search-plan helpers. Shared AI models own stable dependency errors. `integrations/ai/openai/` owns Responses and embeddings HTTP calls, provider payload validation, and mapping into those contracts. Composition binds credentials, endpoint, timeout, model, and vector dimensions. Provider failures become safe application errors; planning fails explicitly, while optional semantic retrieval preserves lexical results. Embedding vectors are matched by input index and must contain finite numbers of the configured dimension. Planner output requires exactly three distinct, nonempty string queries, each bounded to 500 characters. No layer retries AI calls automatically.

### Search

Owns topic-driven Explore behavior: retrieval orchestration, candidate merge, admission, ranking, asynchronous jobs, partial coverage, and response assembly. It does not persist subscriptions.

### Integrations

Own provider-specific external IO: authentication, repository retrieval, supported code retrieval, release and commit monitoring, and checkpoint resolution. Turnstile HTTP verification lives in `integrations/security/cloudflare/`; `services/security/` owns enablement and token limits. Composition binds credentials and timeout, and HTTP routes use the supplied capability. Malformed or oversized provider responses are unavailable verification outcomes, never successful proofs.

Repository integrations share protocol helpers under `integrations/repositories/common/`. Repository helper and provider packages keep marker-only entrypoints; callers import the owning concrete module. The monitoring registry registers each provider’s `monitor` module directly. AI adapters live separately under `integrations/ai/` and do not depend on those helpers. Integrations do not apply admission or ranking policy.

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

`api -> services -> integrations/storage -> database`

`models` and `config` are shared layers. The complete change contract is maintained in [AGENTS.md](../AGENTS.md).

Explore admission failures carry the domain access decision. The API exception
handler owns HTTP status, response serialization, and retry headers.
