import type {
  Activity,
  ActivityBriefInput,
  ActivityStep,
  ActivityStepKey,
  ActivityStepNo,
  ActivityStepStatus,
  ActivityStatus,
  JsonObject,
  JsonValue
} from "@/lib/types/activity";
import type {
  ResearchAuthorityLevel,
  ResearchScope,
  ResearchSourceReference,
  ResearchSourceType
} from "@/lib/types/activity-agent";
import { decimalMultiply, decimalSum } from "@/lib/decimal-arithmetic";

export class ActivityContractError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ActivityContractError";
  }
}

const ACTIVITY_STATUSES = new Set<ActivityStatus>(["draft", "running", "paused", "completed", "failed", "archived"]);
const STEP_STATUSES = new Set<ActivityStepStatus>(["locked", "draft", "generating", "review", "confirmed", "needs_review", "failed"]);
const STEP_KEYS: readonly ActivityStepKey[] = [
  "brief",
  "research",
  "theme",
  "content_space",
  "budget",
  "promotion",
  "execution_plan",
  "channel_business",
  "review"
];
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const ACTIVITY_FIELDS = ["id", "title", "status", "currentStep", "input", "searchEnabled", "createdBy", "createdAt", "updatedAt", "steps"] as const;
const STEP_FIELDS = ["id", "activityId", "stepNo", "stepKey", "status", "inputJson", "outputJson", "version", "confirmedBy", "confirmedAt", "updatedAt"] as const;
const BRIEF_FIELDS = ["idea", "planningMode", "annualPeriod", "annualGoals", "plannedEventCount", "location", "plannedStartAt", "plannedEndAt", "target", "budgetMin", "budgetMax", "targetAudience", "knownConstraints"] as const;
const RESEARCH_SOURCE_TYPES = new Set<ResearchSourceType>(["actual", "public", "calculated", "missing"]);
const RESEARCH_AUTHORITY_LEVELS = new Set<ResearchAuthorityLevel>(["very_high", "high", "normal"]);
const RESEARCH_SCOPES = new Set<ResearchScope>(["weather", "holiday", "similar_events", "public_trend"]);
const RESEARCH_SOURCE_FIELDS = [
  "sourceType",
  "label",
  "url",
  "capturedAt",
  "excerpt",
  "reasoning",
  "publishedAt",
  "siteName",
  "authorityLevel",
  "rank",
  "providerRequestId",
  "scope"
] as const;

function object(value: unknown, name: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new ActivityContractError(`${name} must be an object`);
  }
  return value as Record<string, unknown>;
}

function exactFields(value: Record<string, unknown>, allowed: readonly string[], name: string) {
  const allowedSet = new Set(allowed);
  const unknown = Object.keys(value).filter((key) => !allowedSet.has(key));
  if (unknown.length) throw new ActivityContractError(`${name} contains unknown field(s): ${unknown.join(", ")}`);
}

function required(value: Record<string, unknown>, key: string, name: string): unknown {
  if (!Object.hasOwn(value, key)) throw new ActivityContractError(`${name}.${key} is required`);
  return value[key];
}

function string(value: unknown, name: string, nonEmpty = false): string {
  if (typeof value !== "string" || (nonEmpty && !value.trim())) throw new ActivityContractError(`${name} must be a ${nonEmpty ? "non-empty " : ""}string`);
  return value;
}

function boolean(value: unknown, name: string): boolean {
  if (typeof value !== "boolean") throw new ActivityContractError(`${name} must be a boolean`);
  return value;
}

function integer(value: unknown, name: string, min = 0): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < min) throw new ActivityContractError(`${name} must be an integer >= ${min}`);
  return value;
}

function dateString(value: unknown, name: string): string {
  const result = string(value, name);
  if (Number.isNaN(Date.parse(result))) throw new ActivityContractError(`${name} must be a valid date-time string`);
  return result;
}

function httpUrl(value: unknown, name: string): string {
  const result = string(value, name, true);
  let url: URL;
  try {
    url = new URL(result);
  } catch {
    throw new ActivityContractError(`${name} must be a valid HTTP(S) URL`);
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new ActivityContractError(`${name} must be a valid HTTP(S) URL`);
  }
  return result;
}

function nullableDate(value: unknown, name: string): string | null {
  return value === null ? null : dateString(value, name);
}

function jsonValue(value: unknown, name: string): JsonValue {
  if (value === null) throw new ActivityContractError(`${name} must not be null`);
  if (typeof value === "string" || typeof value === "boolean") return value;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (Array.isArray(value)) return value.map((item, index) => jsonValue(item, `${name}[${index}]`));
  const record = object(value, name);
  const result: JsonObject = {};
  for (const [key, item] of Object.entries(record)) result[key] = jsonValue(item, `${name}.${key}`);
  return result;
}

function jsonObject(value: unknown, name: string): JsonObject {
  const record = object(value, name);
  return jsonValue(record, name) as JsonObject;
}

function parseBrief(value: unknown, name: string): ActivityBriefInput {
  const record = object(value, name);
  exactFields(record, BRIEF_FIELDS, name);
  const result: ActivityBriefInput = { idea: string(required(record, "idea", name), `${name}.idea`, true) };
  validatePlanningFields(record, name);
  if (Object.hasOwn(record, "planningMode")) result.planningMode = record.planningMode as "single" | "annual";
  if (record.planningMode === "annual") {
    result.annualPeriod = record.annualPeriod as string;
    result.annualGoals = record.annualGoals as string;
    result.plannedEventCount = record.plannedEventCount as number;
  }
  for (const key of ["location", "target", "targetAudience", "knownConstraints"] as const) {
    if (Object.hasOwn(record, key)) result[key] = string(record[key], `${name}.${key}`);
  }
  for (const key of ["plannedStartAt", "plannedEndAt"] as const) {
    if (Object.hasOwn(record, key)) result[key] = dateString(record[key], `${name}.${key}`);
  }
  for (const key of ["budgetMin", "budgetMax"] as const) {
    if (Object.hasOwn(record, key)) {
      const value = record[key];
      if (typeof value !== "number" || !Number.isFinite(value) || value < 0) throw new ActivityContractError(`${name}.${key} must be a finite non-negative number`);
      result[key] = value;
    }
  }
  if (result.budgetMin !== undefined && result.budgetMax !== undefined && result.budgetMin > result.budgetMax) {
    throw new ActivityContractError(`${name}.budgetMin cannot exceed budgetMax`);
  }
  return result;
}

function validatePlanningFields(record: Record<string, unknown>, name: string) {
  const mode = Object.hasOwn(record, "planningMode") ? record.planningMode : "single";
  if (mode !== "single" && mode !== "annual") throw new ActivityContractError(`${name}.planningMode is invalid`);
  if (mode === "annual") {
    string(required(record, "annualPeriod", name), `${name}.annualPeriod`, true);
    string(required(record, "annualGoals", name), `${name}.annualGoals`, true);
    if (integer(required(record, "plannedEventCount", name), `${name}.plannedEventCount`, 2) > 12) throw new ActivityContractError(`${name}.plannedEventCount must be from 2 to 12`);
  } else if (["annualPeriod", "annualGoals", "plannedEventCount"].some((key) => Object.hasOwn(record, key))) throw new ActivityContractError(`${name} single mode cannot contain annual fields`);
}

function parseArray(value: unknown, name: string): unknown[] {
  if (!Array.isArray(value)) throw new ActivityContractError(`${name} must be an array`);
  return value;
}

function nonEmptyArray(value: unknown, name: string): unknown[] {
  const result = parseArray(value, name);
  if (!result.length) throw new ActivityContractError(`${name} must not be empty`);
  return result;
}

function finiteNumber(value: unknown, name: string, minimum?: number): number {
  if (typeof value !== "number" || !Number.isFinite(value) || (minimum !== undefined && value < minimum)) {
    throw new ActivityContractError(
      minimum === undefined
        ? `${name} must be a finite number`
        : `${name} must be a finite number >= ${minimum}`
    );
  }
  return value;
}

function stringArray(value: unknown, name: string, allowEmpty = false): string[] {
  const result = parseArray(value, name);
  if (!allowEmpty && !result.length) throw new ActivityContractError(`${name} must not be empty`);
  return result.map((item, index) => string(item, `${name}[${index}]`, true));
}

function sourceType(value: unknown, name: string, allowed: readonly string[]): string {
  const result = string(value, name, true);
  if (!allowed.includes(result)) throw new ActivityContractError(`${name} is invalid`);
  return result;
}

function optionalNonEmptyString(record: Record<string, unknown>, key: string, name: string): void {
  if (Object.hasOwn(record, key)) string(record[key], `${name}.${key}`, true);
}

export function parseResearchSourceReference(
  value: unknown,
  name: string,
  options: { requireSearchMetadata?: boolean } = {}
): ResearchSourceReference {
  const record = object(value, name);
  exactFields(record, RESEARCH_SOURCE_FIELDS, name);
  const sourceType = string(required(record, "sourceType", name), `${name}.sourceType`, true) as ResearchSourceType;
  if (!RESEARCH_SOURCE_TYPES.has(sourceType)) {
    throw new ActivityContractError(`${name}.sourceType is invalid`);
  }
  const label = string(required(record, "label", name), `${name}.label`, true);
  const url = Object.hasOwn(record, "url") ? httpUrl(record.url, `${name}.url`) : undefined;
  const capturedAt = Object.hasOwn(record, "capturedAt")
    ? dateString(record.capturedAt, `${name}.capturedAt`)
    : undefined;
  const excerpt = Object.hasOwn(record, "excerpt")
    ? string(record.excerpt, `${name}.excerpt`)
    : undefined;
  const reasoning = Object.hasOwn(record, "reasoning")
    ? string(record.reasoning, `${name}.reasoning`)
    : undefined;
  const publishedAt = Object.hasOwn(record, "publishedAt")
    ? string(record.publishedAt, `${name}.publishedAt`, true)
    : undefined;
  const siteName = Object.hasOwn(record, "siteName")
    ? string(record.siteName, `${name}.siteName`, true)
    : undefined;
  const authorityLevel = Object.hasOwn(record, "authorityLevel")
    ? string(record.authorityLevel, `${name}.authorityLevel`, true) as ResearchAuthorityLevel
    : undefined;
  if (authorityLevel !== undefined && !RESEARCH_AUTHORITY_LEVELS.has(authorityLevel)) {
    throw new ActivityContractError(`${name}.authorityLevel is invalid`);
  }
  let rank: number | undefined;
  if (Object.hasOwn(record, "rank")) {
    rank = integer(record.rank, `${name}.rank`);
  }
  const providerRequestId = Object.hasOwn(record, "providerRequestId")
    ? string(record.providerRequestId, `${name}.providerRequestId`, true)
    : undefined;
  const scope = Object.hasOwn(record, "scope")
    ? string(record.scope, `${name}.scope`, true) as ResearchScope
    : undefined;
  if (scope !== undefined && !RESEARCH_SCOPES.has(scope)) {
    throw new ActivityContractError(`${name}.scope is invalid`);
  }
  if (sourceType === "public" && (url === undefined || capturedAt === undefined || !excerpt)) {
    throw new ActivityContractError(`${name} public source evidence is incomplete`);
  }
  if (
    sourceType === "public" &&
    options.requireSearchMetadata === true &&
    (rank === undefined || providerRequestId === undefined || scope === undefined)
  ) {
    throw new ActivityContractError(`${name} public search metadata is incomplete`);
  }
  if (sourceType === "calculated" && !reasoning) {
    throw new ActivityContractError(`${name} calculated source reasoning is required`);
  }
  return {
    sourceType,
    label,
    ...(url === undefined ? {} : { url }),
    ...(capturedAt === undefined ? {} : { capturedAt }),
    ...(excerpt === undefined ? {} : { excerpt }),
    ...(reasoning === undefined ? {} : { reasoning }),
    ...(publishedAt === undefined ? {} : { publishedAt }),
    ...(siteName === undefined ? {} : { siteName }),
    ...(authorityLevel === undefined ? {} : { authorityLevel }),
    ...(rank === undefined ? {} : { rank }),
    ...(providerRequestId === undefined ? {} : { providerRequestId }),
    ...(scope === undefined ? {} : { scope })
  };
}

function validateReviewMetric(value: unknown, name: string, expectedSourceType: "actual" | "calculated") {
  const item = object(value, name);
  exactFields(item, ["metric", "value", "unit", "sourceType", "basis"], name);
  string(required(item, "metric", name), `${name}.metric`, true);
  finiteNumber(required(item, "value", name), `${name}.value`);
  string(required(item, "unit", name), `${name}.unit`, true);
  const actualSourceType = sourceType(required(item, "sourceType", name), `${name}.sourceType`, ["actual", "calculated"]);
  if (actualSourceType !== expectedSourceType) {
    throw new ActivityContractError(`${name}.sourceType must be ${expectedSourceType}`);
  }
  string(required(item, "basis", name), `${name}.basis`, true);
}

function parseStepInput(stepNo: ActivityStepNo, value: unknown): JsonObject {
  const record = jsonObject(value, `step ${stepNo} inputJson`);
  if (stepNo === 1) {
    parseBrief(record, `step ${stepNo} inputJson`);
    return record;
  }
  const allowed = stepNo === 2 ? ["useWebSearch"] : stepNo === 3 ? ["selectedThemeId", "selectedPlanItemId"] : [];
  exactFields(record, allowed, `step ${stepNo} inputJson`);
  if (stepNo === 2 && typeof record.useWebSearch !== "boolean") throw new ActivityContractError("step 2 inputJson.useWebSearch must be a boolean");
  if (stepNo === 3 && Object.hasOwn(record, "selectedThemeId") && (typeof record.selectedThemeId !== "string" || !record.selectedThemeId.trim())) {
    throw new ActivityContractError("step 3 inputJson.selectedThemeId must be a non-empty string");
  }
  if (stepNo === 3 && Object.hasOwn(record, "selectedPlanItemId")) string(record.selectedPlanItemId, "step 3 selectedPlanItemId", true);
  if (stepNo === 3 && Object.hasOwn(record, "selectedPlanItemId") && Object.hasOwn(record, "selectedThemeId")) throw new ActivityContractError("step 3 cannot mix annual and single selection");
  return record;
}

function parseStepOutput(stepNo: ActivityStepNo, value: unknown, nested = false): JsonObject {
  const record = jsonObject(value, `step ${stepNo} outputJson`);
  if (!Object.keys(record).length) return record;
  if (stepNo >= 4 && Object.hasOwn(record, "annualPlan")) {
    if (nested) throw new ActivityContractError("annual plan cannot contain nested annual envelopes");
    exactFields(record, stepNo === 5 ? ["annualPlan", "eventPlans", "annualTotalAmount"] : ["annualPlan", "eventPlans"], `annual step ${stepNo}`);
    const annual = parseStepOutput(stepNo, required(record, "annualPlan", "annual output"), true);
    if (!Object.keys(annual).length) throw new ActivityContractError("annual plan cannot be empty");
    const events = nonEmptyArray(required(record, "eventPlans", "annual output"), "annual eventPlans");
    if (events.length < 2 || events.length > 12) throw new ActivityContractError("annual eventPlans must contain 2 to 12 items");
    const ids = new Set<string>();
    const amounts = stepNo === 5 ? [finiteNumber(annual.totalAmount, "annualPlan.totalAmount", 0)] : [];
    events.forEach((entry) => {
      const event = object(entry, "annual eventPlan");
      exactFields(event, ["eventId", "output"], "annual eventPlan");
      const id = string(required(event, "eventId", "eventPlan"), "eventPlan.eventId", true);
      if (["annual", "single"].includes(id)) throw new ActivityContractError("eventId uses a reserved planning unit key");
      if (ids.has(id)) throw new ActivityContractError("annual eventIds must be unique");
      ids.add(id);
      const output = parseStepOutput(stepNo, required(event, "output", "eventPlan"), true);
      if (!Object.keys(output).length) throw new ActivityContractError("event output cannot be empty");
      if (stepNo === 5) amounts.push(finiteNumber(output.totalAmount, "event totalAmount", 0));
    });
    if (stepNo === 5 && finiteNumber(required(record, "annualTotalAmount", "annual budget"), "annualTotalAmount", 0) !== decimalSum(amounts)) throw new ActivityContractError("annualTotalAmount must equal annual shared budget plus all event budgets");
    return record;
  }
  if (stepNo === 1) {
    exactFields(record, ["standardizedBrief", "missingFields"], "step 1 outputJson");
    const brief = object(required(record, "standardizedBrief", "step 1 outputJson"), "step 1 outputJson.standardizedBrief");
    exactFields(brief, ["objective", "planningMode", "annualPeriod", "annualGoals", "plannedEventCount", "location", "plannedStartAt", "plannedEndAt", "target", "budgetMin", "budgetMax", "targetAudience", "knownConstraints"], "standardizedBrief");
    validatePlanningFields(brief, "standardizedBrief");
    string(required(brief, "objective", "standardizedBrief"), "standardizedBrief.objective", true);
    for (const key of ["location", "plannedStartAt", "plannedEndAt", "target", "targetAudience", "knownConstraints"] as const) {
      if (Object.hasOwn(brief, key)) string(brief[key], `standardizedBrief.${key}`);
    }
    for (const key of ["budgetMin", "budgetMax"] as const) {
      if (Object.hasOwn(brief, key) && (typeof brief[key] !== "number" || !Number.isFinite(brief[key]) || brief[key] < 0)) {
        throw new ActivityContractError(`standardizedBrief.${key} must be a finite non-negative number`);
      }
    }
    parseArray(required(record, "missingFields", "step 1 outputJson"), "step 1 outputJson.missingFields").forEach((item, index) => string(item, `missingFields[${index}]`));
  } else if (stepNo === 2) {
    exactFields(record, ["summary", "findings", "sources", "risks"], "step 2 outputJson");
    string(required(record, "summary", "step 2 outputJson"), "step 2 summary", true);
    for (const key of ["findings", "risks"] as const) parseArray(required(record, key, "step 2 outputJson"), `step 2 ${key}`).forEach((item, index) => string(item, `step 2 ${key}[${index}]`));
    parseArray(required(record, "sources", "step 2 outputJson"), "step 2 sources").forEach((source, index) => {
      parseResearchSourceReference(source, `step 2 sources[${index}]`);
    });
  } else if (stepNo === 3) {
    if (Object.hasOwn(record, "annualNarrative") || Object.hasOwn(record, "eventBriefs")) {
      exactFields(record, ["annualNarrative", "eventBriefs"], "annual step 3 output");
      string(required(record, "annualNarrative", "annual output"), "annualNarrative", true);
      const events = nonEmptyArray(required(record, "eventBriefs", "annual output"), "eventBriefs");
      if (events.length < 2 || events.length > 12) throw new ActivityContractError("eventBriefs must contain 2 to 12 items");
      const ids = new Set<string>();
      events.forEach((value) => {
        const item = object(value, "eventBrief");
        exactFields(item, ["id", "name", "timeWindow", "targetAudience", "positioning", "themeDirection", "scale", "sharedAssets", "highlights"], "eventBrief");
        for (const key of ["id", "name", "timeWindow", "targetAudience", "positioning", "themeDirection", "scale"]) string(required(item, key, "eventBrief"), `eventBrief.${key}`, true);
        const id = item.id as string;
        if (["annual", "single"].includes(id)) throw new ActivityContractError("eventBrief id uses a reserved planning unit key");
        if (ids.has(id)) throw new ActivityContractError("annual eventBrief ids must be unique");
        ids.add(id);
        stringArray(required(item, "sharedAssets", "eventBrief"), "eventBrief.sharedAssets", true);
        stringArray(required(item, "highlights", "eventBrief"), "eventBrief.highlights");
      });
      return record;
    }
    exactFields(record, ["candidates"], "step 3 outputJson");
    const candidates = parseArray(required(record, "candidates", "step 3 outputJson"), "step 3 candidates");
    if (candidates.length < 2 || candidates.length > 3) throw new ActivityContractError("step 3 candidates must contain 2 to 3 items");
    const ids = new Set<string>();
    candidates.forEach((candidate, index) => {
      const item = object(candidate, `step 3 candidates[${index}]`);
      exactFields(item, ["id", "name", "storyline", "visualDirection", "highlights"], `step 3 candidates[${index}]`);
      const id = string(required(item, "id", "candidate"), `step 3 candidates[${index}].id`, true);
      if (ids.has(id)) throw new ActivityContractError("step 3 candidate ids must be unique");
      ids.add(id);
      for (const key of ["name", "storyline", "visualDirection"] as const) string(required(item, key, "candidate"), `step 3 candidates[${index}].${key}`, true);
      const highlights = parseArray(required(item, "highlights", "candidate"), `step 3 candidates[${index}].highlights`);
      if (!highlights.length) throw new ActivityContractError("step 3 candidate highlights cannot be empty");
      highlights.forEach((value, itemIndex) => string(value, `step 3 highlights[${itemIndex}]`, true));
    });
  } else if (stepNo === 4) {
    exactFields(record, ["schedule", "zones", "personnel", "safetyRequirements"], "step 4 outputJson");
    const schedule = parseArray(required(record, "schedule", "step 4 outputJson"), "step 4 schedule");
    const zones = parseArray(required(record, "zones", "step 4 outputJson"), "step 4 zones");
    const personnel = parseArray(required(record, "personnel", "step 4 outputJson"), "step 4 personnel");
    const safety = parseArray(required(record, "safetyRequirements", "step 4 outputJson"), "step 4 safetyRequirements");
    if (!schedule.length || !zones.length || !personnel.length || !safety.length) throw new ActivityContractError("step 4 output arrays cannot be empty");
    schedule.forEach((value, index) => {
      const item = object(value, `step 4 schedule[${index}]`);
      exactFields(item, ["time", "title", "description"], `step 4 schedule[${index}]`);
      for (const key of ["time", "title", "description"] as const) string(required(item, key, "schedule item"), `step 4 schedule[${index}].${key}`, true);
    });
    zones.forEach((value, index) => {
      const item = object(value, `step 4 zones[${index}]`);
      exactFields(item, ["name", "purpose", "activities", "requirements"], `step 4 zones[${index}]`);
      for (const key of ["name", "purpose"] as const) string(required(item, key, "zone"), `step 4 zones[${index}].${key}`, true);
      for (const key of ["activities", "requirements"] as const) parseArray(required(item, key, "zone"), `step 4 zones[${index}].${key}`).forEach((entry, entryIndex) => string(entry, `step 4 zones[${index}].${key}[${entryIndex}]`));
    });
    personnel.forEach((value, index) => {
      const item = object(value, `step 4 personnel[${index}]`);
      exactFields(item, ["role", "count", "responsibilities"], `step 4 personnel[${index}]`);
      string(required(item, "role", "personnel"), `step 4 personnel[${index}].role`, true);
      integer(required(item, "count", "personnel"), `step 4 personnel[${index}].count`, 1);
      const responsibilities = parseArray(required(item, "responsibilities", "personnel"), `step 4 personnel[${index}].responsibilities`);
      if (!responsibilities.length) throw new ActivityContractError(`step 4 personnel[${index}].responsibilities cannot be empty`);
      responsibilities.forEach((entry, entryIndex) => string(entry, `step 4 personnel[${index}].responsibilities[${entryIndex}]`, true));
    });
    safety.forEach((entry, index) => string(entry, `step 4 safetyRequirements[${index}]`, true));
  } else if (stepNo === 5) {
    exactFields(record, ["items", "totalAmount", "savings", "resources", "budgetNote"], "step 5 outputJson");
    const items = nonEmptyArray(required(record, "items", "step 5 outputJson"), "step 5 items");
    const subtotals: number[] = [];
    items.forEach((value, index) => {
      const name = `step 5 items[${index}]`;
      const item = object(value, name);
      exactFields(item, ["item", "category", "quantity", "unit", "unitPrice", "subtotal", "sourceType", "basis"], name);
      string(required(item, "item", name), `${name}.item`, true);
      string(required(item, "category", name), `${name}.category`, true);
      const quantity = finiteNumber(required(item, "quantity", name), `${name}.quantity`, Number.MIN_VALUE);
      string(required(item, "unit", name), `${name}.unit`, true);
      const unitPrice = finiteNumber(required(item, "unitPrice", name), `${name}.unitPrice`, 0);
      const subtotal = finiteNumber(required(item, "subtotal", name), `${name}.subtotal`, 0);
      if (subtotal !== decimalMultiply(quantity, unitPrice)) {
        throw new ActivityContractError(`${name}.subtotal must equal quantity multiplied by unitPrice`);
      }
      sourceType(required(item, "sourceType", name), `${name}.sourceType`, ["actual", "public", "calculated", "missing"]);
      string(required(item, "basis", name), `${name}.basis`, true);
      subtotals.push(subtotal);
    });
    const totalAmount = finiteNumber(required(record, "totalAmount", "step 5 outputJson"), "step 5 totalAmount", 0);
    if (totalAmount !== decimalSum(subtotals)) {
      throw new ActivityContractError("step 5 totalAmount must equal the sum of item subtotals");
    }
    parseArray(required(record, "savings", "step 5 outputJson"), "step 5 savings").forEach((value, index) => {
      const name = `step 5 savings[${index}]`;
      const item = object(value, name);
      exactFields(item, ["action", "estimatedSaving", "impact"], name);
      string(required(item, "action", name), `${name}.action`, true);
      finiteNumber(required(item, "estimatedSaving", name), `${name}.estimatedSaving`, 0);
      string(required(item, "impact", name), `${name}.impact`, true);
    });
    nonEmptyArray(required(record, "resources", "step 5 outputJson"), "step 5 resources").forEach((value, index) => {
      const name = `step 5 resources[${index}]`;
      const item = object(value, name);
      exactFields(item, ["name", "quantity", "unit", "purpose"], name);
      string(required(item, "name", name), `${name}.name`, true);
      finiteNumber(required(item, "quantity", name), `${name}.quantity`, Number.MIN_VALUE);
      string(required(item, "unit", name), `${name}.unit`, true);
      string(required(item, "purpose", name), `${name}.purpose`, true);
    });
    string(required(record, "budgetNote", "step 5 outputJson"), "step 5 budgetNote", true);
  } else if (stepNo === 6) {
    exactFields(record, ["strategy", "phases"], "step 6 outputJson");
    string(required(record, "strategy", "step 6 outputJson"), "step 6 strategy", true);
    const phases = parseArray(required(record, "phases", "step 6 outputJson"), "step 6 phases");
    if (phases.length !== 3) throw new ActivityContractError("step 6 phases must contain exactly three items");
    const phaseNames = new Set<string>();
    phases.forEach((value, index) => {
      const name = `step 6 phases[${index}]`;
      const item = object(value, name);
      exactFields(item, ["phase", "objective", "channels", "contentDrafts", "materials"], name);
      phaseNames.add(sourceType(required(item, "phase", name), `${name}.phase`, ["warmup", "peak", "followup"]));
      string(required(item, "objective", name), `${name}.objective`, true);
      stringArray(required(item, "channels", name), `${name}.channels`);
      stringArray(required(item, "contentDrafts", name), `${name}.contentDrafts`);
      stringArray(required(item, "materials", name), `${name}.materials`);
    });
    if (phaseNames.size !== 3) throw new ActivityContractError("step 6 phases must include warmup, peak, and followup once each");
  } else if (stepNo === 7) {
    exactFields(record, ["tasks", "approvalSummary", "externalActionsDraftOnly"], "step 7 outputJson");
    nonEmptyArray(required(record, "tasks", "step 7 outputJson"), "step 7 tasks").forEach((value, index) => {
      const name = `step 7 tasks[${index}]`;
      const item = object(value, name);
      exactFields(item, ["title", "description", "owner", "dueAt", "dependencies", "approvalDraft", "supplierInquiryDraft"], name);
      string(required(item, "title", name), `${name}.title`, true);
      string(required(item, "description", name), `${name}.description`, true);
      optionalNonEmptyString(item, "owner", name);
      if (Object.hasOwn(item, "dueAt")) dateString(item.dueAt, `${name}.dueAt`);
      stringArray(required(item, "dependencies", name), `${name}.dependencies`, true);
      string(required(item, "approvalDraft", name), `${name}.approvalDraft`, true);
      string(required(item, "supplierInquiryDraft", name), `${name}.supplierInquiryDraft`, true);
    });
    string(required(record, "approvalSummary", "step 7 outputJson"), "step 7 approvalSummary", true);
    if (required(record, "externalActionsDraftOnly", "step 7 outputJson") !== true) {
      throw new ActivityContractError("step 7 externalActionsDraftOnly must be true");
    }
  } else if (stepNo === 8) {
    exactFields(record, ["channelActions", "sponsorshipPackages", "ticketingPlan", "secondarySalesPlan", "externalActionsDraftOnly"], "step 8 outputJson");
    nonEmptyArray(required(record, "channelActions", "step 8 outputJson"), "step 8 channelActions").forEach((value, index) => {
      const name = `step 8 channelActions[${index}]`;
      const item = object(value, name);
      exactFields(item, ["channel", "objective", "actions", "revenueModel", "draftTerms"], name);
      string(required(item, "channel", name), `${name}.channel`, true);
      string(required(item, "objective", name), `${name}.objective`, true);
      stringArray(required(item, "actions", name), `${name}.actions`);
      string(required(item, "revenueModel", name), `${name}.revenueModel`, true);
      string(required(item, "draftTerms", name), `${name}.draftTerms`, true);
    });
    nonEmptyArray(required(record, "sponsorshipPackages", "step 8 outputJson"), "step 8 sponsorshipPackages").forEach((value, index) => {
      const name = `step 8 sponsorshipPackages[${index}]`;
      const item = object(value, name);
      exactFields(item, ["name", "targetPartner", "benefits", "referencePrice", "sourceType", "basis"], name);
      string(required(item, "name", name), `${name}.name`, true);
      string(required(item, "targetPartner", name), `${name}.targetPartner`, true);
      stringArray(required(item, "benefits", name), `${name}.benefits`);
      finiteNumber(required(item, "referencePrice", name), `${name}.referencePrice`, 0);
      sourceType(required(item, "sourceType", name), `${name}.sourceType`, ["calculated", "missing"]);
      string(required(item, "basis", name), `${name}.basis`, true);
    });
    string(required(record, "ticketingPlan", "step 8 outputJson"), "step 8 ticketingPlan", true);
    string(required(record, "secondarySalesPlan", "step 8 outputJson"), "step 8 secondarySalesPlan", true);
    if (required(record, "externalActionsDraftOnly", "step 8 outputJson") !== true) {
      throw new ActivityContractError("step 8 externalActionsDraftOnly must be true");
    }
  } else {
    exactFields(record, ["forecastMetrics", "actualMetrics", "missingActualMetrics", "conclusions", "improvements"], "step 9 outputJson");
    nonEmptyArray(required(record, "forecastMetrics", "step 9 outputJson"), "step 9 forecastMetrics").forEach((value, index) => {
      validateReviewMetric(value, `step 9 forecastMetrics[${index}]`, "calculated");
    });
    const actualMetrics = parseArray(required(record, "actualMetrics", "step 9 outputJson"), "step 9 actualMetrics");
    actualMetrics.forEach((value, index) => validateReviewMetric(value, `step 9 actualMetrics[${index}]`, "actual"));
    const missingActualMetrics = stringArray(required(record, "missingActualMetrics", "step 9 outputJson"), "step 9 missingActualMetrics", true);
    if (!actualMetrics.length && !missingActualMetrics.length) {
      throw new ActivityContractError("step 9 missingActualMetrics is required when actualMetrics is empty");
    }
    stringArray(required(record, "conclusions", "step 9 outputJson"), "step 9 conclusions");
    stringArray(required(record, "improvements", "step 9 outputJson"), "step 9 improvements");
  }
  return record;
}

export function parseActivityStep(value: unknown, expectedActivityId?: string): ActivityStep {
  const record = object(value, "activity step");
  exactFields(record, STEP_FIELDS, "activity step");
  const activityId = string(required(record, "activityId", "activity step"), "activity step.activityId");
  if (expectedActivityId && activityId !== expectedActivityId) throw new ActivityContractError("activity step.activityId does not match the requested activity");
  const stepNo = integer(required(record, "stepNo", "activity step"), "activity step.stepNo", 1) as ActivityStepNo;
  if (stepNo > 9) throw new ActivityContractError("activity step.stepNo must be from 1 to 9");
  const stepKey = string(required(record, "stepKey", "activity step"), "activity step.stepKey");
  if (stepKey !== STEP_KEYS[stepNo - 1]) throw new ActivityContractError("activity step.stepKey does not match stepNo");
  const status = string(required(record, "status", "activity step"), "activity step.status") as ActivityStepStatus;
  if (!STEP_STATUSES.has(status)) throw new ActivityContractError("activity step.status is invalid");
  const id = string(required(record, "id", "activity step"), "activity step.id");
  if (!UUID_PATTERN.test(id) || !UUID_PATTERN.test(activityId)) throw new ActivityContractError("activity step ids must be UUIDs");
  const version = integer(required(record, "version", "activity step"), "activity step.version", 1);
  const confirmedBy = record.confirmedBy === null ? null : string(record.confirmedBy, "activity step.confirmedBy", true);
  const confirmedAt = nullableDate(required(record, "confirmedAt", "activity step"), "activity step.confirmedAt");
  const inputJson = parseStepInput(stepNo, required(record, "inputJson", "activity step"));
  const outputJson = parseStepOutput(stepNo, required(record, "outputJson", "activity step"));
  if (stepNo === 3 && Object.keys(outputJson).length) {
    const annual = Object.hasOwn(outputJson, "eventBriefs");
    if (Object.hasOwn(inputJson, annual ? "selectedThemeId" : "selectedPlanItemId")) throw new ActivityContractError("step 3 selection does not match planning mode");
  }
  if (status === "confirmed" ? confirmedBy === null || confirmedAt === null : confirmedBy !== null || confirmedAt !== null) {
    throw new ActivityContractError("activity step confirmation fields do not match status");
  }
  return {
    id,
    activityId,
    stepNo,
    stepKey,
    status,
    inputJson,
    outputJson,
    version,
    confirmedBy,
    confirmedAt,
    updatedAt: dateString(required(record, "updatedAt", "activity step"), "activity step.updatedAt")
  };
}

export function parseSteps(value: unknown, expectedActivityId?: string): ActivityStep[] {
  const values = parseArray(value, "activity steps");
  if (values.length !== 9) throw new ActivityContractError("activity must contain exactly nine steps");
  const steps = values.map((item) => parseActivityStep(item, expectedActivityId));
  const numbers = new Set(steps.map((step) => step.stepNo));
  if (numbers.size !== 9 || steps.some((step, index) => step.stepNo !== index + 1)) throw new ActivityContractError("activity steps must contain each step number exactly once in order");
  return steps;
}

export function parseActivity(value: unknown): Activity {
  const record = object(value, "activity");
  exactFields(record, ACTIVITY_FIELDS, "activity");
  const id = string(required(record, "id", "activity"), "activity.id");
  if (!UUID_PATTERN.test(id)) throw new ActivityContractError("activity.id must be a UUID");
  const status = string(required(record, "status", "activity"), "activity.status") as ActivityStatus;
  if (!ACTIVITY_STATUSES.has(status)) throw new ActivityContractError("activity.status is invalid");
  const currentStep = integer(required(record, "currentStep", "activity"), "activity.currentStep", 1) as ActivityStepNo;
  if (currentStep > 9) throw new ActivityContractError("activity.currentStep must be from 1 to 9");
  const steps = parseSteps(required(record, "steps", "activity"), id);
  const input = parseBrief(required(record, "input", "activity"), "activity.input");
  const annual = input.planningMode === "annual";
  const briefs = steps[2].outputJson.eventBriefs;
  for (const step of steps) {
    if (!Object.keys(step.outputJson).length) continue;
    if (step.stepNo === 1) {
      const standardized = object(step.outputJson.standardizedBrief, "standardizedBrief");
      if ((standardized.planningMode === "annual") !== annual) throw new ActivityContractError("standardizedBrief planning mode differs from activity");
    } else if (step.stepNo >= 3) {
      if (Object.hasOwn(step.outputJson, step.stepNo === 3 ? "eventBriefs" : "annualPlan") !== annual) throw new ActivityContractError("step output planning mode differs from activity");
      // Invalidation and regeneration retain the previous output for review. It
      // remains historical while waiting, generating, or after a failed run;
      // writable drafts and successful results must match the current IDs.
      const historicalAnnualOutput = step.status === "needs_review" || step.status === "generating" || step.status === "failed";
      if (annual && step.stepNo >= 4 && !historicalAnnualOutput && Array.isArray(briefs)) {
        const expected = briefs.map((item) => (item as JsonObject).id);
        const actual = (step.outputJson.eventPlans as JsonObject[]).map((item) => item.eventId);
        if (JSON.stringify(expected) !== JSON.stringify(actual)) throw new ActivityContractError("annual eventPlans differ from confirmed event brief order");
      }
    }
  }
  const firstUnconfirmed = steps.find((step) => step.status !== "confirmed");
  const expectedCurrentStep = firstUnconfirmed?.stepNo ?? 9;
  if (currentStep !== expectedCurrentStep) throw new ActivityContractError("activity.currentStep does not match step statuses");
  if (firstUnconfirmed && status === "completed") {
    throw new ActivityContractError("activity.status cannot be completed while a step is unconfirmed");
  }
  if (!firstUnconfirmed && status !== "completed" && status !== "archived") {
    throw new ActivityContractError("activity.status must be completed or archived when all steps are confirmed");
  }
  return {
    id,
    title: string(required(record, "title", "activity"), "activity.title", true),
    status,
    currentStep,
    input,
    searchEnabled: boolean(required(record, "searchEnabled", "activity"), "activity.searchEnabled"),
    createdBy: string(required(record, "createdBy", "activity"), "activity.createdBy", true),
    createdAt: dateString(required(record, "createdAt", "activity"), "activity.createdAt"),
    updatedAt: dateString(required(record, "updatedAt", "activity"), "activity.updatedAt"),
    steps
  };
}

export function parseActivityList(value: unknown): Activity[] {
  return parseArray(value, "activities").map(parseActivity);
}
