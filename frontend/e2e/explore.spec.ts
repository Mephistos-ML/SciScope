import type { Response } from "@playwright/test";
import { expect, test } from "./fixtures";

const api = "http://127.0.0.1:8011";
const provider = "http://127.0.0.1:8012";
const initialRepository = "science/protein-folding";
const expandedRepository = "science/molecular-docking";

async function isRunningPoll(response: Response): Promise<boolean> {
  return response.request().method() === "GET"
    && response.url().startsWith(`${api}/api/explore/search-runs/`)
    && response.status() === 200
    && (await response.json()).status === "running";
}

test("guest discovers repositories, polls and expands the same durable run", async ({ page, request }) => {
  const baseline = await (await request.get(`${provider}/facts`)).json();
  const unexpectedRequests: string[] = [];
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (url.origin === "http://127.0.0.1:5174" || url.origin === api) {
      return route.continue();
    }
    if (url.origin === "https://fonts.googleapis.com") {
      return route.fulfill({ status: 200, contentType: "text/css", body: "" });
    }
    unexpectedRequests.push(url.origin);
    return route.abort();
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Explore Scientific Software" })).toBeVisible();
  await page.getByLabel("Topic Description").fill("Scientific simulation software");
  const createdResponse = page.waitForResponse((response) => response.url() === `${api}/api/explore/search-runs`
    && response.request().method() === "POST");
  const firstRunningPoll = page.waitForResponse(isRunningPoll);
  await page.getByRole("button", { name: "Run Search", exact: true }).click();
  const creation = await createdResponse;
  expect(creation.status()).toBe(202);
  const created = await creation.json();
  expect(created.guestAccessToken).toBeTruthy();
  const firstPoll = await firstRunningPoll;
  expect(firstPoll.request().headers()["x-search-run-token"] === created.guestAccessToken).toBe(true);
  await expect(page.getByRole("button", { name: "Searching", exact: true })).toBeDisabled();
  await expect.poll(async () => (await (await request.get(`${provider}/state`)).json()).initial).toBe(true);
  // A second real pending poll proves scheduling continues, and spans the 1s guest cooldown.
  await page.waitForResponse(isRunningPoll);
  expect((await request.get(`${api}/api/explore/search-runs/${created.runId}`)).status()).toBe(404);
  expect((await request.post(`${provider}/release/initial`)).ok()).toBeTruthy();
  await expect(page.getByText(initialRepository, { exact: true })).toBeVisible();
  await expect(page.getByText("1 results", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Expand search", exact: true })).toBeEnabled();

  const expansionResponse = page.waitForResponse((response) => response.url() === `${api}/api/explore/search-runs/${created.runId}/expand`
    && response.request().method() === "POST");
  const expansionPoll = page.waitForResponse(isRunningPoll);
  await page.getByRole("button", { name: "Expand search", exact: true }).click();
  const expansion = await expansionResponse;
  expect(expansion.status()).toBe(202);
  expect(expansion.request().headers()["x-search-run-token"] === created.guestAccessToken).toBe(true);
  expect((await expansion.json()).runId).toBe(created.runId);
  await expansionPoll;
  await expect.poll(async () => (await (await request.get(`${provider}/state`)).json()).expansion).toBe(true);
  // Keep useful results visible while the next angle is still blocked at provider IO.
  await expect(page.getByText(initialRepository, { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Expand search", exact: true })).toBeDisabled();
  expect((await request.post(`${provider}/release/expansion`)).ok()).toBeTruthy();
  await expect(page.getByText(expandedRepository, { exact: true })).toBeVisible();
  await expect(page.getByText(initialRepository, { exact: true })).toBeVisible();
  await expect(page.getByText("2 results", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Expand search", exact: true })).toBeEnabled();

  const final = await request.get(`${api}/api/explore/search-runs/${created.runId}`, {
    headers: { "X-Search-Run-Token": created.guestAccessToken },
  });
  expect(final.status()).toBe(200);
  const snapshot = await final.json();
  expect(snapshot.status).toBe("completed");
  expect(snapshot.runId).toBe(created.runId);
  expect(snapshot.items.map((item: { itemId: string }) => item.itemId).sort()).toEqual(["github:repo:1", "github:repo:2"]);
  const facts = await (await request.get(`${provider}/facts`)).json();
  expect(facts.counts.search_runs - baseline.counts.search_runs).toBe(1);
  expect(facts.counts.search_run_operations - baseline.counts.search_run_operations).toBe(2);
  expect(facts.counts.search_run_stages - baseline.counts.search_run_stages).toBe(2);
  expect(facts.counts.repository_subscriptions).toBe(0);
  expect(unexpectedRequests).toEqual([]);
  expect(pageErrors).toEqual([]);
});
