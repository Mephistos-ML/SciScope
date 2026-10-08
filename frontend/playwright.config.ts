import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("..", import.meta.url));
if (!process.env.SCISCOPE_TEST_POSTGRES_URL) {
  throw new Error("Browser tests require SCISCOPE_TEST_POSTGRES_URL for a disposable PostgreSQL server.");
}

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  timeout: 45_000,
  globalTimeout: 180_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5174",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "python -m tests.browser.server",
      cwd: root,
      env: { PYTHONPATH: "backend", PATH: `${path.join(root, ".venv", "bin")}${path.delimiter}${process.env.PATH}` },
      url: "http://127.0.0.1:8011/ready",
      reuseExistingServer: false,
      timeout: 60_000,
      gracefulShutdown: { signal: "SIGTERM", timeout: 15_000 },
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5174 --strictPort",
      env: { VITE_API_BASE_URL: "http://127.0.0.1:8011", VITE_TURNSTILE_SITE_KEY: "" },
      url: "http://127.0.0.1:5174",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
