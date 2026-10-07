# SciScope Engineering Contract

This file defines the engineering requirements for changes to SciScope. It is
normative: existing code is not evidence that a design complies with these rules.
Do not weaken a rule or invent an exception to accommodate the current implementation.

The aim is to deliver a useful, reliable product whose behavior and design remain
understandable as it evolves. Apply these requirements in proportion to the
change's user impact, data risk, and operational cost.

Keep implementation maps and current system descriptions in architecture docs.
Keep existing violations and remediation plans in reviews or tracked work, not in
this contract. A task does not authorize unrelated refactoring.

## Product Behavior and Scope

- Start from the user outcome, acceptance conditions, and affected contracts.
- Identify relevant invariants, failure behavior, and resource constraints before
  choosing an implementation.
- Separate product requirements from implementation choices. Make tradeoffs
  explicit when latency, freshness, completeness, cost, or reliability compete.
- Deliver the smallest cohesive change that satisfies the requirement. Update
  affected callers, tests, and documentation together.
- Preserve unrelated behavior and user work. Report pre-existing problems
  separately unless resolving them is necessary for the requested change.

## Responsibility and Dependency Boundaries

Assign responsibilities by what the code does, independently of directory names:

- **Transport:** validate requests, establish request identity, invoke use cases,
  serialize responses, and map application failures to protocol responses.
- **Application:** coordinate use cases, authorization decisions, product policy,
  and transaction requirements through explicit capabilities.
- **Domain:** own identities, invariants, value types, and rules independent of
  frameworks, transport, providers, and persistence.
- **Integration:** perform external IO, enforce provider protocol requirements,
  and map validated external data into application contracts.
- **Persistence:** own queries, database constraints, transaction mechanics, and
  mapping between stored records and application contracts.
- **Composition:** select implementations, supply configuration and dependencies,
  and own startup, shutdown, and resource lifecycle.

Dependency rules:

- Domain code must not depend on transport, orchestration, or infrastructure.
- Application policy must not depend on route modules, ORM records or sessions,
  provider clients, or implementation-specific transport and database errors.
- Transport handlers must not perform persistence or provider operations directly.
- Adapters must not import transport handlers or application orchestration.
  They may implement capability contracts owned by their consumers.
- Composition may wire concrete adapters to application capabilities. Keep this
  wiring distinct from request handling and business policy, even when colocated.
- No circular imports or cross-boundary access to private implementation details.

A call flow and an import graph are different: calling an adapter does not require
business logic to know how that adapter works. A documented function contract can
be a sufficient capability boundary; a class or interface is not mandatory.

## Composition and Explicit Dependencies

- Select providers, databases, delivery mechanisms, and other concrete
  implementations at composition boundaries, not inside business logic.
- A conditional implementing a product rule belongs with that rule. A conditional
  choosing an infrastructure implementation belongs in composition.
- Pass capabilities and configuration explicitly. Do not discover dependencies
  through hidden globals, service locators, or fallback environment reads.
- Read and validate deployment configuration at startup or the relevant entrypoint.
  Infrastructure and application operations must not silently choose another
  dependency when a required value is absent.
- Keep process-local caches and coordination distinct from durable product state.
  State required across requests, restarts, or workers needs a documented owner,
  persistence guarantee, and recovery behavior.

## Simplicity and Abstraction

Prefer direct, readable composition that meets today's requirements.

An abstraction must name a real concept, own one responsibility, and make its
consumers simpler. Introduce it to capture an invariant, isolate a meaningful
external boundary, or unify existing variation. A capability isolating real IO can
be justified with one production implementation.

Do not add speculative frameworks, generic repositories, plugin systems, or
configuration switches for imagined consumers. Avoid wrappers, aliases, and
duplicate APIs without a present contract or responsibility, and compatibility
shims for obsolete internal callers.

- Share code when the shared behavior has one reason to change. Similar syntax
  alone does not imply a shared concept.
- Split modules by responsibility and independent reasons to change, not arbitrary
  line counts. Keep orchestration readable without chasing trivial forwarding layers.
- Prefer explicit control flow and names over cleverness. Comments explain
  invariants, constraints, and decisions that the code cannot express clearly.
- Introduce dependencies and tools for a concrete benefit, considering maintenance,
  runtime cost, and operational burden.

## Public Module Boundaries

- Define the intended cross-module contract and its owner. A public boundary may
  be a concrete module; it does not require a facade package.
- Export or re-export symbols only to establish a deliberate, documented boundary.
  Do not turn package entrypoints into convenience barrels for implementation details.
- Keep private helpers private. Consumers use the owning module's public contract,
  not its incidental imports or nested implementation modules.
- An export list describes a contract; it does not justify an otherwise unnecessary
  wrapper or make an internal API an external compatibility obligation.

## Data Ownership and Contracts

- Give each fact and invariant one authoritative owner. Avoid competing sources
  of truth and independently maintained definitions of the same contract.
- Domain types, transport DTOs, provider payloads, and persistence records may have
  separate representations when their responsibilities differ. Map between them
  explicitly; do not force one type to serve every layer.
- Use named structures for results with distinct semantic fields. Positional
  tuples are appropriate for homogeneous sequences, not implicit result schemas.
- Keep inter-module contracts typed. Restrict unstructured dictionaries and
  arbitrary metadata to explicit extension or serialization boundaries.
- Validate untrusted data at its entry boundary and preserve domain invariants
  regardless of the caller. Distinguish missing, empty, invalid, and unknown data
  when those states have different product meaning.
- Keep canonical identity separate from mutable names, URLs, and display values.
- Persist canonical facts. Derive presentation values at the presentation edge.
  Historical snapshots may preserve delivered output when required for audit or
  reproducibility; define their purpose, schema, and authority explicitly.
- Persisted JSON, queued messages, and resumable execution state are versioned
  data contracts, even if their serializer is named internal.
- State machines must define permitted transitions, terminal states, and conflict
  behavior. Apply transitions atomically where concurrent actors can race.

## Transactions, Concurrency, and Idempotency

- Application use cases define what must succeed or fail together. Persistence
  implements that boundary without exposing ORM sessions to application logic.
- Commit related product facts and their work scheduling atomically when a partial
  commit would violate an invariant. Independent repository calls are not one
  transaction merely because they share a caller.
- Enforce uniqueness and concurrency-sensitive invariants in the database or
  another authoritative coordination mechanism. A prior read or process-local
  lock alone does not protect against other workers.
- Make transaction isolation, conflict handling, and lock scope explicit where
  correctness depends on them. Keep transactions short; avoid external IO while
  holding database locks.
- Assume durable work may execute more than once. Define deduplication identity
  and make repeated effects safe. Do not claim exactly-once behavior without
  defining and demonstrating the guarantee's scope.
- A lease provides temporary ownership, not permanent exclusion. Prevent expired
  or superseded owners from committing authoritative results, using conditional
  writes, fencing, or an equivalent enforced mechanism.
- Define recovery for crashes, partial writes, lost ownership, and interrupted
  operations. Do not advance progress markers beyond durably committed work.
- When a transaction cannot span external effects, define retry, reconciliation,
  or compensation behavior; do not hide the gap behind a success response.

## External IO and Resource Budgets

- Bound network timeouts, total operation deadlines, retries, concurrency,
  pagination, batch sizes, and input/output growth where relevant.
- Propagate remaining deadlines to nested operations. Returning on timeout does
  not imply that background work has stopped; bound or cancel outstanding work.
- Retry only failures classified as transient and only when repeating the effect
  is safe. Use bounded backoff with jitter where retrying can amplify load.
- Choose an explicit retry owner. Avoid multiplying attempts across layers and
  respect provider limits and retry windows.
- Distinguish a complete empty result from unavailable or incomplete coverage.
  Preserve completed work when the product permits partial results, and surface
  completeness separately from result count.
- Treat provider and generated output as untrusted input. Validate structure,
  identity, and size before allowing it to affect durable state or privileged work.
- Keep provider-specific authentication, pagination, protocol quirks, and payload
  mapping in integration code. Eligibility, prioritization, and delivery decisions
  remain product policy.

## Errors and Observability

- Expose stable application failure categories. Translate expected infrastructure
  failures at adapter boundaries and map them to protocol responses in transport.
- Distinguish validation failures, access denial, lifecycle conflicts, dependency
  unavailability, and unexpected defects. Do not turn them all into empty results.
- Catch broad exceptions only at an intentional isolation boundary. Record the
  unexpected failure and preserve defined recovery behavior; never silently
  declare success or discard unfinished work.
- Return safe, actionable messages to users while retaining diagnostic context
  internally. Preserve causes when translating failures.
- Correlate work across request, operation, and worker boundaries. Record outcome,
  duration, retries, and relevant dependency failures with structured fields.
- Measure critical user journeys, including background completion and data
  freshness where relevant. Set reliability and latency targets from product
  needs and measurements; health checks alone do not demonstrate product health.
- Keep operational recovery instructions current for changes affecting durable
  work or deployment behavior. Avoid sensitive data and unbounded identifiers in
  metric labels.

## Access Control and Data Protection

- Authenticate at trusted entry boundaries; enforce authorization for the actual
  resource and action in every applicable use case.
- Treat identifiers, client flags, and hidden UI controls as untrusted. They are
  not proof of ownership or privilege. Background jobs need an explicit scope too.
- Preserve tenant or user ownership constraints through persistence operations.
  Never rely solely on a UI filter to prevent cross-user access.
- Define protection for state-changing requests, session/token lifecycle, and
  internal diagnostic access according to the authentication model.
- Keep secrets and bearer credentials out of logs, URLs, public responses, and
  committed artifacts. Collect and retain personal data only for a defined purpose;
  account deletion and retention must include derived and historical records as
  required by the product's documented policy.

## API and Frontend Behavior

- Define request, response, and error schemas at transport boundaries. Backend
  and client must agree on fields, status values, nullability, and failure behavior.
  Verify that agreement through generated contracts or contract checks.
- Use protocol semantics consistently, including validation, conflict responses,
  pagination, retry information, and idempotency where exposed.
- Keep server-owned policy and authorization authoritative on the server. Client
  validation and presentation may improve UX without redefining those rules.
- Separate UI rendering, interaction state, and network operations by responsibility.
  Do not require a state library or component hierarchy without a concrete need.
- Define loading, empty, partial, failure, and completion states. Handle stale
  responses, repeated actions, navigation, and cleanup of polling or requests.
- Maintain keyboard access, semantic controls, accessible names, and visible
  feedback for affected user interactions.

## Compatibility, Migrations, and Delivery

- Update internal callers together. Preserve compatibility for public APIs,
  persisted data, released integrations, and independently deployed consumers.
  Backend and frontend deployments may overlap; internal ownership alone does not
  make simultaneous rollout safe.
- Amend a migration only when it is private, unmerged, unreleased, and unapplied to
  a shared environment. Published, merged, or shared migration history is immutable.
  If its status is unknown, verify it before rewriting history.
- When a feature's migration meets those conditions, update that revision and its
  tests instead of accumulating follow-on revisions for the same unfinished change.
- Include serialized state and queued work in migration planning, not only tables.
  Define how old data is read, converted, or rejected without silent data loss.
- For incompatible changes, document deployment order and a safe staged transition
  or coordinated cutover. Do not add permanent compatibility layers by default.
- Assess locking, backfill size, restart behavior, and data preservation for schema
  and data changes. Make repair/backfill operations bounded, observable, and safe
  to resume or repeat; provide a preview when they modify existing user data.
- Release tested, identifiable artifacts through required CI gates. Keep dependency
  resolution reproducible and do not promote a revision whose required checks failed.
- Document rollback or forward-recovery behavior. Rolling back application code
  does not automatically reverse schema changes or already committed effects.

## Testing and Automated Enforcement

- Test observable behavior, invariants, and contract boundaries. Avoid assertions
  coupled only to private call order, helper names, or incidental implementation.
- Add regression coverage for meaningful bug fixes. Scale validation to risk;
  documentation edits and trivial reversible changes do not require invented tests.
- Keep tests deterministic and independent. Control clocks, randomness, and
  external IO; do not require live provider access for routine CI.
- Use real implementations when practical. Use fakes or mocks at meaningful IO
  boundaries, not as a substitute for checking that adapters honor their contracts.
- Verify database-specific behavior against the supported production database,
  especially locks, isolation, constraints, SQL features, and migrations. A different
  database or mocked repository does not prove those guarantees.
- Exercise failure and concurrent execution paths when correctness depends on
  retries, atomicity, ownership, or state transitions. Sequential calls alone do
  not establish concurrency safety.
- Cover critical user journeys with a small set of integration or end-to-end
  checks. UI builds and type checks do not prove runtime behavior.
- Changes to generated or scored product behavior need representative evaluation
  examples and an explicit quality comparison where correctness is not binary.
- Enforce stable, mechanically checkable rules in CI: formatting/linting, type and
  contract checks, dependency boundaries, and relevant tests. Coverage numbers
  support review; they are not a substitute for meaningful assertions.
- Report checks actually run and their results. Identify unverified guarantees
  clearly; do not infer correctness from a green unrelated suite.

## Review and Architecture Decisions

Before completing a change, verify:

1. Does it satisfy the user outcome and preserve the relevant invariants?
2. Does each responsibility have a clear owner and dependency boundary?
3. Is every added abstraction necessary, and can any layer be removed cleanly?
4. Are contracts, identities, and durable state authoritative and consistent?
5. Are concurrent execution, partial failure, retries, and resource limits handled?
6. Are authorization, data protection, and affected UI behavior preserved?
7. Can the change be deployed and recovered without violating compatibility?
8. Do the validation results support the claimed guarantees?
9. Are affected documentation and operational instructions current?

Record significant boundary or contract decisions with the requirement,
alternatives, tradeoffs, and consequences. Routine local choices do not require a
separate architecture decision document.

If an exception is necessary, state the rule, reason, scope, consequences, and
removal condition in the patch summary and a durable decision record when the
exception will outlive the change. Existing violations do not grant new ones.

## Practice References

These public references inform the contract; the rules above are repository
policy, not a claim of a universal company standard:

- [Google Engineering Practices: what to look for in code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
- [Software Engineering at Google: testing overview](https://abseil.io/resources/swe-book/html/ch11.html)
- [Google SRE: addressing cascading failures](https://sre.google/sre-book/addressing-cascading-failures/)
- [Google SRE Workbook: implementing SLOs](https://sre.google/workbook/implementing-slos/)
- [Amazon Builders' Library: making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
