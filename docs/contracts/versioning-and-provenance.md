# Versions, generated contracts, and evaluation provenance

## Release and contract versions

Semantic release owns the application release number. Its preparation script
synchronizes backend `__version__.py`, frontend `package.json`, and both version
entries in `package-lock.json`. `python scripts/check_release_versions.py` checks
all four copies without application startup. Quality CI and release checks run
it. Schema and ranking-policy version changes remain explicit reviewed decisions;
parameter tuning does not automatically create a new algorithm version.

Pull requests run the Test workflow. A push to main runs Release, which calls
that same Test workflow at the caller's commit. Publication requires its backend
static checks, backend tests, PostgreSQL tests, frontend checks and browser
journeys to succeed. Only the publication job receives write permissions.
Checkout is pinned to the triggering SHA; a pre-publication guard rejects a
checkout or remote main that no longer matches the checked revision. Semantic
release then prepares the version/changelog commit. This workflow publishes a
GitHub release; deployment remains a separate operation. Local reusable workflow
references select the caller's commit, as defined by [GitHub Actions](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows).

CI jobs have 15-minute limits and publication has a 10-minute limit. A failed or
cancelled quality job prevents publication. If publication is interrupted, inspect
the remote main commit, version tag and GitHub release before retrying: remote
release effects are not rolled back automatically. The revision guard rejects an
older triggering SHA once main has advanced.

## Generated TypeScript contracts

The ranking models own current and explicitly retained historical policy/schema
IDs. `RetrievalMatchLocation` owns the current location vocabulary, and
`ScientificDomain` owns the domain IDs. Run:

```sh
python scripts/generate_search_contracts.py
python scripts/generate_search_contracts.py --check
```

The generator reads literal declarations and ranking DTO annotations with AST,
without importing configuration or composition. It writes
`frontend/src/types/searchContracts.generated.ts`: supported IDs, locations,
scientific domains and current ranking DTO types. Unsupported annotations fail
explicitly. This is scoped
generation, not a general Python-to-TypeScript compiler or generation of every API.

CI rejects stale generated output. TypeScript checks consumers of generated DTO
fields. Historical formats retain explicit readers/fixtures; unknown schemas are
shown as unsupported rather than assumed to use the old 0--100 scale. Deploy
compatible readers before new writers.

## Source identity

`APP_REVISION` is a full source Git SHA (40 or 64 lowercase hexadecimal digits).
Production requires it at startup. Docker writes the identity to `app/_image_revision.txt`;
startup configuration reads this file for API, workers, migration commands and SSH
diagnostics. A conflicting runtime `APP_REVISION` fails startup. Runtime images
contain neither `.git` nor Git.

Fly Dashboard builds derive the SHA from the checkout without additional build
arguments. The build context permits only `.git/HEAD`, `.git/refs/**` and
`.git/packed-refs`; credentials in `.git/config`, objects and logs stay excluded.
A read-only BuildKit mount exposes the filtered context only to the identity stage.
Only the resulting SHA file is copied into the runtime application package,
including the installed wheel used by API and worker entrypoints. Branch, detached-HEAD
and packed-ref checkouts are supported. The checkout must be committed and clean;
HEAD metadata alone does not prove that local source files are unmodified.

For local deployment:

```sh
python scripts/deploy_backend.py --dry-run
python scripts/deploy_backend.py
```

This helper requires a clean committed checkout, derives its SHA, and passes
`--build-arg APP_REVISION=<sha>` to Fly. It does not verify remote CI conclusions;
deploy only revisions that passed required checks. Source archives and worktrees
without usable in-context Git metadata still require the explicit build argument.
An explicit SHA conflicting with available HEAD metadata fails the build. Missing
or invalid identity also fails; it is never replaced by a placeholder.

The Test workflow builds the complete image without arguments and compares the
installed application configuration revision with the checked-out SHA. Fly Dashboard deployment remains separate
from GitHub quality gates: deploy only a revision whose checks passed. Roll back
using the prior compatible image; do not change its embedded revision. A stopped
Machine may remain stopped after deployment; verify Machine state and readiness
and explicitly start the updated Machine if necessary.

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
- `ranking_configuration`: schema version 2, ranking policy ID, all location
  weights and the Explore score threshold;
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

The JSON extension stores configuration schema 2. New scores use breakdown schema 5
and policy v4; execution schema 2 is unchanged. The separate repository-profile
schema migration and coordinated cutover are documented in backend recovery. Historical
reports can omit the extension. Restart API/workers after configuration changes;
each new scored stage records what it used.
