// SPDX-FileCopyrightText: 2026 Ernest Borysenko
// SPDX-License-Identifier: Apache-2.0

// Client interaction and request contracts with fixed API responses.
// The companion Explore journey checks real API/worker persistence.
import { expect, test } from "@playwright/test";
import type { ExploreSearchRequest } from "../src/types/api";
import { SCIENTIFIC_DOMAINS } from "../src/types/searchContracts.generated";

const api = "http://127.0.0.1:8011";
const selector = "Scientific domain (optional)";

test.beforeEach(async ({ page }) => {
  await page.route("https://fonts.googleapis.com/**", (route) =>
    route.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.route(`${api}/api/me`, (route) => route.fulfill({ json: { user: null } }));
});

test("domain selection is optional, matches the backend vocabulary and supports keyboard input", async ({ page }) => {
  await page.goto("/");
  const domain = page.getByRole("combobox", { name: selector });
  await expect(domain).toHaveValue("");
  expect(await domain.locator("option").evaluateAll((options) =>
    options.map((option) => (option as HTMLOptionElement).value),
  )).toEqual(["", ...SCIENTIFIC_DOMAINS]);
  await domain.focus();
  await expect(domain).toBeFocused();
  await domain.press("p");
  await domain.press("Tab");
  await expect(domain).toHaveValue("physics");
  await domain.selectOption("");
  await expect(domain).toHaveValue("");
});

for (const width of [1280, 390]) {
  test(`query fields fit the ${width}px layout`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/");
    const topic = await page.getByLabel("Topic Description").boundingBox();
    const domain = await page.getByRole("combobox", { name: selector }).boundingBox();
    expect(topic).not.toBeNull();
    expect(domain).not.toBeNull();
    if (width > 980) {
      expect(domain!.x).toBeGreaterThanOrEqual(topic!.x + topic!.width);
      expect(Math.abs(domain!.y - topic!.y)).toBeLessThan(2);
    } else {
      expect(domain!.y).toBeGreaterThan(topic!.y + topic!.height);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  });
}

test("new searches send context while expansion keeps the saved run context", async ({ page }) => {
  const createdBodies: ExploreSearchRequest[] = [];
  const expansionBodies: Record<string, unknown>[] = [];
  let completed = false;
  let savedDomain: ExploreSearchRequest["scientificDomain"] = null;
  const snapshot = () => ({
    runId: "domain-run", status: completed ? "completed" : "running",
    topicDescription: "Scientific software", scientificDomain: savedDomain,
    aiSearchPlan: { status: "ready", queries: [] }, items: [], sourceStatuses: [],
    canExpand: completed, partial: false, error: null, message: null,
    createdAt: "2026-11-20T00:00:00Z", updatedAt: "2026-11-20T00:00:01Z",
  });
  await page.route(`${api}/api/explore/search-runs`, async (route) => {
    const body = route.request().postDataJSON() as ExploreSearchRequest;
    createdBodies.push(body);
    savedDomain = body.scientificDomain;
    completed = false;
    await route.fulfill({ status: 202, json: { ...snapshot(), status: "queued", guestAccessToken: "test-token" } });
  });
  await page.route(`${api}/api/explore/search-runs/domain-run`, (route) => route.fulfill({ json: snapshot() }));
  await page.route(`${api}/api/explore/search-runs/domain-run/expand`, (route) => {
    expansionBodies.push(route.request().postDataJSON());
    return route.fulfill({ status: 202, json: snapshot() });
  });
  await page.goto("/");
  await page.getByLabel("Topic Description").fill("Scientific software");
  const domain = page.getByRole("combobox", { name: selector });
  await domain.selectOption("chemistry");
  await page.getByRole("button", { name: "Run Search", exact: true }).click();
  await expect(domain).toBeDisabled();
  await expect.poll(() => createdBodies.length).toBe(1);
  expect(createdBodies[0].scientificDomain).toBe("chemistry");
  completed = true;
  await expect(domain).toBeEnabled();
  await expect(domain).toHaveValue("chemistry");

  // Editing the next search's context must not mutate an existing run.
  await domain.selectOption("physics");
  await page.getByRole("button", { name: "Expand search", exact: true }).click();
  await expect.poll(() => expansionBodies.length).toBe(1);
  expect(expansionBodies[0]).not.toHaveProperty("scientificDomain");
  expect(savedDomain).toBe("chemistry");
  await expect(domain).toBeEnabled();
  await expect(domain).toHaveValue("physics");

  await domain.selectOption("");
  await page.getByRole("button", { name: "Run Search", exact: true }).click();
  await expect.poll(() => createdBodies.length).toBe(2);
  expect(createdBodies[1].scientificDomain).toBeNull();
});

test("rejected searches preserve the selected domain for retry", async ({ page }) => {
  await page.route(`${api}/api/explore/search-runs`, (route) =>
    route.fulfill({ status: 429, json: { error: "Please try again shortly." } }));
  await page.goto("/");
  await page.getByLabel("Topic Description").fill("Scientific software");
  const domain = page.getByRole("combobox", { name: selector });
  await domain.selectOption("earth_environmental_science");
  await page.getByRole("button", { name: "Run Search", exact: true }).click();
  await expect(page.getByText("Please try again shortly.", { exact: true })).toBeVisible();
  await expect(domain).toBeEnabled();
  await expect(domain).toHaveValue("earth_environmental_science");
});
