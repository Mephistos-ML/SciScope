# Explore browser test

The Chromium journey creates a guest search, checks authenticated polling,
reads results and expands the same run. It verifies retained results during
expansion, disabled pending controls and durable operation/stage counts.

The harness starts the real API and worker in separate processes, applies all
migrations to a newly created PostgreSQL database, and drops that database on
shutdown. Only the planner and provider retrieval capabilities use fixed data.
Provider gates keep initial retrieval and expansion pending until the browser
has checked their loading states. No application API responses are mocked.
The external font stylesheet is replaced with empty CSS to avoid network access.
Live provider protocols, OAuth and subscription flows are outside this test.

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
contain disposable guest access tokens. Open a failure trace with
`npx playwright show-trace <trace.zip>`.
