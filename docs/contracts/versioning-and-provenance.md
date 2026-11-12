# Versions, generated contracts, and evaluation provenance

## Release and contract versions

Semantic release owns the application release number. Its preparation script
synchronizes backend `__version__.py`, frontend `package.json`, and both version
entries in `package-lock.json`. `python scripts/check_release_versions.py` checks
all four copies without application startup. Quality CI and release checks run
it. Schema and ranking-policy version changes remain explicit reviewed decisions;
parameter tuning does not automatically create a new algorithm version.

The Test and Release workflows still trigger independently. These consistency
checks do not establish that every other CI job passed before publication.
Complete cross-workflow release gating is separate delivery work.

## Generated TypeScript contracts

The ranking models own current and explicitly retained historical policy/schema
IDs. `RetrievalMatchLocation` owns the current vocabulary. Run:

```sh
python scripts/generate_search_contracts.py
python scripts/generate_search_contracts.py --check
```

The generator reads literal declarations and ranking DTO annotations with AST,
without importing configuration or composition. It writes
`frontend/src/types/searchContracts.generated.ts`: supported IDs, locations, and
current ranking DTO types. Unsupported annotations fail explicitly. This is scoped
generation, not a general Python-to-TypeScript compiler or generation of every API.

CI rejects stale generated output. TypeScript checks consumers of generated DTO
fields. Historical formats retain explicit readers/fixtures; unknown schemas are
shown as unsupported rather than assumed to use the old 0--100 scale. Deploy
compatible readers before new writers.

## Source identity

`APP_REVISION` is a full source Git SHA (40 or 64 lowercase hexadecimal digits).
Production requires it at startup. Docker requires it as a build argument and
embeds it in the image environment; runtime images do not need `.git` or Git.
For the existing Fly deployment:

```sh
python scripts/deploy_backend.py --dry-run
python scripts/deploy_backend.py
```

This helper requires a clean committed checkout, derives its SHA, and passes
`--build-arg APP_REVISION=<sha>` to Fly. It does not verify remote CI conclusions;
deploy only revisions that passed required checks. Direct builds need the same
argument. Do not override the embedded identity with an unrelated runtime value.

Development composition resolves Git once at startup when no artifact identity
is supplied. Dirty tracked/untracked source is marked `<sha>-dirty`. A source
archive without Git is explicitly `unavailable`, not an identifiable research
artifact. Application use cases receive this value through Explore dependencies
and perform no Git commands or environment discovery.

Run creation records the API revision in the existing `backend_revision` column.
Each scored stage's candidate snapshots also record the actual worker revision,
which can differ after deployment. Historical `unknown` values are preserved.

## Ranking configuration fingerprint

`explore/provenance.py` owns the versioned `evaluation_provenance` extension in
ranking snapshot `candidateFacts`. It contains:

- `backend_revision`: the worker's source identity;
- `ranking_configuration`: schema version 1, ranking policy ID, all location
  weights, popularity cap/reference, and the Explore score threshold;
- `configuration_fingerprint`: `sha256:<hex>` of that configuration.

Canonical encoding is UTF-8 JSON with sorted keys, no whitespace, finite numbers,
fixed numeric representations, and normalized zero. Fingerprints are independent
of dictionary order and code revision. Parameters remain stored alongside the
hash; a hash alone cannot reconstruct an experiment.

This identifies ranking/visibility parameters, not an entire search or dataset.
Data revisions, query partitions, provider budgets, clocks, seeds, and lockfiles
still belong in the study manifest. A new source SHA with the same parameter hash
is a different artifact. Matching fingerprints do not prove equivalent execution.

Metadata is stored for candidates actually scored. Empty/planning-only runs have
no ranking candidate snapshot: their creation revision exists, but a research
runner must save the configuration independently before executing an experiment.

The existing JSON extension stores this metadata. Scores, breakdown schema 4, and
execution schema 2 are unchanged. No table migration/backfill is needed. Historical
reports can omit the extension. Restart API/workers after configuration changes;
each new scored stage records what it used.
