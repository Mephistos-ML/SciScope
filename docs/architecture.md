# SciScope V0 Architecture

## Core Flow

`topic -> profile -> source fetch -> parse -> normalize -> store -> dashboard`

## Architectural Style

- Structured monolith
- One repository
- One application
- One database
- Background jobs for ingestion

## Stable Boundaries

### Topics

Owns user-entered research topics and generated research profiles.

### Sources

Owns source adapters and fetching logic.

### Services

Owns profile generation, ingestion orchestration, and normalization.

### Matching

Owns the logic that decides whether a normalized signal matches a research
profile. This layer starts as deterministic profile matching and can later grow
into a ranking layer.

### Storage

Owns persistence for raw signals, normalized signals, and source-scoped seen
identities.

### Models

Owns persistent domain entities.

### Jobs

Owns scheduled tasks and refresh workflows.

### Web

Owns dashboard pages and topic views.

## V0 Domain Entities

- `ResearchTopic`
- `ResearchProfile`
- `Source`
- `RawSignal`
- `NormalizedSignal`

## V0 Constraints

- pNMR-first validation
- generic engine shape
- no advanced ranking yet
- dashboard before email delivery

## Borrowed SignalWatch Patterns

- source adapters only fetch and normalize
- matching stays outside the source layer
- source-scoped stable identity prevents duplicates
- one monitoring cycle should be runnable independently of the UI
