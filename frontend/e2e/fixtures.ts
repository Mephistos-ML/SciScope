import { expect, test as base } from "@playwright/test";

const provider = "http://127.0.0.1:8012";

export const test = base.extend<{ isolatedBackend: void }>({
  isolatedBackend: [async ({ page, request }, use) => {
    expect((await request.post(`${provider}/reset`)).ok()).toBeTruthy();
    try {
      await use();
    } finally {
      // Stop browser actions before releasing provider IO and waiting for real worker commits.
      await page.close();
      for (const stage of ["initial", "expansion"]) {
        expect((await request.post(`${provider}/release/${stage}`)).ok()).toBeTruthy();
      }
      await expect.poll(async () => {
        const response = await request.get(`${provider}/facts`);
        expect(response.ok()).toBeTruthy();
        return (await response.json()).pendingOperations;
      }, { timeout: 15_000 }).toBe(0);
      expect((await request.post(`${provider}/reset`)).ok()).toBeTruthy();
    }
  }, { auto: true }],
});

export { expect };
