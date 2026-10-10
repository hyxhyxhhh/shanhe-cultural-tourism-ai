import {
  ActivityContractError,
  parseResearchSourceReference
} from "@/lib/api/activity-contract";
import type {
  Deliverable,
  ExecutionTask,
  ExecutionTaskStatus,
  ResearchItem,
  ResearchAuthorityLevel,
  ResearchEvidenceSelection,
  ResearchResult,
  ResearchScope
} from "@/lib/types/activity-agent";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const RESEARCH_SCOPES = new Set<ResearchScope>([
  "weather",
  "holiday",
  "similar_events",
  "public_trend"
]);
const AUTHORITY_LEVELS = new Set<ResearchAuthorityLevel>(["very_high", "high", "normal"]);
const TASK_STATUSES = new Set<ExecutionTaskStatus>([
  "draft",
  "pending_confirmation",
  "ready",
  "in_progress",
  "blocked",
  "completed"
]);
const DELIVERABLE_FILENAMES = new Set<Deliverable["filename"]>([
  "event-plan.docx",
  "budget.xlsx",
  "execution-tasks.xlsx"
]);

function object(value: unknown, name: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new ActivityContractError(`${name} must be an object`);
  }
  return value as Record<string, unknown>;
}

function exactFields(value: Record<string, unknown>, allowed: readonly string[], name: string) {
  const allowedSet = new Set(allowed);
  const unknown = Object.keys(value).filter((key) => !allowedSet.has(key));
  if (unknown.length > 0) {
    throw new ActivityContractError(`${name} contains unknown field(s): ${unknown.join(", ")}`);
  }
}

function required(value: Record<string, unknown>, key: string, name: string) {
  if (!Object.hasOwn(value, key)) throw new ActivityContractError(`${name}.${key} is required`);
  return value[key];
}

function string(value: unknown, name: string, nonEmpty = false): string {
  if (typeof value !== "string" || (nonEmpty && !value.trim())) {
    throw new ActivityContractError(`${name} must be a ${nonEmpty ? "non-empty " : ""}string`);
  }
  return value;
}

function uuid(value: unknown, name: string): string {
  const result = string(value, name, true);
  if (!UUID_PATTERN.test(result)) throw new ActivityContractError(`${name} must be a UUID`);
  return result;
}

function dateTime(value: unknown, name: string): string {
  const result = string(value, name, true);
  if (Number.isNaN(Date.parse(result))) {
    throw new ActivityContractError(`${name} must be a valid date-time string`);
  }
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

function array(value: unknown, name: string): unknown[] {
  if (!Array.isArray(value)) throw new ActivityContractError(`${name} must be an array`);
  return value;
}

function scopes(value: unknown, name: string, allowEmpty = false): ResearchScope[] {
  const result = array(value, name).map((entry, index) => {
    const scope = string(entry, `${name}[${index}]`, true) as ResearchScope;
    if (!RESEARCH_SCOPES.has(scope)) {
      throw new ActivityContractError(`${name}[${index}] is not supported`);
    }
    return scope;
  });
  if (!allowEmpty && result.length === 0) throw new ActivityContractError(`${name} must not be empty`);
  if (new Set(result).size !== result.length) {
    throw new ActivityContractError(`${name} must not contain duplicates`);
  }
  return result;
}

function parseResearchItem(value: unknown, index: number): ResearchItem {
  const name = `research result.items[${index}]`;
  const record = object(value, name);
  exactFields(
    record,
    ["label", "summary", "url", "capturedAt", "publishedAt", "siteName", "authorityLevel", "rank", "providerRequestId", "scope"],
    name
  );
  const authorityLevel = Object.hasOwn(record, "authorityLevel")
    ? string(record.authorityLevel, `${name}.authorityLevel`) as ResearchAuthorityLevel
    : undefined;
  if (authorityLevel !== undefined && !AUTHORITY_LEVELS.has(authorityLevel)) {
    throw new ActivityContractError(`${name}.authorityLevel is invalid`);
  }
  const rank = required(record, "rank", name);
  if (typeof rank !== "number" || !Number.isSafeInteger(rank) || rank < 0) {
    throw new ActivityContractError(`${name}.rank must be a non-negative integer`);
  }
  const scope = string(required(record, "scope", name), `${name}.scope`) as ResearchScope;
  if (!RESEARCH_SCOPES.has(scope)) throw new ActivityContractError(`${name}.scope is invalid`);
  return {
    label: string(required(record, "label", name), `${name}.label`, true),
    summary: string(required(record, "summary", name), `${name}.summary`, true),
    url: httpUrl(required(record, "url", name), `${name}.url`),
    capturedAt: dateTime(required(record, "capturedAt", name), `${name}.capturedAt`),
    ...(Object.hasOwn(record, "publishedAt") ? { publishedAt: string(record.publishedAt, `${name}.publishedAt`, true) } : {}),
    ...(Object.hasOwn(record, "siteName") ? { siteName: string(record.siteName, `${name}.siteName`, true) } : {}),
    ...(authorityLevel === undefined ? {} : { authorityLevel }),
    rank,
    providerRequestId: string(required(record, "providerRequestId", name), `${name}.providerRequestId`, true),
    scope
  };
}

export function parseResearchResult(value: unknown, expectedActivityId?: string): ResearchResult {
  const record = object(value, "research result");
  exactFields(
    record,
    [
      "activityId",
      "useWebSearch",
      "query",
      "queryScope",
      "sourceType",
      "items",
      "sourceReferences",
      "warning"
    ],
    "research result"
  );
  const activityId = uuid(required(record, "activityId", "research result"), "research result.activityId");
  if (expectedActivityId !== undefined && activityId !== expectedActivityId) {
    throw new ActivityContractError("research result.activityId does not match the requested activity");
  }
  if (typeof record.useWebSearch !== "boolean") {
    throw new ActivityContractError("research result.useWebSearch must be a boolean");
  }
  const sourceType = string(
    required(record, "sourceType", "research result"),
    "research result.sourceType"
  );
  if (sourceType !== "public" && sourceType !== "missing") {
    throw new ActivityContractError("research result.sourceType is invalid");
  }
  const items = array(required(record, "items", "research result"), "research result.items").map(
    parseResearchItem
  );
  if ((sourceType === "public") !== (items.length > 0)) {
    throw new ActivityContractError("research result sourceType does not match its items");
  }
  const sourceReferences = array(
    required(record, "sourceReferences", "research result"),
    "research result.sourceReferences"
  ).map((source, index) =>
    parseResearchSourceReference(
      source,
      `research result.sourceReferences[${index}]`,
      { requireSearchMetadata: true }
    )
  );
  if (sourceReferences.length === 0) {
    throw new ActivityContractError("research result.sourceReferences must not be empty");
  }
  let warning: string | null | undefined;
  if (Object.hasOwn(record, "warning")) {
    warning = record.warning === null ? null : string(record.warning, "research result.warning", true);
  }
  return {
    activityId,
    useWebSearch: record.useWebSearch,
    query: string(required(record, "query", "research result"), "research result.query", record.useWebSearch === true),
    queryScope: scopes(
      required(record, "queryScope", "research result"),
      "research result.queryScope",
      record.useWebSearch === false
    ),
    sourceType,
    items,
    sourceReferences,
    ...(warning === undefined ? {} : { warning })
  };
}

export function parseResearchSelection(value: unknown, expectedActivityId: string): ResearchEvidenceSelection {
  const name = "research selection";
  const record = object(value, name);
  exactFields(record, ["activityId", "totalCount", "selectedCount", "omittedCount", "selected", "omitted"], name);
  const activityId = uuid(required(record, "activityId", name), `${name}.activityId`);
  if (activityId !== expectedActivityId) throw new ActivityContractError(`${name}.activityId does not match the requested activity`);
  const integer = (value: unknown, field: string): number => {
    if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
      throw new ActivityContractError(`${field} must be a non-negative integer`);
    }
    return value;
  };
  const entry = (value: unknown, field: string, omitted: boolean) => {
    const item = object(value, field);
    const evidenceFields = ["label", "url", "capturedAt", "excerpt", "providerRequestId", "publishedAt", "siteName", "authorityLevel", "scope", "rank"];
    exactFields(item, omitted ? [...evidenceFields, "reason"] : evidenceFields, field);
    const scope = string(required(item, "scope", field), `${field}.scope`) as ResearchScope;
    if (!RESEARCH_SCOPES.has(scope)) throw new ActivityContractError(`${field}.scope is invalid`);
    const capturedAt = dateTime(required(item, "capturedAt", field), `${field}.capturedAt`);
    if (!/(?:Z|[+-]\d{2}:\d{2})$/i.test(capturedAt)) throw new ActivityContractError(`${field}.capturedAt must include a timezone`);
    const authorityLevel = Object.hasOwn(item, "authorityLevel")
      ? string(item.authorityLevel, `${field}.authorityLevel`) as ResearchAuthorityLevel
      : undefined;
    if (authorityLevel !== undefined && !AUTHORITY_LEVELS.has(authorityLevel)) throw new ActivityContractError(`${field}.authorityLevel is invalid`);
    return {
      label: string(required(item, "label", field), `${field}.label`, true),
      url: httpUrl(required(item, "url", field), `${field}.url`),
      capturedAt,
      excerpt: string(required(item, "excerpt", field), `${field}.excerpt`, true),
      providerRequestId: string(required(item, "providerRequestId", field), `${field}.providerRequestId`, true),
      ...(Object.hasOwn(item, "publishedAt") ? { publishedAt: string(item.publishedAt, `${field}.publishedAt`, true) } : {}),
      ...(Object.hasOwn(item, "siteName") ? { siteName: string(item.siteName, `${field}.siteName`, true) } : {}),
      ...(authorityLevel === undefined ? {} : { authorityLevel }),
      scope,
      rank: integer(required(item, "rank", field), `${field}.rank`),
      ...(omitted ? { reason: string(required(item, "reason", field), `${field}.reason`, true) } : {})
    };
  };
  const selected = array(required(record, "selected", name), `${name}.selected`).map((item, index) => entry(item, `${name}.selected[${index}]`, false));
  const omitted = array(required(record, "omitted", name), `${name}.omitted`).map((item, index) => {
    const result = entry(item, `${name}.omitted[${index}]`, true);
    return { ...result, reason: result.reason! };
  });
  const totalCount = integer(required(record, "totalCount", name), `${name}.totalCount`);
  const selectedCount = integer(required(record, "selectedCount", name), `${name}.selectedCount`);
  const omittedCount = integer(required(record, "omittedCount", name), `${name}.omittedCount`);
  if (selectedCount !== selected.length || omittedCount !== omitted.length || totalCount !== selectedCount + omittedCount) {
    throw new ActivityContractError(`${name} counts do not match its entries`);
  }
  if (selectedCount !== totalCount || omittedCount !== 0 || omitted.length !== 0) {
    throw new ActivityContractError(`${name} must include all search evidence without omissions`);
  }
  return { activityId, totalCount, selectedCount, omittedCount, selected, omitted };
}

export function parseExecutionTask(value: unknown, expectedActivityId?: string): ExecutionTask {
  const record = object(value, "execution task");
  exactFields(
    record,
    [
      "id",
      "activityId",
      "stepNo",
      "title",
      "description",
      "owner",
      "dueAt",
      "status",
      "attachmentFileIds"
    ],
    "execution task"
  );
  const activityId = uuid(required(record, "activityId", "execution task"), "execution task.activityId");
  if (expectedActivityId !== undefined && activityId !== expectedActivityId) {
    throw new ActivityContractError("execution task.activityId does not match the requested activity");
  }
  if (record.stepNo !== 7) throw new ActivityContractError("execution task.stepNo must be 7");
  const status = string(required(record, "status", "execution task"), "execution task.status") as ExecutionTaskStatus;
  if (!TASK_STATUSES.has(status)) throw new ActivityContractError("execution task.status is invalid");
  const attachmentFileIds = array(
    required(record, "attachmentFileIds", "execution task"),
    "execution task.attachmentFileIds"
  ).map((entry, index) => string(entry, `execution task.attachmentFileIds[${index}]`, true));
  const description = record.description === null
    ? null
    : string(required(record, "description", "execution task"), "execution task.description");
  const owner = record.owner === null
    ? null
    : string(required(record, "owner", "execution task"), "execution task.owner");
  const dueAt = record.dueAt === null
    ? null
    : dateTime(required(record, "dueAt", "execution task"), "execution task.dueAt");
  return {
    id: uuid(required(record, "id", "execution task"), "execution task.id"),
    activityId,
    stepNo: 7,
    title: string(required(record, "title", "execution task"), "execution task.title", true),
    description,
    owner,
    dueAt,
    status,
    attachmentFileIds
  };
}

export function parseExecutionTasks(value: unknown, expectedActivityId?: string): ExecutionTask[] {
  return array(value, "execution tasks").map((entry) => parseExecutionTask(entry, expectedActivityId));
}

export function parseDeliverable(value: unknown, expectedActivityId?: string): Deliverable {
  const record = object(value, "deliverable");
  exactFields(
    record,
    ["id", "activityId", "filename", "contentType", "storageKey", "version", "createdAt"],
    "deliverable"
  );
  const activityId = uuid(required(record, "activityId", "deliverable"), "deliverable.activityId");
  if (expectedActivityId !== undefined && activityId !== expectedActivityId) {
    throw new ActivityContractError("deliverable.activityId does not match the requested activity");
  }
  const filename = string(required(record, "filename", "deliverable"), "deliverable.filename") as Deliverable["filename"];
  if (!DELIVERABLE_FILENAMES.has(filename)) {
    throw new ActivityContractError("deliverable.filename is invalid");
  }
  const version = required(record, "version", "deliverable");
  if (typeof version !== "number" || !Number.isSafeInteger(version) || version < 1) {
    throw new ActivityContractError("deliverable.version must be a positive integer");
  }
  return {
    id: uuid(required(record, "id", "deliverable"), "deliverable.id"),
    activityId,
    filename,
    contentType: string(required(record, "contentType", "deliverable"), "deliverable.contentType", true),
    storageKey: string(required(record, "storageKey", "deliverable"), "deliverable.storageKey", true),
    version,
    createdAt: dateTime(required(record, "createdAt", "deliverable"), "deliverable.createdAt")
  };
}

export function parseDeliverables(value: unknown, expectedActivityId?: string): Deliverable[] {
  return array(value, "deliverables").map((entry) => parseDeliverable(entry, expectedActivityId));
}
