import assert from "node:assert/strict";
import test from "node:test";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createRequire } from "node:module";
import ts from "typescript";

const temporaryDirectory = mkdtempSync(join(tmpdir(), "planning-stream-contract-"));
for (const name of ["decimal-arithmetic", "activity-contract", "client", "planning-generation"]) {
  const source = readFileSync(new URL(name === "decimal-arithmetic" ? "../decimal-arithmetic.ts" : `./${name}.ts`, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  writeFileSync(join(temporaryDirectory, `${name}.cjs`), compiled.replaceAll('require("@/lib/api/activity-contract")', 'require("./activity-contract.cjs")').replaceAll('require("@/lib/api/client")', 'require("./client.cjs")').replaceAll('require("@/lib/decimal-arithmetic")', 'require("./decimal-arithmetic.cjs")'));
}
const require = createRequire(import.meta.url);
const { parsePlanningGenerationProgress, parsePlanningGenerationEnvelope, checkPlanningProgressTransition, consumePlanningGenerationStream } = require(join(temporaryDirectory, "planning-generation.cjs"));
const { ActivityContractError } = require(join(temporaryDirectory, "activity-contract.cjs"));
const { ApiError } = require(join(temporaryDirectory, "client.cjs"));
test.after(() => rmSync(temporaryDirectory, { recursive: true, force: true }));

const activityId = "00000000-0000-4000-8000-000000000001";
const generationId = "00000000-0000-4000-8000-000000000003";
const initial = { activityId, generationId, stepNo: 2, status: "running", totalUnits: 2, completedUnits: 0, units: [{ key: "annual", status: "waiting", label: "年度统筹" }, { key: "event-1", status: "waiting", label: "活动简案 1" }] };
const snapshot = (statuses, status = "running") => ({ ...initial, status, completedUnits: statuses.filter((entry) => entry === "completed").length, units: initial.units.map((entry, index) => ({ ...entry, status: statuses[index] })) });
const failed = { ...snapshot(["completed", "failed"], "failed"), errorCode: "CCODE_TIMEOUT" };
const step = { id: "00000000-0000-4000-8000-000000000002", activityId, stepNo: 2, stepKey: "research", status: "review", inputJson: { useWebSearch: true }, outputJson: { summary: "跨范围研判摘要", findings: ["全年客流与生态活动需要协调。"], risks: [], sources: [{ sourceType: "public", label: "公开资料", url: "https://example.com", capturedAt: "2026-10-09T00:00:00+00:00", excerpt: "资料原文", rank: 0, providerRequestId: "request", scope: "weather" }] }, version: 10, confirmedAt: null, confirmedBy: null, updatedAt: "2026-10-09T00:00:00+00:00" };
const frame = (event, data) => `event: ${event}\r\ndata: ${JSON.stringify(data)}\r\n\r\n`;
function response(text, chunkSize = 7) {
  const bytes = new TextEncoder().encode(text);
  let offset = 0;
  return new Response(new ReadableStream({ pull(controller) { if (offset === bytes.length) controller.close(); else { controller.enqueue(bytes.slice(offset, offset + chunkSize)); offset = Math.min(offset + chunkSize, bytes.length); } } }), { headers: { "Content-Type": "text/event-stream; charset=utf-8" } });
}
const prefix = () => frame("planning_progress", initial) + frame("planning_progress", snapshot(["running", "waiting"])) + frame("planning_progress", snapshot(["completed", "waiting"])) + frame("planning_progress", snapshot(["completed", "running"]));

test("snapshot validates counts, annual-first ordering and sequential state", () => {
  assert.deepEqual(parsePlanningGenerationProgress(initial, activityId, 2), initial);
  assert.deepEqual(parsePlanningGenerationEnvelope({ activityId, stepNo: 2, progress: failed }, activityId, 2), failed);
  assert.equal(parsePlanningGenerationEnvelope({ activityId, stepNo: 2, progress: null }, activityId, 2), null);
  for (const bad of [{ ...initial, legacy: true }, { ...initial, completedUnits: 1 }, { ...initial, units: [...initial.units].reverse() }, snapshot(["waiting", "running"]), snapshot(["waiting", "completed"]), { ...initial, errorCode: "SECRET" }, { ...failed, errorCode: undefined }, { ...failed, units: initial.units }]) assert.throws(() => parsePlanningGenerationProgress(bad, activityId, 2), ActivityContractError);
});
test("transition rejects completed first frame, new generation and regressions", () => {
  assert.throws(() => checkPlanningProgressTransition(null, snapshot(["running", "waiting"])), ActivityContractError);
  assert.throws(() => checkPlanningProgressTransition(null, snapshot(["completed", "waiting"])), ActivityContractError);
  assert.throws(() => checkPlanningProgressTransition(initial, { ...initial, generationId: activityId }), ActivityContractError);
  assert.throws(() => checkPlanningProgressTransition(snapshot(["completed", "waiting"]), initial), ActivityContractError);
  assert.throws(() => checkPlanningProgressTransition(initial, snapshot(["completed", "waiting"])), ActivityContractError);
});
test("single planning and annual event units preserve the backend unit identities", () => {
  const single = { ...initial, stepNo: 1, totalUnits: 1, units: [{ key: "single", label: "活动方案", status: "waiting" }] };
  assert.deepEqual(parsePlanningGenerationProgress(single, activityId, 1), single);
  const annual3 = { ...initial, stepNo: 3, totalUnits: 3, units: [
    { key: "annual", label: "年度架构", status: "waiting" },
    { key: "event-1", label: "活动简案 1", status: "waiting" },
    { key: "event-2", label: "活动简案 2", status: "waiting" }
  ] };
  assert.deepEqual(parsePlanningGenerationProgress(annual3, activityId, 3), annual3);
  const annual4 = { ...annual3, stepNo: 4, units: [
    { key: "annual", label: "年度统筹", status: "waiting" },
    { key: "spring_nature", label: "春季自然课堂", status: "waiting" },
    { key: "autumn_walk", label: "秋季自然漫步", status: "waiting" }
  ] };
  assert.deepEqual(parsePlanningGenerationProgress(annual4, activityId, 4), annual4);
  assert.throws(() => parsePlanningGenerationProgress(annual4, activityId, 3), ActivityContractError);
  assert.throws(() => parsePlanningGenerationProgress({ ...annual4, units: [annual4.units[0], annual4.units[1], annual4.units[1]] }, activityId, 4), ActivityContractError);
});
test("failure is a single failed unit followed only by cancelled units", () => {
  for (const statuses of [["failed", "failed"], ["cancelled", "failed"]]) assert.throws(() => parsePlanningGenerationProgress({ ...snapshot(statuses, "failed"), errorCode: "CCODE_TIMEOUT" }, activityId, 2), ActivityContractError);
  const single = { ...initial, totalUnits: 1, units: [{ key: "single", label: "活动简报", status: "waiting" }] };
  assert.equal(parsePlanningGenerationProgress(single, activityId, 2).totalUnits, 1);
});
test("split UTF8 and SSE boundaries deliver real progress before saved result", async () => {
  const progress = [];
  const result = await consumePlanningGenerationStream(response(prefix() + frame("planning_progress", snapshot(["completed", "completed"])) + frame("planning_completed", { ...snapshot(["completed", "completed"], "completed"), step }), 1), activityId, 2, (value) => progress.push(value));
  assert.equal(result.outputJson.summary, "跨范围研判摘要");
  assert.deepEqual(progress.map((entry) => [entry.status, entry.completedUnits]), [["running", 0], ["running", 0], ["running", 1], ["running", 1], ["running", 2], ["completed", 2]]);
});
test("all groups completed still requires terminal saved-result event", async () => {
  await assert.rejects(consumePlanningGenerationStream(response(prefix() + frame("planning_progress", snapshot(["completed", "completed"]))), activityId, 2, () => {}), (error) => error instanceof ApiError && error.payload.detail.code === "GENERATION_INTERRUPTED");
});
test("domain failure remains failure with exact public code", async () => {
  const progress = [];
  await assert.rejects(consumePlanningGenerationStream(response(prefix() + frame("planning_failed", failed)), activityId, 2, (value) => progress.push(value)), (error) => error instanceof ApiError && error.payload.detail.code === "CCODE_TIMEOUT");
  assert.equal(progress.at(-1).status, "failed");
});
test("rejects mismatched activity, truncated frames, unknown event and fake terminal step", async () => {
  for (const text of [frame("planning_progress", { ...initial, activityId: generationId }), frame("legacy", initial), frame("planning_progress", initial).slice(0, -2), prefix() + frame("planning_completed", { ...snapshot(["completed", "completed"], "completed"), step: { ...step, status: "confirmed", confirmedBy: activityId, confirmedAt: step.updatedAt } })]) {
    await assert.rejects(consumePlanningGenerationStream(response(text), activityId, 2, () => {}), ActivityContractError);
  }
});
test("HTTP auth/domain rejection preserves server error payload", async () => {
  const payload = { detail: { code: "VERSION_CONFLICT" } };
  await assert.rejects(consumePlanningGenerationStream(Response.json(payload, { status: 409 }), activityId, 2, () => {}), (error) => error instanceof ApiError && error.status === 409 && error.payload.detail.code === "VERSION_CONFLICT");
});
test("aborting an in-flight response never synthesizes completion", async () => {
  const aborted = new DOMException("The request was aborted", "AbortError");
  let pulls = 0;
  const seen = [];
  const stream = new ReadableStream({ pull(controller) { if (pulls++ === 0) controller.enqueue(new TextEncoder().encode(frame("planning_progress", initial))); else controller.error(aborted); } });
  await assert.rejects(consumePlanningGenerationStream(new Response(stream, { headers: { "Content-Type": "text/event-stream" } }), activityId, 2, (value) => seen.push(value)), (error) => error === aborted);
  assert.deepEqual(seen.map((entry) => entry.status), ["running"]);
  assert.equal(stream.locked, false);
});
