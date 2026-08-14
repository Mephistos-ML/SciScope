# SciScope Architecture

## System Shape

SciScope is a structured monolith with:

- one backend application
- one frontend application
- one database
- background monitoring inside the backend process

The runtime is repository-only.

The runtime hierarchy is centered on repositories, subscriptions, and signals.

## End-to-End Flow

### Explore Flow

`topic description -> AI query plan -> repository discovery -> deterministic matching -> results`

Ownership:

- `services/ai/`
  - builds search queries from the topic description
- `sources/github/discovery.py`
  - loads GitHub repository candidates
- `sources/gitlab/discovery.py`
  - loads GitLab repository candidates
- `services/search/explore.py`
  - merges source results, matches them against generated queries, and returns Explore payloads

Explore is read-only and does not create subscriptions.

### Subscription Flow

`clicked repository -> repository upsert -> subscription create -> baseline sync`

Ownership:

- `api/routes/subscriptions.py`
  - validates repo-centric request payloads
- `services/subscriptions/service.py`
  - builds a `Repository`, stores it, creates the subscription, and starts baseline sync
- `storage/repositories.py`
  - persists repository records and checkpoints
- `storage/subscriptions.py`
  - persists direct repository subscriptions

The subscription is the explicit user decision to monitor one repository.

### Monitoring Flow

`subscription watch -> source-specific checkpoint -> release fetch -> Signal -> signal view`

Ownership:

- `services/runtime.py`
  - background scheduler and signal view assembly
- `sources/runtime.py`
  - routes each watch to the correct source adapter
- `sources/github/monitor.py`
  - loads GitHub releases for one subscribed repository
- `sources/gitlab/monitor.py`
  - loads GitLab releases for one subscribed repository
- `storage/seen_signals.py`
  - persists seen signal ids by `(source, item_id)`

The monitoring loop processes repositories from user subscriptions.

## Stable Boundaries

### API

Owns transport.

- FastAPI request/response handling
- auth redirects
- payload validation
- no source logic
- no persistence logic

### AI Planning

Owns query generation.

- input: one topic description
- output: one query plan
- no repository storage
- no subscription creation

### Search

Owns Explore behavior.

- source discovery fan-out
- deterministic matching
- result ranking and serialization
- no subscription persistence

### Subscriptions

Owns explicit repository watches.

- create
- list
- delete
- baseline initialization

### Sources

Own repository-hosting adapters.

- repository discovery
- release monitoring
- source auth
- checkpoint resolution

Sources do not decide whether a repository should be subscribed.

### Storage

Owns persistence contracts.

- repositories
- subscriptions
- seen signals
- auth records

### Runtime

Owns the monitoring loop.

- start / stop
- periodic scans
- signal views
- status payloads

## Domain Model

Core objects:

- `Repository`
- `Subscription`
- `Signal`
- `SignalMatch`

### Repository

One canonical watched repository with:

- `repository_id`
- `source`
- `full_name`
- `url`
- `metadata`

### Subscription

One direct watch owned by one user.

- `subscription_id`
- `user_id`
- `repository_id`
- `selected_query`
- `created_at`

### Signal

One canonical internal signal object used everywhere.

- source and item identity
- signal kind
- title and url
- published time
- `raw_text`
- `normalized_text`
- `payload`

The `Signal` model stores both raw and normalized text.

## Source Contracts

Repository discovery adapters return candidate repository `Signal` objects.

Monitoring adapters return release `Signal` objects for one subscribed repository.

Both contracts keep these rules:

- source adapter fetches and shapes data
- source adapter keeps source-specific payload details
- matching stays outside the source layer
- deduplication anchor is `(source, item_id)`

## Constraints

- Explore is public, Feed is user-owned
- subscriptions are repository-only
- monitoring is release-only
- GitHub and GitLab are active providers
- Gitee, GitCode, and GitVerse return unavailable or empty results
- the Feed UI focuses on subscriptions and does not render monitored signal streams
