import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

// Compile the actual TypeScript module with the project's existing compiler.
const source = await readFile(new URL("../src/lib/searchRuns.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext },
});
const { pollExploreSearchRun } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);

function snapshot(status) {
  return {
    runId: "run-1",
    status,
    topicDescription: "Scientific software",
    aiSearchPlan: { status: "ready", queries: ["scientific software"] },
    items: [],
    canExpand: false,
    error: null,
    message: null,
    createdAt: "2026-10-07T10:00:00Z",
    updatedAt: "2026-10-07T10:00:01Z",
  };
}

test("polls queued and running runs until partial completion", async (t) => {
  const timers = [];
  t.mock.method(globalThis, "setTimeout", (callback) => {
    timers.push(callback);
    return timers.length;
  });
  const completed = { ...snapshot("completed_partial"), partial: true, message: "One source timed out." };
  const responses = [snapshot("queued"), snapshot("running"), completed];
  const received = [];
  const errors = [];
  let requests = 0;
  pollExploreSearchRun({
    fetchSnapshot: async () => responses[requests++],
    onSnapshot: (value) => received.push(value),
    onError: (error) => errors.push(error),
  });
  await Promise.resolve();
  assert.equal(timers.length, 1);
  timers.shift()();
  await Promise.resolve();
  assert.equal(timers.length, 1);
  timers.shift()();
  await Promise.resolve();

  assert.deepEqual(received.map((value) => value.status), ["queued", "running", "completed_partial"]);
  assert.equal(received.at(-1), completed);
  assert.equal(requests, 3);
  assert.equal(timers.length, 0);
  assert.deepEqual(errors, []);
});

for (const status of ["completed", "completed_partial", "failed", "interrupted"]) {
  test(`stops polling when the run is ${status}`, async (t) => {
    t.mock.method(globalThis, "setTimeout", () => assert.fail("Terminal runs must not schedule another poll"));
    const response = snapshot(status);
    const received = [];
    const errors = [];
    pollExploreSearchRun({
      fetchSnapshot: async () => response,
      onSnapshot: (value) => received.push(value),
      onError: (error) => errors.push(error),
    });
    await Promise.resolve();
    assert.deepEqual(received, [response]);
    assert.deepEqual(errors, []);
  });
}

test("reports request failure without scheduling another poll", async (t) => {
  t.mock.method(globalThis, "setTimeout", () => assert.fail("Failed requests must not schedule another poll"));
  const failure = new Error("API unavailable");
  const errors = [];
  pollExploreSearchRun({
    fetchSnapshot: async () => { throw failure; },
    onSnapshot: () => assert.fail("A failed request has no snapshot"),
    onError: (error) => errors.push(error),
  });
  await Promise.resolve();
  assert.deepEqual(errors, [failure]);
});

test("cleanup removes a scheduled poll and prevents stale timer work", async (t) => {
  let callback;
  t.mock.method(globalThis, "setTimeout", (value) => {
    callback = value;
    return 42;
  });
  const cleared = [];
  t.mock.method(globalThis, "clearTimeout", (value) => cleared.push(value));
  let requests = 0;
  const cancel = pollExploreSearchRun({
    fetchSnapshot: async () => { requests += 1; return snapshot("running"); },
    onSnapshot: () => {},
    onError: () => assert.fail("Cleanup must not report errors"),
  });
  await Promise.resolve();
  cancel();
  callback();
  await Promise.resolve();
  assert.deepEqual(cleared, [42]);
  assert.equal(requests, 1);
});

for (const rejects of [false, true]) {
  test(`cleanup ignores a late ${rejects ? "failure" : "response"}`, async (t) => {
    t.mock.method(globalThis, "setTimeout", () => assert.fail("Cancelled polling must not schedule work"));
    let resolve;
    let reject;
    const request = new Promise((yes, no) => { resolve = yes; reject = no; });
    const received = [];
    const errors = [];
    const cancel = pollExploreSearchRun({
      fetchSnapshot: () => request,
      onSnapshot: (value) => received.push(value),
      onError: (error) => errors.push(error),
    });
    cancel();
    if (rejects) {
      reject(new Error("Late request failure"));
    } else {
      resolve(snapshot("completed"));
    }
    await Promise.resolve();
    assert.deepEqual(received, []);
    assert.deepEqual(errors, []);
  });
}
