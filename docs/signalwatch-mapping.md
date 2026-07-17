# SignalWatch To SciScope Mapping

## What To Reuse

### Source Contract

SignalWatch already uses a clean source protocol:

- source fetches data
- source normalizes data
- source does not decide what matters

SciScope should keep the same rule.

### Shared Domain Item

SignalWatch uses one shared domain item per source fetch. SciScope should split
this into:

- `RawSignal`
- `NormalizedSignal`

This keeps raw source payloads separate from matching-ready data.

### Matching Outside Sources

SignalWatch keeps matching outside the source adapter. SciScope should do the
same so that profile matching can evolve independently of ingestion.

### Source-Scoped Identity

SignalWatch uses `(source, item_id)` as the deduplication anchor. SciScope
should keep a source-scoped identity for raw ingestion and later build richer
cross-source linking on top.

## What Not To Reuse Directly

- CLI-first application flow
- retail-specific metadata fields
- notification-centered output
- single flat item model

## V0.1 Reuse Target

For the first GitHub-only success criterion, SciScope should reuse these ideas:

- source adapter protocol
- simple signal dataclasses
- deterministic profile matching
- seen-signal storage skeleton
