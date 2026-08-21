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
