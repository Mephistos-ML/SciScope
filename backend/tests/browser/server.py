"""Own a disposable PostgreSQL database, API/worker processes and provider gates."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from threading import Event, Thread
from time import sleep
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[3]
API_PORT = 8011
PROVIDER_PORT = 8012


def api() -> None:
    import uvicorn
    from app.api.app import app
    from tests.browser.capabilities import dependencies

    app.state.explore_dependencies = dependencies()
    uvicorn.run(app, host="127.0.0.1", port=API_PORT)


def worker() -> None:
    from app.config import DATABASE_URL
    from app.jobs.process_search_runs import process_next_search_run_operation
    from tests.browser.capabilities import dependencies

    selected = dependencies()
    while True:
        if not process_next_search_run_operation(
            worker_id="browser-worker",
            dependencies=selected,
            database_url=DATABASE_URL,
            lease_seconds=30,
        ):
            sleep(0.1)


def serve() -> None:
    raw_url = os.environ.get("SCISCOPE_TEST_POSTGRES_URL")
    if not raw_url:
        raise RuntimeError(
            "Browser tests require SCISCOPE_TEST_POSTGRES_URL for a disposable PostgreSQL server."
        )
    url = make_url(raw_url)
    if url.drivername != "postgresql+psycopg":
        raise RuntimeError("Browser tests require postgresql+psycopg.")
    admin = create_engine(
        url,
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
        connect_args={"connect_timeout": 5},
    )
    name = f"sciscope_browser_{uuid4().hex}"
    created = False
    processes: list[subprocess.Popen] = []
    gates = {stage: Event() for stage in ("initial", "expansion")}
    entered = {stage: Event() for stage in gates}
    failures = {stage: Event() for stage in gates}
    stop = Event()
    server = None
    engine = None
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}" TEMPLATE template0'))
        created = True
        database_url = (
            url.set(database=name)
            .update_query_dict(
                {
                    "options": "-c statement_timeout=15000 -c lock_timeout=10000",
                }
            )
            .render_as_string(hide_password=False)
        )
        env = {
            **os.environ,
            "DATABASE_URL": database_url,
            "APP_ENV": "test",
            "APP_HOST": "127.0.0.1",
            "APP_PORT": str(API_PORT),
            "CORS_ORIGINS": "http://127.0.0.1:5174",
            "AI_PLANNER_MODE": "bootstrap",
            "SEMANTIC_CATALOG_ENABLED": "false",
            "TURNSTILE_ENABLED": "false",
            "GITHUB_AUTH_MODE": "disabled",
            "GITLAB_AUTH_MODE": "disabled",
            "GOOGLE_CLIENT_ID": "",
            "GOOGLE_CLIENT_SECRET": "",
            "GOOGLE_OAUTH_REDIRECT_URI": "",
            "SEARCH_DIAGNOSTICS_USER_EMAILS": "",
            "SEARCH_QUOTA_BYPASS_USER_EMAILS": "",
            "EXPLORE_GUEST_DAILY_LIMIT": "100",
            "EXPLORE_GLOBAL_DAILY_LIMIT": "100",
            "EXPLORE_GUEST_COOLDOWN_SECONDS": "1",
            "SCISCOPE_E2E_PROVIDER_URL": f"http://127.0.0.1:{PROVIDER_PORT}",
            "PYTHONPATH": str(ROOT / "backend"),
        }
        os.environ.update(env)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                "backend/alembic.ini",
                "upgrade",
                "head",
            ],
            cwd=ROOT,
            env=env,
            check=True,
            timeout=45,
        )
        engine = create_engine(database_url)

        class ProviderHandler(BaseHTTPRequestHandler):
            def reply(self, status, payload):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = urlparse(self.path)
                if path.path == "/state":
                    self.reply(
                        200, {stage: event.is_set() for stage, event in entered.items()}
                    )
                elif path.path == "/facts":
                    with engine.connect() as connection:
                        counts = {
                            table: connection.scalar(
                                text(f"SELECT count(*) FROM {table}")
                            )
                            for table in (
                                "search_runs",
                                "search_run_operations",
                                "search_run_stages",
                                "repository_subscriptions",
                            )
                        }
                        pending = connection.scalar(text(
                            "SELECT count(*) FROM search_run_operations WHERE status IN ('queued', 'running')"
                        ))
                    self.reply(200, {"counts": counts, "pendingOperations": pending})
                elif path.path == "/retrieve":
                    from tests.browser.capabilities import provider_stage

                    query = parse_qs(path.query)["query"][0]
                    stage = provider_stage(query)
                    entered[stage].set()
                    if not gates[stage].wait(20):
                        self.reply(504, {"error": "Provider gate was not released."})
                    elif failures[stage].is_set():
                        self.reply(503, {"error": "Controlled provider failure."})
                    else:
                        self.reply(200, {})
                else:
                    self.reply(404, {})

            def do_POST(self):
                stage = self.path.removeprefix("/release/")
                if self.path.startswith("/release/") and stage in gates:
                    gates[stage].set()
                    self.reply(200, {})
                elif (
                    self.path.startswith("/fail/")
                    and self.path.removeprefix("/fail/") in gates
                ):
                    stage = self.path.removeprefix("/fail/")
                    failures[stage].set()
                    gates[stage].set()
                    self.reply(200, {})
                elif self.path == "/feed/seed":
                    from tests.browser.feed import seed_feed

                    self.reply(200, seed_feed(database_url))
                elif self.path == "/reset":
                    with engine.begin() as connection:
                        pending = connection.scalar(text(
                            "SELECT count(*) FROM search_run_operations WHERE status IN ('queued', 'running')"
                        ))
                        if pending:
                            self.reply(409, {"error": "Release and drain pending operations before reset."})
                            return
                        connection.execute(text(
                            "TRUNCATE search_runs, repositories, search_access_events, users, monitoring_job_leases, monitoring_runs CASCADE"
                        ))
                    for event in (
                        *gates.values(),
                        *entered.values(),
                        *failures.values(),
                    ):
                        event.clear()
                    self.reply(200, {})
                else:
                    self.reply(404, {})

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", PROVIDER_PORT), ProviderHandler)
        Thread(target=server.serve_forever, daemon=True).start()
        for role in ("api", "worker"):
            processes.append(
                subprocess.Popen(
                    [sys.executable, "-m", "tests.browser.server", role],
                    cwd=ROOT,
                    env=env,
                )
            )
        while not stop.wait(0.1):
            if any(process.poll() is not None for process in processes):
                raise RuntimeError("Browser-test API or worker exited unexpectedly.")
    finally:
        for event in gates.values():
            event.set()
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if server:
            server.shutdown()
            server.server_close()
        if engine:
            engine.dispose()
        if created:
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


if __name__ == "__main__":
    role = sys.argv[1] if len(sys.argv) > 1 else "serve"
    {"serve": serve, "api": api, "worker": worker}[role]()
