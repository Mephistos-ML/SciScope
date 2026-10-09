# Browser journeys

Playwright tests exercise Explore, subscriptions and the grouped Feed in Chromium
against the real API, worker and a disposable PostgreSQL database.

## Run locally

Prerequisites:

- Backend development dependencies installed in the repository's `.venv`;
  see [backend setup](../../backend/README.md#development-checks).
- Node.js 24, npm 11 and installed [frontend dependencies](../README.md).
- A disposable PostgreSQL server with pgvector and a role allowed to create
  databases; see [PostgreSQL test setup](../../docs/contracts/postgresql-correctness.md).
- Free ports 5174, 8011 and 8012. The harness starts its own frontend, API and worker.

From the repository root, with the test server running on port 55432 as in the
PostgreSQL setup:

```sh
cd frontend
npx playwright install chromium
SCISCOPE_TEST_POSTGRES_URL='postgresql+psycopg://sciscope_test:sciscope_test@127.0.0.1:55432/postgres' npm run test:e2e
```

Adjust the URL for your disposable server. The harness creates and migrates a new
database, then drops it on shutdown. CI installs Chromium with its system
dependencies and runs the same suite against its PostgreSQL service.

## Coverage

- **Explore:** guest search, token-authorized polling, result delivery and expansion
  of the same run; retained results, pending controls and durable operation counts.
- **Feed and subscriptions:** grouped updates, repository filters, lazy commit
  loading, card and commit pagination, keyboard disclosure and mobile layout.
- **Read state:** opening details preserves unread state; explicit card read
  actions persist after reload.
- **Failure handling:** rejected admission and expansion, failed worker execution,
  polling errors, partial and unavailable coverage, retry feedback and stale
  responses during navigation.

Feed scenarios create real sessions and subscriptions, then publish releases and
commits through the monitoring scan. Older closed groups exercise list pagination.

## Verification boundaries

Planner, retrieval and repository-monitor capabilities use fixed data. OAuth and
live provider protocols are outside this suite; the harness creates sessions
instead of performing Google sign-in.

Successful journeys mock no API responses. HTTP rejection/error scenarios inject
responses at the browser transport boundary to check client handling, not server
quota or availability policy. Worker failure and provider outage scenarios use
real API snapshots and PostgreSQL state.

## Test isolation

The API and worker run in separate processes. Provider gates hold initial
retrieval and expansion pending until the browser checks their loading states.
Each test starts with empty run, catalog, admission, user and monitoring data.

Teardown closes the page, releases provider gates, waits for pending worker
operations to commit, and clears data even when assertions fail. Reset rejects
pending work; within a test, admission waits respect the real backend cooldown.
The external font stylesheet is replaced with empty CSS to avoid network access.

## Inspect failures

Failures retain screenshots and traces under `frontend/test-results/` and an HTML
report under `frontend/playwright-report/`. CI retains these artifacts for seven
days. Traces contain disposable guest tokens and session cookies.

From `frontend/`:

```sh
npx playwright show-report
npx playwright show-trace path/to/trace.zip
```
