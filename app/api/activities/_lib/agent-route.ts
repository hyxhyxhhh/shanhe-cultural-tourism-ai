import {
  authenticatedFastApiFetch,
  authenticationRequired,
  forwardFastApiResponse,
  readJsonObject
} from "@/lib/server/fastapi";
import type {
  ExecutionTaskInput,
  ExecutionTaskStatus,
  ExecutionTaskUpdateInput,
  ResearchRequest,
  ResearchScope
} from "@/lib/types/activity-agent";

export type AgentActivityRouteContext = {
  params: Promise<{ activityId: string }>;
};

export type ExecutionTaskRouteContext = {
  params: Promise<{ activityId: string; taskId: string }>;
};

export type DeliverableRouteContext = {
  params: Promise<{ activityId: string; deliverableId: string }>;
};

type ValidationResult<T> = { value: T; response?: never } | { value?: never; response: Response };

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DELIVERABLE_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
const RESEARCH_SCOPES = new Set<ResearchScope>([
  "weather",
  "holiday",
  "similar_events",
  "public_trend"
]);
const EXECUTION_TASK_STATUSES = new Set<ExecutionTaskStatus>([
  "draft",
  "pending_confirmation",
  "ready",
  "in_progress",
  "blocked",
  "completed"
]);

function badRequest(code: string, message: string) {
  return Response.json({ detail: { code, message } }, { status: 400 });
}

function rejectUnknownFields(
  body: Record<string, unknown>,
  allowedFields: readonly string[]
): ValidationResult<undefined> {
  const allowed = new Set(allowedFields);
  const unknown = Object.keys(body).filter((field) => !allowed.has(field));
  if (unknown.length === 0) return { value: undefined };
  return {
    response: badRequest(
      "UNKNOWN_FIELD",
      `Unknown request field${unknown.length > 1 ? "s" : ""}: ${unknown.join(", ")}`
    )
  };
}

async function parseBody(request: Request): Promise<ValidationResult<Record<string, unknown>>> {
  const body = await readJsonObject(request);
  if (!body) {
    return { response: badRequest("INVALID_REQUEST_BODY", "request body must be a JSON object") };
  }
  return { value: body };
}

function parseRequiredString(
  value: unknown,
  field: string,
  maxLength: number
): ValidationResult<string> {
  if (typeof value !== "string" || !value.trim() || value.length > maxLength) {
    return {
      response: badRequest(
        "INVALID_REQUEST_BODY",
        `${field} must be a non-empty string of at most ${maxLength} characters`
      )
    };
  }
  return { value };
}

function parseOptionalString(
  body: Record<string, unknown>,
  field: string,
  maxLength: number
): ValidationResult<string | undefined> {
  if (!Object.hasOwn(body, field)) return { value: undefined };
  if (typeof body[field] !== "string" || (body[field] as string).length > maxLength) {
    return {
      response: badRequest(
        "INVALID_REQUEST_BODY",
        `${field} must be a string of at most ${maxLength} characters`
      )
    };
  }
  return { value: body[field] as string };
}

function parseDateTime(value: unknown, field: string): ValidationResult<string> {
  if (typeof value !== "string" || !value.trim() || Number.isNaN(Date.parse(value))) {
    return { response: badRequest("INVALID_REQUEST_BODY", `${field} must be a valid date-time string`) };
  }
  return { value };
}

function parseUuid(value: string, field: string, code: string): ValidationResult<string> {
  if (!UUID_PATTERN.test(value)) {
    return { response: badRequest(code, `${field} must be a UUID`) };
  }
  return { value };
}

export async function resolveAgentActivityRoute(
  context: AgentActivityRouteContext
): Promise<ValidationResult<{ activityId: string }>> {
  const { activityId: rawActivityId } = await context.params;
  const activityId = parseUuid(rawActivityId, "activityId", "INVALID_ACTIVITY_ID");
  if (activityId.response) return activityId;
  return { value: { activityId: activityId.value } };
}

export async function resolveExecutionTaskRoute(
  context: ExecutionTaskRouteContext
): Promise<ValidationResult<{ activityId: string; taskId: string }>> {
  const { activityId: rawActivityId, taskId: rawTaskId } = await context.params;
  const activityId = parseUuid(rawActivityId, "activityId", "INVALID_ACTIVITY_ID");
  if (activityId.response) return activityId;
  const taskId = parseUuid(rawTaskId, "taskId", "INVALID_TASK_ID");
  if (taskId.response) return taskId;
  return { value: { activityId: activityId.value, taskId: taskId.value } };
}

export async function resolveDeliverableRoute(
  context: DeliverableRouteContext
): Promise<ValidationResult<{ activityId: string; deliverableId: string }>> {
  const { activityId: rawActivityId, deliverableId } = await context.params;
  const activityId = parseUuid(rawActivityId, "activityId", "INVALID_ACTIVITY_ID");
  if (activityId.response) return activityId;
  if (!DELIVERABLE_ID_PATTERN.test(deliverableId)) {
    return {
      response: badRequest(
        "INVALID_DELIVERABLE_ID",
        "deliverableId must be a non-empty identifier of at most 128 characters"
      )
    };
  }
  return { value: { activityId: activityId.value, deliverableId } };
}

export async function parseResearchRequest(
  request: Request
): Promise<ValidationResult<ResearchRequest>> {
  const parsed = await parseBody(request);
  if (parsed.response) return parsed;
  const fields = rejectUnknownFields(parsed.value, ["version", "useWebSearch", "queryScope", "query"]);
  if (fields.response) return fields;
  if (!Number.isSafeInteger(parsed.value.version) || (parsed.value.version as number) < 1) {
    return { response: badRequest("INVALID_VERSION", "version must be a positive integer") };
  }
  if (typeof parsed.value.useWebSearch !== "boolean") {
    return {
      response: badRequest("INVALID_REQUEST_BODY", "useWebSearch must be a boolean")
    };
  }
  if (!Array.isArray(parsed.value.queryScope) || parsed.value.queryScope.length > 4) {
    return {
      response: badRequest("INVALID_REQUEST_BODY", "queryScope must be an array with at most four entries")
    };
  }
  const queryScope: ResearchScope[] = [];
  const seen = new Set<ResearchScope>();
  for (const scope of parsed.value.queryScope) {
    if (typeof scope !== "string" || !RESEARCH_SCOPES.has(scope as ResearchScope)) {
      return {
        response: badRequest("INVALID_RESEARCH_SCOPE", "queryScope contains an unsupported value")
      };
    }
    const typedScope = scope as ResearchScope;
    if (seen.has(typedScope)) {
      return {
        response: badRequest("DUPLICATE_RESEARCH_SCOPE", "queryScope must not contain duplicates")
      };
    }
    seen.add(typedScope);
    queryScope.push(typedScope);
  }
  const result: ResearchRequest = {
    version: parsed.value.version as number,
    useWebSearch: parsed.value.useWebSearch,
    queryScope
  };
  if (parsed.value.useWebSearch && queryScope.length === 0) {
    return { response: badRequest("INVALID_REQUEST_BODY", "queryScope is required when web search is enabled") };
  }
  if (!parsed.value.useWebSearch && (queryScope.length > 0 || Object.hasOwn(parsed.value, "query"))) {
    return {
      response: badRequest(
        "INVALID_REQUEST_BODY",
        "query and queryScope must be omitted when web search is disabled"
      )
    };
  }
  if (parsed.value.useWebSearch) {
    const query = parseRequiredString(parsed.value.query, "query", 70);
    if (query.response) return query;
    if (query.value !== query.value.trim()) {
      return { response: badRequest("INVALID_REQUEST_BODY", "query must not contain surrounding whitespace") };
    }
    result.query = query.value;
  }
  return { value: result };
}

export async function parseExecutionTaskCreateRequest(
  request: Request
): Promise<ValidationResult<ExecutionTaskInput>> {
  const parsed = await parseBody(request);
  if (parsed.response) return parsed;
  const fields = rejectUnknownFields(parsed.value, [
    "title",
    "description",
    "owner",
    "dueAt",
    "attachmentFileIds"
  ]);
  if (fields.response) return fields;
  const title = parseRequiredString(parsed.value.title, "title", 300);
  if (title.response) return title;
  const description = parseOptionalString(parsed.value, "description", 5000);
  if (description.response) return description;
  const owner = parseOptionalString(parsed.value, "owner", 200);
  if (owner.response) return owner;

  let dueAt: string | undefined;
  if (Object.hasOwn(parsed.value, "dueAt")) {
    const parsedDueAt = parseDateTime(parsed.value.dueAt, "dueAt");
    if (parsedDueAt.response) return parsedDueAt;
    dueAt = parsedDueAt.value;
  }

  let attachmentFileIds: string[] | undefined;
  if (Object.hasOwn(parsed.value, "attachmentFileIds")) {
    if (
      !Array.isArray(parsed.value.attachmentFileIds) ||
      parsed.value.attachmentFileIds.some((item) => typeof item !== "string" || !item)
    ) {
      return {
        response: badRequest(
          "INVALID_REQUEST_BODY",
          "attachmentFileIds must be an array of non-empty strings"
        )
      };
    }
    attachmentFileIds = parsed.value.attachmentFileIds;
  }

  return {
    value: {
      title: title.value,
      ...(description.value === undefined ? {} : { description: description.value }),
      ...(owner.value === undefined ? {} : { owner: owner.value }),
      ...(dueAt === undefined ? {} : { dueAt }),
      ...(attachmentFileIds === undefined ? {} : { attachmentFileIds })
    }
  };
}

export async function parseExecutionTaskUpdateRequest(
  request: Request
): Promise<ValidationResult<ExecutionTaskUpdateInput>> {
  const parsed = await parseBody(request);
  if (parsed.response) return parsed;
  const fields = rejectUnknownFields(parsed.value, ["owner", "dueAt", "status"]);
  if (fields.response) return fields;
  if (Object.keys(parsed.value).length === 0) {
    return {
      response: badRequest("INVALID_REQUEST_BODY", "at least one update field is required")
    };
  }

  const result: ExecutionTaskUpdateInput = {};
  if (Object.hasOwn(parsed.value, "owner")) {
    if (
      parsed.value.owner !== null &&
      (typeof parsed.value.owner !== "string" || parsed.value.owner.length > 200)
    ) {
      return {
        response: badRequest("INVALID_REQUEST_BODY", "owner must be null or a string of at most 200 characters")
      };
    }
    result.owner = parsed.value.owner as string | null;
  }
  if (Object.hasOwn(parsed.value, "dueAt")) {
    if (parsed.value.dueAt === null) {
      result.dueAt = null;
    } else {
      const dueAt = parseDateTime(parsed.value.dueAt, "dueAt");
      if (dueAt.response) return dueAt;
      result.dueAt = dueAt.value;
    }
  }
  if (Object.hasOwn(parsed.value, "status")) {
    if (
      typeof parsed.value.status !== "string" ||
      !EXECUTION_TASK_STATUSES.has(parsed.value.status as ExecutionTaskStatus)
    ) {
      return {
        response: badRequest("INVALID_TASK_STATUS", "status is not a supported execution task status")
      };
    }
    result.status = parsed.value.status as ExecutionTaskStatus;
  }
  return { value: result };
}

export async function parseEmptyObjectRequest(
  request: Request
): Promise<ValidationResult<Record<string, never>>> {
  const parsed = await parseBody(request);
  if (parsed.response) return parsed;
  const fields = rejectUnknownFields(parsed.value, []);
  if (fields.response) return fields;
  return { value: {} };
}

export function jsonRequest(method: "PATCH" | "POST", body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  };
}

export async function proxyAuthenticated(path: string, init?: RequestInit) {
  const upstream = await authenticatedFastApiFetch(path, init);
  if (!upstream) return authenticationRequired();
  return forwardFastApiResponse(upstream);
}

export async function fetchAuthenticated(path: string, init?: RequestInit) {
  const upstream = await authenticatedFastApiFetch(path, init);
  return upstream ?? authenticationRequired();
}
