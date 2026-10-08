import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";

const api = "http://127.0.0.1:8011/api/explore/search-runs";
const provider = "http://127.0.0.1:8012";
let admittedAt = 0;

async function waitForAdmissionCooldown() {
  // Browser clock control does not advance the real backend admission clock.
  await expect.poll(() => Date.now() - admittedAt).toBeGreaterThanOrEqual(1000);
}

async function openExplore(page: Page, topic = "Scientific simulation software") {
  await page.route("https://fonts.googleapis.com/**", (route) =>
    route.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.goto("/");
  await page.getByLabel("Topic Description").fill(topic);
}

async function startSearch(page: Page) {
  await waitForAdmissionCooldown();
  const created = page.waitForResponse((response) => response.url() === api && response.request().method() === "POST");
  await page.getByRole("button", { name: "Run Search", exact: true }).click();
  const response = await created;
  expect(response.status()).toBe(202);
  admittedAt = Date.now();
  return response.json();
}

test.beforeEach(() => {
  admittedAt = 0;
});

test("rejected admission shows retry feedback without starting polling", async ({ page }) => {
  let polls = 0;
  page.on("request", (request) => { if (request.url().startsWith(`${api}/`) && request.method() === "GET") polls++; });
  await page.route(api, (route) => route.fulfill({ status: 429, json: {
    error: "Please wait before starting another search.", retryAfterSeconds: 60, signInSuggested: true,
  } }));
  await openExplore(page);
  await page.getByRole("button", { name: "Run Search", exact: true }).click();
  await expect(page.getByText("Please wait before starting another search.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Try Again in/ })).toBeDisabled();
  await page.clock.install();
  await page.clock.fastForward(2000);
  expect(polls).toBe(0);
  await page.clock.fastForward(60_000);
  await expect(page.getByRole("button", { name: "Run Search", exact: true })).toBeEnabled();
});

test("worker failure ends loading and allows a new search", async ({ page, request }) => {
  await openExplore(page, "Fail planning");
  const created = await startSearch(page);
  await expect(page.getByText("Explore search failed unexpectedly.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run Search", exact: true })).toBeEnabled();
  const snapshot = await request.get(`${api}/${created.runId}`, { headers: { "X-Search-Run-Token": created.guestAccessToken } });
  expect((await snapshot.json()).status).toBe("failed");
  let polls = 0;
  page.on("request", (request) => { if (request.url() === `${api}/${created.runId}`) polls++; });
  await page.clock.install();
  await page.clock.fastForward(5000);
  expect(polls).toBe(0);
  await page.getByLabel("Topic Description").fill("Scientific simulation software");
  const replacement = await startSearch(page);
  expect(replacement.runId).not.toBe(created.runId);
  await request.post(`${provider}/release/initial`);
  await expect(page.getByText("science/protein-folding", { exact: true })).toBeVisible();
});

test("polling HTTP failure stops loading without cancelling durable work", async ({ page, request }) => {
  let polls = 0;
  await page.route(`${api}/*`, (route) => {
    polls++;
    return route.fulfill({ status: 503, json: { error: "Search status is temporarily unavailable." } });
  });
  await openExplore(page);
  const created = await startSearch(page);
  await expect(page.getByText("Search status is temporarily unavailable.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run Search", exact: true })).toBeEnabled();
  await page.clock.install();
  await page.clock.fastForward(5000);
  expect(polls).toBe(1);
  await request.post(`${provider}/release/initial`);
  await expect.poll(async () => {
    const snapshot = await request.get(`${api}/${created.runId}`, { headers: { "X-Search-Run-Token": created.guestAccessToken } });
    return (await snapshot.json()).status;
  }).toBe("completed");
});

test("provider outage during expansion retains results and reports partial coverage", async ({ page, request }) => {
  await openExplore(page);
  const created = await startSearch(page);
  await request.post(`${provider}/release/initial`);
  await expect(page.getByText("science/protein-folding", { exact: true })).toBeVisible();
  await waitForAdmissionCooldown();
  await page.getByRole("button", { name: "Expand search", exact: true }).click();
  await expect.poll(async () => (await (await request.get(`${provider}/state`)).json()).expansion).toBe(true);
  await request.post(`${provider}/fail/expansion`);
  await expect(page.getByText(/Search completed with partial coverage:/)).toBeVisible();
  await expect(page.getByText("science/protein-folding", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run Search", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Expand search", exact: true })).toBeEnabled();
  const snapshot = await request.get(`${api}/${created.runId}`, { headers: { "X-Search-Run-Token": created.guestAccessToken } });
  expect((await snapshot.json()).status).toBe("completed_partial");
});


test("rejected expansion keeps results and restores controls", async ({ page, request }) => {
  await openExplore(page);
  const created = await startSearch(page);
  await request.post(`${provider}/release/initial`);
  await expect(page.getByText("science/protein-folding", { exact: true })).toBeVisible();
  const baseline = await (await request.get(`${provider}/facts`)).json();
  await page.route(`${api}/${created.runId}/expand`, (route) => route.fulfill({
    status: 503, json: { error: "Expansion is temporarily unavailable." },
  }));
  await page.getByRole("button", { name: "Expand search", exact: true }).click();
  await expect(page.getByText("Expansion is temporarily unavailable.", { exact: true })).toBeVisible();
  await expect(page.getByText("science/protein-folding", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Expand search", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Run Search", exact: true })).toBeEnabled();
  const facts = await (await request.get(`${provider}/facts`)).json();
  expect(facts.counts.search_run_operations).toBe(baseline.counts.search_run_operations);
});
