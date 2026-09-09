# AI Contract

This file is the architecture contract for future AI-assisted changes in SciScope.

The goal is simple: keep boundaries hard, imports predictable, and code easy to evolve.

## Dependency Direction

Default dependency flow:

`api -> services -> sources/storage -> database`

Shared layers:

- `models`
- `config`
- `__version__`

Special infrastructure state:

- `runtime.state`

## Package Roles

### `app/api`

Owns HTTP transport only.

Allowed:

- parse requests
- read `request.app.state`
- call application services
- shape HTTP responses
- map domain errors to HTTP errors

Must not:

- query the database directly
- import `app.storage.*`
- import `app.database.*` except app bootstrap utilities already used by the app entrypoint
- call source adapters directly
- contain business logic

### `app/services`

Owns application logic and orchestration.

Allowed:

- coordinate storage and source adapters
- enforce product rules
- transform domain objects into API payloads
- own use-case flows

Must not:

- import `app.database.records`
- open SQLAlchemy sessions
- know raw HTTP transport details unless the service is explicitly auth/session-facing
- depend on route modules

### `app/sources`

Owns external provider access and payload mapping.

Allowed:

- call GitHub/GitLab/etc APIs
- map provider payloads into app models
- raise source-specific availability/auth errors

Must not:

- import `app.api`
- import route modules
- own product ranking/business policy
- become the main orchestration layer for use cases

Preferred:

- source modules return domain objects
- orchestration lives one level above, usually in `services`

### `app/storage`

Owns persistence only.

Allowed:

- read/write the database
- map between SQLAlchemy record models and app-level records/domain objects

Must not:

- import `app.api`
- import `app.services`
- import `app.sources`
- import `app.runtime.state`
- own product logic

Rules:

- `storage` accepts explicit dependencies such as `database_url`
- no hidden config fallbacks inside storage modules

### `app/database`

Owns SQLAlchemy internals.

`app/database/records`:

- internal persistence detail
- may be imported by `storage`
- must not be imported by `api`, `services`, or `sources`

`app/database/session.py`:

- owns engine/session helpers
- may be used by `storage`
- app bootstrap may call connection checks

### `app/models`

Owns app-level data structures.

Must stay clean:

- no imports from `api`
- no imports from `services`
- no imports from `storage`
- no imports from `sources`
- no SQLAlchemy knowledge

### `app/runtime`

Owns process-local runtime state only.

Rules:

- `runtime.state` is infrastructure, not domain
- source adapters should not depend on it unless there is no better boundary
- prefer passing explicit values from orchestration instead of reading global state deep inside adapters

## Import Rules

Hard rules:

- no upward imports
- no circular imports
- no sibling package reaching into another package's internals

Examples:

- `api` may import `services`, but `services` must not import `api`
- `services` may import `storage`, but `storage` must not import `services`
- `storage` may import `database.records`, but `services` must not

## Design and Abstraction Principles

Prefer the simplest design that fully satisfies the current product requirement.

Do not add abstractions for hypothetical future consumers, providers, workflows,
or compatibility needs. Generalize only when the code already has multiple real
implementations, or when a documented extension boundary requires it.

An abstraction is justified only when it:

- represents a real domain, transport, or capability concept;
- has one clear responsibility;
- hides meaningful implementation variation;
- makes the calling code simpler than direct composition.

Do not introduce abstractions that only rename, forward, unwrap, repackage, or
preserve an obsolete internal API.

Examples of usually unjustified code:

- pass-through wrappers;
- duplicate functions that differ only by an optional return value;
- aliases that conceal rather than clarify a concept;
- interfaces with a single implementation and no defined extension boundary;
- configuration or indirection created only for imagined future flexibility.

When changing an internal API, update all internal callers in the same change.
Backward compatibility is required only for documented external contracts,
persisted data, public APIs, plugins, or independently deployed consumers.

## Dependency Inversion and Composition

Business logic must depend on stable capabilities, not concrete infrastructure
implementations.

Concrete implementations are selected at the composition boundary. Application
services must not contain implementation-selection logic for infrastructure,
transport, providers, databases, or delivery channels.

The composition boundary owns registration and wiring. Services own business
rules. Infrastructure owns implementation details.

A conditional is acceptable when it expresses a product rule. A conditional
whose purpose is to select an implementation belongs in composition.

## API and Data Contract Design

Give each concept one authoritative representation and one clear owner.

Use named data structures when multiple values form one meaningful result.
Do not use positional tuples for values with distinct semantics.

Do not leak transport, persistence, provider, or presentation details across
layers unless that detail is part of the receiving layer's explicit contract.

Do not persist presentation-only values such as labels, colours, icons, or
localized text. Persist canonical facts; derive presentation at the edge.

## Schema Migration Discipline

Treat an unmerged, undeployed migration as part of the current change, not as
immutable history. Before creating a new migration, check whether the relevant
schema change has already been merged and deployed to a shared environment.

If it has not, amend the existing migration and its tests instead of creating a
follow-on revision for the same feature. Delete any superseded local revision.
Create a new revision only when the earlier migration is already part of shared
or deployed history, where rewriting it would break an existing database path.

## Change Quality Gate

Before completing a change, review the diff and ask:

1. Is every new abstraction necessary today?
2. Would deleting an added layer make the design clearer without losing a real
   requirement?
3. Does each layer own only the decisions appropriate to that layer?
4. Did a concrete implementation leak into business logic?
5. Did the change create duplicate representations, APIs, or sources of truth?
6. Is the new code easier to remove, replace, test, and explain than the code
   it replaces?
7. Is the change the smallest cohesive solution to the requested behavior?
8. Does this schema change belong in an existing unmerged migration rather than
   a new revision?

If any answer is uncertain, simplify the design before proceeding.

## Public Surface Rule

If one package needs functionality from another package, prefer importing from that package's public surface, not from random inner modules.

Good:

- `from app.storage.repositories import upsert_repositories`

Bad:

- `from app.storage.repositories.repositories import upsert_repositories`

Use inner-module imports only when the package intentionally has no facade yet.

## Current Boundary Risks

These areas should be treated carefully in future refactors:

- `app/services/subscriptions/service.py`
  It currently uses `Signal` plus `sources.common` factories to build repository entities. Prefer a small service/domain factory instead of borrowing source-adapter construction logic.

- `app/services/search/explore.py`
  It should depend on retrieval orchestration, not on provider-specific search modules directly.

- `app/sources/*/monitor.py` and `app/sources/*/state.py`
  Keep these from growing into mixed source-plus-persistence-plus-runtime orchestration modules.

## Decision Rules For New Code

When adding code, decide in this order:

1. Is this HTTP transport?
   Then it goes to `api`.

2. Is this application policy or orchestration?
   Then it goes to `services`.

3. Is this external provider integration?
   Then it goes to `sources`.

4. Is this database persistence?
   Then it goes to `storage`.

5. Is this SQLAlchemy record/session plumbing?
   Then it goes to `database`.

6. Is this a pure data structure?
   Then it goes to `models`.

## Before Writing Code

Future AI must check:

- does this module import only downward or shared dependencies?
- am I placing logic in the shallowest correct layer?
- am I leaking SQLAlchemy outside `storage`?
- am I leaking HTTP concerns outside `api`?
- am I leaking provider-specific concerns outside `sources`?
- am I introducing a hidden global dependency instead of explicit injection?

## Override Rule

If a change must violate this contract, do not do it silently.

Document the exception in the patch summary and explain:

- why the boundary is being crossed
- why the current architecture cannot absorb the change cleanly
- what follow-up refactor would remove the exception
