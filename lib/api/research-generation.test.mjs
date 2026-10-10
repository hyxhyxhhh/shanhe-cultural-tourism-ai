import assert from "node:assert/strict";
import test from "node:test";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createRequire } from "node:module";
import ts from "typescript";

const temporaryDirectory = mkdtempSync(join(tmpdir(), "research-stream-contract-"));
for (const name of ["decimal-arithmetic", "activity-contract", "client", "research-generation"]) {
  const source = readFileSync(new URL(name === "decimal-arithmetic" ? "../decimal-arithmetic.ts" : `./${name}.ts`, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  writeFileSync(join(temporaryDirectory, `${name}.cjs`), compiled.replaceAll('require("@/lib/api/activity-contract")', 'require("./activity-contract.cjs")').replaceAll('require("@/lib/api/client")', 'require("./client.cjs")').replaceAll('require("@/lib/decimal-arithmetic")', 'require("./decimal-arithmetic.cjs")'));
}
const require = createRequire(import.meta.url);
const { parseResearchGenerationProgress, parseResearchGenerationEnvelope, checkResearchProgressTransition, consumeResearchGenerationStream } = require(join(temporaryDirectory, "research-generation.cjs"));
const { ActivityContractError } = require(join(temporaryDirectory, "activity-contract.cjs"));
const { ApiError } = require(join(temporaryDirectory, "client.cjs"));
test.after(() => rmSync(temporaryDirectory, { recursive: true, force: true }));

const activityId = "00000000-0000-4000-8000-000000000001";
const generationId = "00000000-0000-4000-8000-000000000003";
const initial = { activityId, generationId, status: "running", totalScopes: 2, completedScopes: 0, scopes: [{ scope: "weather", status: "waiting", sourceCount: 10 }, { scope: "public_trend", status: "waiting", sourceCount: 10 }] };
const snapshot = (statuses, status = "running") => ({ ...initial, status, completedScopes: statuses.filter((entry) => entry === "completed").length, scopes: initial.scopes.map((entry, index) => ({ ...entry, status: statuses[index] })) });
const failed = { ...snapshot(["completed", "failed"], "failed"), errorCode: "CCODE_TIMEOUT" };
const step = { id: "00000000-0000-4000-8000-000000000002", activityId, stepNo: 2, stepKey: "research", status: "review", inputJson: { useWebSearch: true }, outputJson: { summary: "跨范围研判摘要", findings: ["全年客流与生态活动需要协调。"], risks: [], sources: [{ sourceType: "public", label: "公开资料", url: "https://example.com", capturedAt: "2026-10-09T00:00:00+00:00", excerpt: "资料原文", rank: 0, providerRequestId: "request", scope: "weather" }] }, version: 10, confirmedAt: null, confirmedBy: null, updatedAt: "2026-10-09T00:00:00+00:00" };
const frame = (event, data) => `event: ${event}\r\ndata: ${JSON.stringify(data)}\r\n\r\n`;
function response(text, chunkSize = 7) {
  const bytes = new TextEncoder().encode(text);
  let offset = 0;
  return new Response(new ReadableStream({ pull(controller) { if (offset === bytes.length) controller.close(); else { controller.enqueue(bytes.slice(offset, offset + chunkSize)); offset = Math.min(offset + chunkSize, bytes.length); } } }), { headers: { "Content-Type": "text/event-stream; charset=utf-8" } });
}
const prefix = () => frame("research_progress", initial) + frame("research_progress", snapshot(["running", "waiting"])) + frame("research_progress", snapshot(["completed", "waiting"])) + frame("research_progress", snapshot(["completed", "running"]));

test("snapshot validates counts, canonical scope ordering and sequential state", () => {
  assert.deepEqual(parseResearchGenerationProgress(initial, activityId), initial);
  assert.deepEqual(parseResearchGenerationEnvelope({ activityId, progress: failed }, activityId), failed);
  assert.equal(parseResearchGenerationEnvelope({ activityId, progress: null }, activityId), null);
  for (const bad of [{ ...initial, legacy: true }, { ...initial, completedScopes: 1 }, { ...initial, scopes: [...initial.scopes].reverse() }, snapshot(["waiting", "running"]), snapshot(["waiting", "completed"]), { ...initial, errorCode: "SECRET" }, { ...failed, errorCode: undefined }, { ...failed, scopes: initial.scopes }]) assert.throws(() => parseResearchGenerationProgress(bad, activityId), ActivityContractError);
});
test("transition rejects completed first frame, new generation and regressions", () => {
  assert.throws(() => checkResearchProgressTransition(null, snapshot(["running", "waiting"])), ActivityContractError);
  assert.throws(() => checkResearchProgressTransition(null, snapshot(["completed", "waiting"])), ActivityContractError);
  assert.throws(() => checkResearchProgressTransition(initial, { ...initial, generationId: activityId }), ActivityContractError);
  assert.throws(() => checkResearchProgressTransition(snapshot(["completed", "waiting"]), initial), ActivityContractError);
  assert.throws(() => checkResearchProgressTransition(initial, snapshot(["completed", "waiting"])), ActivityContractError);
});
test("failure cannot have multiple failed scopes or fail after cancellation", () => {
  for (const statuses of [["failed", "failed"], ["cancelled", "failed"]]) assert.throws(() => parseResearchGenerationProgress({ ...snapshot(statuses, "failed"), errorCode: "CCODE_TIMEOUT" }, activityId), ActivityContractError);
});
test("split UTF8 and SSE boundaries deliver real progress before saved result", async () => {
  const progress = [];
  const result = await consumeResearchGenerationStream(response(prefix() + frame("research_progress", snapshot(["completed", "completed"])) + frame("research_completed", { ...snapshot(["completed", "completed"], "completed"), step }), 1), activityId, (value) => progress.push(value));
  assert.equal(result.outputJson.summary, "跨范围研判摘要");
  assert.deepEqual(progress.map((entry) => [entry.status, entry.completedScopes]), [["running", 0], ["running", 0], ["running", 1], ["running", 1], ["running", 2], ["completed", 2]]);
});
test("all groups completed still requires terminal saved-result event", async () => {
  await assert.rejects(consumeResearchGenerationStream(response(prefix() + frame("research_progress", snapshot(["completed", "completed"]))), activityId, () => {}), (error) => error instanceof ApiError && error.payload.detail.code === "GENERATION_INTERRUPTED");
});
test("domain failure remains failure with exact public code", async () => {
  const progress = [];
  await assert.rejects(consumeResearchGenerationStream(response(prefix() + frame("research_failed", failed)), activityId, (value) => progress.push(value)), (error) => error instanceof ApiError && error.payload.detail.code === "CCODE_TIMEOUT");
  assert.equal(progress.at(-1).status, "failed");
});
test("rejects mismatched activity, truncated frames, unknown event and fake terminal step", async () => {
  for (const text of [frame("research_progress", { ...initial, activityId: generationId }), frame("legacy", initial), frame("research_progress", initial).slice(0, -2), prefix() + frame("research_completed", { ...snapshot(["completed", "completed"], "completed"), step: { ...step, status: "confirmed", confirmedBy: activityId, confirmedAt: step.updatedAt } })]) {
    await assert.rejects(consumeResearchGenerationStream(response(text), activityId, () => {}), ActivityContractError);
  }
});
test("HTTP auth/domain rejection preserves server error payload", async () => {
  const payload = { detail: { code: "VERSION_CONFLICT" } };
  await assert.rejects(consumeResearchGenerationStream(Response.json(payload, { status: 409 }), activityId, () => {}), (error) => error instanceof ApiError && error.status === 409 && error.payload.detail.code === "VERSION_CONFLICT");
});
test("aborting an in-flight response never synthesizes completion", async () => {
  const aborted = new DOMException("The request was aborted", "AbortError");
  let pulls = 0;
  const seen = [];
  const stream = new ReadableStream({ pull(controller) { if (pulls++ === 0) controller.enqueue(new TextEncoder().encode(frame("research_progress", initial))); else controller.error(aborted); } });
  await assert.rejects(consumeResearchGenerationStream(new Response(stream, { headers: { "Content-Type": "text/event-stream" } }), activityId, (value) => seen.push(value)), (error) => error === aborted);
  assert.deepEqual(seen.map((entry) => entry.status), ["running"]);
  assert.equal(stream.locked, false);
});
