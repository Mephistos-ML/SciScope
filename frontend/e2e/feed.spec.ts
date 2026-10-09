import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";

const provider = "http://127.0.0.1:8012";
const api = "http://127.0.0.1:8011";

async function openFeed(page: Page) {
  await page.route("https://fonts.googleapis.com/**", (route) => route.fulfill({ contentType: "text/css", body: "" }));
  const response = await page.request.post(`${provider}/feed/seed`);
  expect(response.ok()).toBeTruthy();
  const identity = await response.json();
  await page.context().addCookies([{
    name: identity.cookieName, value: identity.sessionToken, domain: "127.0.0.1",
    path: "/", httpOnly: true, sameSite: "Lax", secure: false,
  }]);
  await page.goto("/feed");
  await expect(page.getByLabel("24 unread feed updates", { exact: true })).toBeVisible();
  await expect(page.getByRole("article", { name: "v2.0", exact: true })).toBeVisible();
  return identity;
}

test("grouped updates page commits, preserve read state on opening, and mark whole cards read", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const detailRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().startsWith(`${api}/api/feed/groups/`)) detailRequests.push(request.method());
  });
  await openFeed(page);
  const saved = await (await page.request.get(`${api}/api/subscriptions`)).json();
  expect(saved.items.map((item: { unreadGroupCount: number }) => item.unreadGroupCount).sort((a: number, b: number) => a - b)).toEqual([4, 20]);
  expect(detailRequests).toEqual([]); // Listing cards does not fetch their commit contents.
  await expect(page.getByText("20 updates", { exact: true })).toBeVisible();
  const release = page.getByRole("article", { name: "v2.0", exact: true });
  const toggle = release.getByRole("button", { name: "Commits (23)", exact: true });
  await toggle.focus();
  await page.keyboard.press("Space");
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  const commits = release.getByRole("region", { name: "Commits for v2.0", exact: true });
  await expect(commits.getByRole("listitem")).toHaveCount(10);
  await expect(commits.getByRole("link", { name: "Release commit 22", exact: true })).toHaveAttribute(
    "href", /^https:\/\/github\.com\/science\/tool\/commit\/[0-9a-f]{40}$/,
  );
  await expect(commits.getByText("Improve numerical accuracy and simulation reproducibility.", { exact: true })).toHaveCount(10);
  await page.setViewportSize({ width: 390, height: 844 });
  await release.scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.setViewportSize({ width: 1280, height: 720 });
  await expect(page.getByLabel("24 unread feed updates", { exact: true })).toBeVisible();
  await commits.getByRole("button", { name: "Load more commits", exact: true }).click();
  await expect(commits.getByRole("listitem")).toHaveCount(20);
  await commits.getByRole("button", { name: "Load more commits", exact: true }).click();
  await expect(commits.getByRole("listitem")).toHaveCount(23);
  await expect(commits.getByRole("button", { name: "Load more commits", exact: true })).toHaveCount(0);
  const links = await commits.getByRole("listitem").getByRole("link").evaluateAll((items) => items.map((item) => item.getAttribute("href")));
  expect(new Set(links).size).toBe(23);
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(commits).toBeHidden();
  await toggle.click();
  await expect(commits.getByRole("listitem")).toHaveCount(23);
  expect(detailRequests).toEqual(["GET", "GET", "GET"]);

  await page.getByRole("button", { name: "Load older updates", exact: true }).click();
  await expect(page.getByText("24 updates", { exact: true })).toBeVisible();
  await release.getByRole("button", { name: "Mark v2.0 read", exact: true }).click();
  await expect(release.getByText("Read", { exact: true })).toBeVisible();
  await expect(page.getByText("24 updates", { exact: true })).toBeVisible();
  await expect(commits.getByRole("listitem")).toHaveCount(23);
  await expect(page.getByLabel("23 unread feed updates", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("article", { name: "v2.0", exact: true }).getByText("Read", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Unread (23)", exact: true }).click();
  await expect(page.getByRole("article", { name: "v2.0", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Load older updates", exact: true }).click();
  await expect(page.getByText("23 updates", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Mark all read", exact: true }).click();
  await expect(page.getByText("No unread updates.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Mark all read", exact: true })).toBeDisabled();
  await page.reload();
  await expect(page.getByRole("button", { name: "Mark all read", exact: true })).toBeDisabled();
  expect((await (await page.request.get(`${api}/api/feed/groups`)).json()).unreadCount).toBe(0);
  expect(errors).toEqual([]);
});

test("partial and unavailable release coverage stays useful and subscription filters survive read actions", async ({ page }) => {
  const identity = await openFeed(page);
  const partial = page.getByRole("article", { name: "v1.5", exact: true });
  await partial.getByRole("button", { name: "Commits (2)", exact: true }).click();
  await expect(partial.getByText("2 of 5 commits available for this release. View the release for the full context.", { exact: true })).toBeVisible();
  await expect(partial.getByRole("listitem")).toHaveCount(2);
  await expect(partial.getByRole("button", { name: "Load more commits", exact: true })).toHaveCount(0);
  const unknown = page.getByRole("article", { name: "v1.0", exact: true });
  await unknown.getByRole("button", { name: "Commits", exact: true }).click();
  await expect(unknown.getByText("Commit details are unavailable. View the release on GitHub for more information.", { exact: true })).toBeVisible();
  await expect(unknown.getByRole("link", { name: "v1.0", exact: true })).toHaveAttribute("href", "https://github.com/science/tool/releases/tag/v1.0");
  await expect(unknown.getByRole("button", { name: "Commits (0)", exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "Subscriptions", exact: true }).click();
  await page.getByRole("button", { name: /science\/tool simulation github/ }).click();
  await expect(page.getByText("4 updates", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "View all updates", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Repository Updates", exact: true })).toBeVisible();
  await expect(page.getByText("4 updates", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Unread (24)", exact: true }).click();
  await expect(page.getByText("4 updates", { exact: true })).toBeVisible();
  const batch = page.getByRole("article", { name: "Repository updates", exact: true });
  await batch.getByRole("button", { name: "Commits (2)", exact: true }).click();
  await expect(batch.getByRole("listitem")).toHaveCount(2);
  await expect(batch.getByText("Independent commit 1", { exact: true })).toBeVisible();
  await batch.getByRole("button", { name: "Mark Repository updates read", exact: true }).click();
  await expect(page.getByText("3 updates", { exact: true })).toBeVisible();
  await expect(page.getByLabel("23 unread feed updates", { exact: true })).toBeVisible();
  const scoped = await (await page.request.get(`${api}/api/feed/groups?state=unread&subscription_id=${identity.subscriptionId}`)).json();
  expect(scoped.items).toHaveLength(3);
  expect(scoped.items.every((item: { subscriptionId: string }) => item.subscriptionId === identity.subscriptionId)).toBe(true);
  await page.getByRole("button", { name: "Subscriptions", exact: true }).click();
  await page.getByRole("button", { name: /Feed 23/ }).click();
  await expect(page.getByRole("heading", { name: "Recent Repository Updates", exact: true })).toBeVisible();
  await expect(page.getByText("20 updates", { exact: true })).toBeVisible();
});

test("commit and read failures can be retried without losing loaded facts or falsely marking a card read", async ({ page }) => {
  await openFeed(page);
  const release = page.getByRole("article", { name: "v2.0", exact: true });
  let failDetails = true;
  await page.route(`${api}/api/feed/groups/*`, async (route) => {
    if (route.request().method() === "GET" && failDetails) {
      failDetails = false;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ error: "Commit details temporarily unavailable." }) });
    } else if (route.request().method() === "PATCH") {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ error: "Read update temporarily unavailable." }) });
    } else await route.continue();
  });
  await release.getByRole("button", { name: "Commits (23)", exact: true }).click();
  await expect(release.getByRole("alert")).toHaveText("Commit details temporarily unavailable.");
  await release.getByRole("button", { name: "Retry commits", exact: true }).click();
  await expect(release.getByRole("listitem")).toHaveCount(10);
  failDetails = true;
  await release.getByRole("button", { name: "Load more commits", exact: true }).click();
  await expect(release.getByRole("listitem")).toHaveCount(10);
  await expect(release.getByRole("alert")).toBeVisible();
  await release.getByRole("button", { name: "Retry commits", exact: true }).click();
  await expect(release.getByRole("listitem")).toHaveCount(20);
  await release.getByRole("button", { name: "Mark v2.0 read", exact: true }).click();
  await expect(page.getByText("Read update temporarily unavailable.", { exact: true })).toBeVisible();
  await expect(release.getByRole("button", { name: "Mark v2.0 read", exact: true })).toBeEnabled();
  await expect(page.getByLabel("24 unread feed updates", { exact: true })).toBeVisible();
  await page.unroute(`${api}/api/feed/groups/*`);
  await release.getByRole("button", { name: "Mark v2.0 read", exact: true }).click();
  await expect(page.getByLabel("23 unread feed updates", { exact: true })).toBeVisible();
  await expect(release.getByRole("listitem")).toHaveCount(20);
});

test("a late global filter response cannot replace a newly selected repository feed", async ({ page }) => {
  await openFeed(page);
  let releaseResponse!: () => void;
  const gate = new Promise<void>((resolve) => { releaseResponse = resolve; });
  let captured!: () => void;
  const responseCaptured = new Promise<void>((resolve) => { captured = resolve; });
  await page.route(`${api}/api/feed/groups?*`, async (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get("state") === "unread" && !url.searchParams.has("subscription_id")) {
      const response = await route.fetch();
      captured();
      await gate;
      await route.fulfill({ response });
    } else await route.continue();
  });
  try {
    await page.getByRole("button", { name: "Unread (24)", exact: true }).click();
    await responseCaptured;
    await page.getByRole("button", { name: "Subscriptions", exact: true }).click();
    await page.getByRole("button", { name: /science\/tool simulation github/ }).click();
    await page.getByRole("button", { name: "View all updates", exact: true }).click();
    await expect(page.getByText("4 updates", { exact: true })).toBeVisible();
    const lateResponse = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === "/api/feed/groups" && url.searchParams.get("state") === "unread" && !url.searchParams.has("subscription_id");
    });
    releaseResponse();
    await lateResponse;
    await expect(page.getByText("4 updates", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Repository Updates", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "All", exact: true })).toHaveAttribute("aria-pressed", "true");
  } finally {
    releaseResponse();
  }
});

test("navigation during a read cannot restore a pre-read list or double-decrement the badge", async ({ page }) => {
  await openFeed(page);
  await page.getByRole("button", { name: "Subscriptions", exact: true }).click();
  await page.getByRole("button", { name: /science\/tool simulation github/ }).click();
  await page.getByRole("button", { name: "View all updates", exact: true }).click();
  await expect(page.getByText("4 updates", { exact: true })).toBeVisible();
  let releaseRead!: () => void;
  const readGate = new Promise<void>((resolve) => { releaseRead = resolve; });
  let readStarted!: () => void;
  const reading = new Promise<void>((resolve) => { readStarted = resolve; });
  let releaseList!: () => void;
  const listGate = new Promise<void>((resolve) => { releaseList = resolve; });
  let listCaptured!: () => void;
  const captured = new Promise<void>((resolve) => { listCaptured = resolve; });
  let heldList = false;
  await page.route(`${api}/api/feed/groups**`, async (route) => {
    if (route.request().method() === "PATCH") {
      readStarted();
      await readGate;
      await route.continue();
    } else {
      const url = new URL(route.request().url());
      if (!heldList && url.pathname === "/api/feed/groups" && url.searchParams.get("limit") === "20" && !url.searchParams.has("subscription_id")) {
        heldList = true;
        const response = await route.fetch();
        listCaptured();
        await listGate;
        await route.fulfill({ response });
      } else await route.continue();
    }
  });
  try {
    await page.getByRole("button", { name: "Mark v2.0 read", exact: true }).click();
    await reading;
    await page.getByRole("button", { name: "Subscriptions", exact: true }).click();
    await captured;
    releaseRead();
    await expect(page.getByLabel("23 unread feed updates", { exact: true })).toBeVisible();
    releaseList();
    await page.getByRole("button", { name: /Feed 23/ }).click();
    await expect(page.getByRole("heading", { name: "Recent Repository Updates", exact: true })).toBeVisible();
    await expect(page.getByRole("article", { name: "v2.0", exact: true }).getByText("Read", { exact: true })).toBeVisible();
    await expect(page.getByLabel("23 unread feed updates", { exact: true })).toBeVisible();
  } finally {
    releaseRead();
    releaseList();
  }
});

test("a late subscription feed response cannot override newer navigation", async ({ page }) => {
  await openFeed(page);
  await page.getByRole("button", { name: "Subscriptions", exact: true }).click();
  await page.getByRole("button", { name: /science\/tool simulation github/ }).click();
  await expect(page.getByText("4 updates", { exact: true })).toBeVisible();
  let releaseResponse!: () => void;
  const gate = new Promise<void>((resolve) => { releaseResponse = resolve; });
  let captured!: () => void;
  const responseCaptured = new Promise<void>((resolve) => { captured = resolve; });
  await page.route(`${api}/api/feed/groups?*`, async (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get("limit") === "20" && url.searchParams.has("subscription_id")) {
      const response = await route.fetch();
      captured();
      await gate;
      await route.fulfill({ response });
    } else await route.continue();
  });
  try {
    await page.getByRole("button", { name: "View all updates", exact: true }).click();
    await responseCaptured;
    await page.getByRole("button", { name: "Explore", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Explore Scientific Software", exact: true })).toBeVisible();
    const lateResponse = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === "/api/feed/groups" && url.searchParams.get("limit") === "20" && url.searchParams.has("subscription_id");
    });
    releaseResponse();
    await lateResponse;
    await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    await expect(page).toHaveURL("/");
    await expect(page.getByRole("heading", { name: "Explore Scientific Software", exact: true })).toBeVisible();
    // A subsequent Feed visit also retains global scope rather than the discarded request's scope.
    await page.getByRole("button", { name: /Feed 24/ }).click();
    await expect(page.getByRole("heading", { name: "Recent Repository Updates", exact: true })).toBeVisible();
    await expect(page.getByText("20 updates", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Explore", exact: true }).click();
    await expect(page).toHaveURL("/");
  } finally {
    releaseResponse();
  }
});
