# Browser journeys

The Chromium journey creates a guest search, checks authenticated polling,
reads results and expands the same run. It verifies retained results during
expansion, disabled pending controls and durable operation/stage counts.

The harness starts the real API and worker in separate processes, applies all
migrations to a newly created PostgreSQL database, and drops that database on
shutdown. Planner, retrieval and repository-monitor capabilities use fixed data.
Provider gates keep initial retrieval and expansion pending until the browser
has checked their loading states.

Failure tests additionally check rejected admission and expansion, failed worker
execution, polling errors and partial coverage. HTTP rejection/error tests inject
responses at the browser transport boundary; they verify client handling, not
server quota or availability policy. Worker failure and provider outage tests use
real API snapshots and PostgreSQL state. Successful journeys mock no API
responses. Feed tests create a real session and subscriptions in the disposable
database, then publish release comparisons and independent commits through the
real monitoring scan. Older closed groups exercise list pagination. They check
lazy commit loading, keyboard disclosure, mobile layout, commit/card pagination,
partial and unavailable coverage, explicit read actions, persistence after reload,
repository filters, retry feedback and stale responses during navigation.
OAuth and live provider protocols remain outside this suite; the test harness
creates sessions instead of performing Google sign-in.

Each test starts with empty run, catalog, admission, user and monitoring data. Teardown closes the
page, releases provider gates, waits for the worker to commit pending operations,
and clears data even when assertions fail. Reset rejects pending work. This keeps
failed scenarios from changing the next test;
within a test, admission waits respect the real backend cooldown.
The external font stylesheet is replaced with empty CSS to avoid network access.

Install backend development dependencies and frontend dependencies first.
Use a disposable PostgreSQL server with pgvector and a role allowed to create
databases (see [PostgreSQL test setup](../../docs/contracts/postgresql-correctness.md)).
Ports 5174, 8011 and 8012 must be free.

```sh
cd frontend
npx playwright install chromium
SCISCOPE_TEST_POSTGRES_URL=postgresql+psycopg://sciscope_test:sciscope_test@127.0.0.1:5432/postgres npm run test:e2e
```

CI installs Chromium with its system dependencies and runs the same command.
Failures retain screenshots and traces under `test-results/` and an HTML report
under `playwright-report/`; CI retains these artifacts for seven days. Traces
contain disposable guest tokens and session cookies. Open a failure trace with
`npx playwright show-trace <trace.zip>`.
