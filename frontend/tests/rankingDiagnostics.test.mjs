// SPDX-FileCopyrightText: 2026 Ernest Borysenko
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

// Render the actual component; type-only API imports disappear on transpilation.
const source = await readFile(new URL("../src/components/SearchDiagnosticsRepositoryDetails.tsx", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: {
    target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.React,
  },
});
const code = `import React from ${JSON.stringify(import.meta.resolve("react"))};\n${outputText}`;
const { SearchDiagnosticsRepositoryDetails } = await import(
  `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`
);

function render(scoreBreakdown, finalScore) {
  return renderToStaticMarkup(React.createElement(SearchDiagnosticsRepositoryDetails, {
    snapshot: {
      rankPosition: 1, finalScore, rankingFeatures: {}, admissionFacts: {},
      retrievalFacts: {}, scoreBreakdown,
    },
  }));
}

test("renders location counts, weights and log contributions without a percentage scale", () => {
  const html = render({
    schema_version: 2,
    formula: "location_weighted_log_matches_v1",
    locations: [{ location: "code", count: 3, weight: 0.6, points: 0.6 * Math.log(4) }],
  }, 0.6 * Math.log(4));
  assert.match(html, /Weighted log matches/);
  assert.match(html, /3 matches × weight 0.60 → 0.8318 pts/);
  assert.doesNotMatch(html, /\/ 100|Corroboration/);
});

test("renders persisted unversioned scores with their historical scale and breakdown", () => {
  const html = render({ strongest_match_points: 72.25, corroboration_points: 0 }, 72.25);
  assert.match(html, /72.25 \/ 100/);
  assert.match(html, /Strongest match/);
  assert.match(html, /72.25 pts/);
  assert.match(html, /Corroboration/);
  assert.doesNotMatch(html, /Weighted log matches/);
});

test("renders a zero-evidence snapshot explicitly", () => {
  assert.match(render({ schema_version: 2, locations: [] }, 0), /No current-query matches/);
});
