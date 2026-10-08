# Backend quality gates

`AGENTS.md` defines policy. `pyproject.toml` contains the executable import,
lint and type-checking configuration; `.github/workflows/test.yml` runs each
check in the independent `Backend architecture and static checks` job. A failed
check fails that job on pull requests and pushes to main. Requiring the job for
merges also needs GitHub branch protection; workflow configuration alone does not
configure repository permissions.

## Import boundaries

Import Linter statically checks all application modules, including relative,
function-local and type-checking imports, without starting the application.
Contracts enforce:

- domain models cannot depend on application, configuration, transport or IO;
- services cannot import transport, composition, ORM/database plumbing or concrete
  provider implementations;
- persistence cannot depend on application orchestration or external adapters;
- integrations cannot depend on orchestration, persistence or deployment config;
- HTTP modules cannot directly perform persistence or provider IO;
- ORM records are private to persistence, and session helpers are restricted to
  persistence plus the API startup boundary;
- sibling packages and modules cannot form dependency cycles, recursively.

Direct-import checks for service/database and HTTP/adapter boundaries intentionally
allow indirect reachability: a service must be able to call storage, and a route
must be able to call a service. The other forbidden contracts also check indirect
paths. `api/app.py` may import database session helpers for its documented startup
connection check; route modules may not. There are no ignored import edges.

Repository common contracts/factories remain shared with services. Concrete
provider packages are blocked. This gate does not prove that common factories
contain no provider policy, or that a permitted import performs only the intended
operations. Dynamic imports and architectural meaning still require review.

Architecture regression tests add prohibited imports and a cycle to temporary
copies of the application and require the actual CLI to reject them.

## Lint and types

Ruff checks all backend Python code: application, scripts, migrations and tests.
The initial rules (`E4`, `E9`, `F`) catch misplaced imports, syntax issues,
undefined names, unused imports/variables and duplicate definitions. This is a
correctness gate, not a repository-wide formatting rollout. There are no blanket
file exclusions or rule suppressions.

Mypy runs in strict mode over domain models, AI capabilities/helpers, retrieval
contracts, Explore dependencies and persisted execution state, and admission
models. Imported modules are analyzed with `follow_imports = "silent"`: their
types remain available, but errors outside the declared scope are not reported.
The configured gate does not claim whole-backend type safety. Extend its `files`
scope when a coherent boundary is ready; do not hide errors with broad ignores.

Retrieval, admission and ranking packages expose intentional search-stage contracts
through explicit `__all__` lists. Those entrypoints own candidate retrieval,
admission evaluation and ranking respectively; their lists are not general-purpose
exports of every helper.

## Local checks

Run from the repository root in an activated virtual environment:

```sh
python -m pip install -e '.[dev]'
PYTHONPATH=backend lint-imports --no-cache
ruff check backend
mypy
python -m pytest -q
```

The dev extra pins direct test and static-analysis tool versions, and both local
development and CI use it. Application dependencies and transitive dependencies
still use their existing version constraints; this is not a full dependency lock.
Static checks do not need provider credentials, database access or network IO.

## Tool references

- [Import Linter contracts](https://import-linter.readthedocs.io/en/stable/contract_types/)
- [Ruff configuration](https://docs.astral.sh/ruff/configuration/)
- [Mypy strict mode and import discovery](https://mypy.readthedocs.io/en/stable/command_line.html)
