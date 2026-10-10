import assert from "node:assert/strict";
import test from "node:test";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createRequire } from "node:module";
import ts from "typescript";
const testDirectory = mkdtempSync(join(tmpdir(), "activity-contract-"));
for (const name of ["decimal-arithmetic", "activity-contract"]) {
 const source = readFileSync(new URL(name === "decimal-arithmetic" ? "../decimal-arithmetic.ts" : "./activity-contract.ts", import.meta.url), "utf8");
 const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText.replaceAll('require("@/lib/decimal-arithmetic")', 'require("./decimal-arithmetic.cjs")');
 writeFileSync(join(testDirectory, `${name}.cjs`), compiled);
}
const contract = createRequire(import.meta.url)(join(testDirectory, "activity-contract.cjs"));
test.after(() => rmSync(testDirectory, { recursive: true, force: true }));
const { ActivityContractError, parseActivityStep, parseResearchSourceReference } = contract;

const publicSource = {
  sourceType: "public",
  label: "武汉市人民政府活动信息",
  url: "https://www.wuhan.gov.cn/example",
  capturedAt: "2026-09-24T06:59:21+00:00",
  excerpt: "公开活动信息摘要",
  publishedAt: "2026-09-20",
  siteName: "武汉市人民政府",
  authorityLevel: "high",
  rank: 0,
  providerRequestId: "2026092414592122F77DC0C034B41C89EC",
  scope: "similar_events"
};

function researchStep(source = publicSource) {
  return {
    id: "00000000-0000-4000-8000-000000000002",
    activityId: "00000000-0000-4000-8000-000000000001",
    stepNo: 2,
    stepKey: "research",
    status: "review",
    inputJson: { useWebSearch: true },
    outputJson: {
      summary: "已完成联网搜索。",
      findings: ["发现一"],
      sources: [source],
      risks: []
    },
    version: 2,
    confirmedBy: null,
    confirmedAt: null,
    updatedAt: "2026-09-24T07:00:00+00:00"
  };
}

test("canonical step 2 accepts persisted public-search metadata", () => {
  const parsed = parseActivityStep(researchStep());
  assert.deepEqual(parsed.outputJson.sources, [publicSource]);
});

test("research POST and activity GET share the strict source-reference parser", () => {
  assert.deepEqual(
    parseResearchSourceReference(publicSource, "source", { requireSearchMetadata: true }),
    publicSource
  );
});

for (const field of ["rank", "providerRequestId", "scope"]) {
  test(`research POST source reference requires ${field}`, () => {
    const source = { ...publicSource };
    delete source[field];
    assert.throws(
      () => parseResearchSourceReference(source, "source", { requireSearchMetadata: true }),
      (error) => error instanceof ActivityContractError && /public search metadata is incomplete/.test(error.message)
    );
  });
}

for (const [label, source, pattern] of [
  ["unknown fields", { ...publicSource, legacyAuthority: "high" }, /contains unknown field/],
  ["invalid authority", { ...publicSource, authorityLevel: "official" }, /authorityLevel is invalid/],
  ["invalid scope", { ...publicSource, scope: "traffic" }, /scope is invalid/],
  ["explicit null", { ...publicSource, siteName: null }, /siteName must be a non-empty string/],
  ["non-HTTP URL", { ...publicSource, url: "ftp://example.com/source" }, /valid HTTP\(S\) URL/],
  ["invalid rank", { ...publicSource, rank: -1 }, /rank must be an integer >= 0/],
  [
    "calculated source without reasoning",
    { sourceType: "calculated", label: "测算结果" },
    /calculated source reasoning is required/
  ]
]) {
  test(`source reference rejects ${label}`, () => {
    assert.throws(
      () => parseResearchSourceReference(source, "source"),
      (error) => error instanceof ActivityContractError && pattern.test(error.message)
    );
  });
}
