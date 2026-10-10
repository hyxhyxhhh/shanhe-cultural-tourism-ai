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
const { parseActivityStep, parseActivity, ActivityContractError } = contract;
const aid = "00000000-0000-4000-8000-000000000001";
const keys = ["brief", "research", "theme", "content_space", "budget", "promotion", "execution_plan", "channel_business", "review"];
const event = (id) => ({ id, name: "生态活动", timeWindow: "春季", targetAudience: "亲子家庭", positioning: "生态体验", themeDirection: "自然观察", scale: "小型", sharedAssets: [], highlights: ["自然教育"] });
const annual3 = { annualNarrative: "全年生态教育", eventBriefs: [event("event-1"), event("event-2")] };
const brief = { idea: "年度生态活动", planningMode: "annual", annualPeriod: "2027 年", annualGoals: "生态教育", plannedEventCount: 2 };
function step(n, outputJson = {}, inputJson = {}) { return { id: `00000000-0000-4000-8000-${String(n + 1).padStart(12, "0")}`, activityId: aid, stepNo: n, stepKey: keys[n - 1], status: "draft", inputJson: n === 1 ? brief : n === 2 ? { useWebSearch: false } : inputJson, outputJson, version: 1, confirmedBy: null, confirmedAt: null, updatedAt: "2026-10-09T00:00:00Z" }; }
const content = { schedule: [{ time: "活动日", title: "生态体验", description: "自然观察" }], zones: [{ name: "主场地", purpose: "教学", activities: [], requirements: [] }], personnel: [{ role: "讲师", count: 1, responsibilities: ["讲解"] }], safetyRequirements: ["现场疏导"] };
const envelope = { annualPlan: content, eventPlans: [{ eventId: "event-1", output: content }, { eventId: "event-2", output: content }] };
const activity = () => ({ id: aid, title: "年度规划", status: "draft", currentStep: 1, input: brief, searchEnabled: false, createdBy: aid, createdAt: "2026-10-09T00:00:00Z", updatedAt: "2026-10-09T00:00:00Z", steps: keys.map((_, i) => step(i + 1, i === 2 ? annual3 : i === 3 ? envelope : {})) });
test("annual step 3 and downstream envelopes validate independently", () => {
  assert.deepEqual(parseActivityStep(step(3, annual3)).outputJson, annual3);
  assert.deepEqual(parseActivityStep(step(4, envelope)).outputJson, envelope);
  assert.equal(parseActivity(activity()).input.planningMode, "annual");
});
test("annual output rejects mode mixing, duplicate IDs and missing brief fields", () => {
  for (const output of [{ ...annual3, candidates: [] }, { ...annual3, eventBriefs: [event("same"), event("same")] }, { ...annual3, eventBriefs: [{ ...event("event-1"), scale: "" }, event("event-2")] }, { ...annual3, eventBriefs: [event("event-1")] }]) assert.throws(() => parseActivityStep(step(3, output)), ActivityContractError);
  assert.throws(() => parseActivityStep(step(3, annual3, { selectedThemeId: "theme" })), ActivityContractError);
  assert.throws(() => parseActivityStep(step(4, { annualPlan: envelope, eventPlans: envelope.eventPlans })), ActivityContractError);
});
test("annual input is explicit; single cannot carry annual fields", () => {
  const value = activity();
  value.input = { ...brief, annualPeriod: "" };
  assert.throws(() => parseActivity(value), ActivityContractError);
  value.input = { ...brief, planningMode: "single" };
  assert.throws(() => parseActivity(value), ActivityContractError);
});
test("invalidated annual history stays readable while regenerating or after failure", () => {
  const value = activity();
  value.steps[3].outputJson = { ...envelope, eventPlans: [{ eventId: "old-1", output: content }, { eventId: "old-2", output: content }] };
  for (const status of ["draft", "review", "confirmed"]) {
    value.steps[3].status = status;
    value.steps[3].confirmedBy = status === "confirmed" ? aid : null;
    value.steps[3].confirmedAt = status === "confirmed" ? value.steps[3].updatedAt : null;
    assert.throws(() => parseActivity(value), ActivityContractError);
  }
  value.steps[3].confirmedBy = null;
  value.steps[3].confirmedAt = null;
  for (const status of ["needs_review", "generating", "failed"]) {
    value.steps[3].status = status;
    assert.equal(parseActivity(value).steps[3].status, status);
    value.steps[3].outputJson = { ...envelope, eventPlans: [{ eventId: "old-1", output: content }, { eventId: "old-1", output: content }] };
    assert.throws(() => parseActivity(value), ActivityContractError);
    value.steps[3].outputJson = { ...envelope, eventPlans: [{ eventId: "old-1", output: content }, { eventId: "old-2", output: content }] };
  }
});
test("annual budget rejects even a small incorrect declared total", () => {
  const budget = { items: [{ item: "材料", category: "物料", quantity: 3, unit: "份", unitPrice: 0.1, subtotal: 0.3, sourceType: "calculated", basis: "测算" }], totalAmount: 0.3, savings: [], resources: [{ name: "物料", quantity: 3, unit: "份", purpose: "活动" }], budgetNote: "参考测算" };
  const value = { annualPlan: budget, eventPlans: [{ eventId: "event-1", output: budget }, { eventId: "event-2", output: budget }], annualTotalAmount: 0.9 };
  assert.equal(parseActivityStep(step(5, value)).outputJson.annualTotalAmount, 0.9);
  assert.throws(() => parseActivityStep(step(5, { ...value, annualTotalAmount: 0.9001 })), ActivityContractError);
  assert.throws(() => parseActivityStep(step(5, { ...budget, totalAmount: 0.3001 })), ActivityContractError);
});
