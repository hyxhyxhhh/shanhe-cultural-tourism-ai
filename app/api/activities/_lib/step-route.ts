import {
  authenticatedFastApiFetch,
  authenticationRequired,
  forwardFastApiResponse,
  readJsonObject
} from "@/lib/server/fastapi";
import type {
  ActivityStepNo,
  ConfirmStepRequest,
  GenerateStepRequest,
  JsonObject,
  PatchStepRequest,
  ReopenStepRequest
} from "@/lib/types/activity";

export type StepRouteContext = {
  params: Promise<{ activityId: string; stepNo: string }>;
};

export type ActivityRouteContext = {
  params: Promise<{ activityId: string }>;
};

type ValidationResult<T> = { value: T; response?: never } | { value?: never; response: Response };

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function badRequest(code: string, message: string) {
  return Response.json({ detail: { code, message } }, { status: 400 });
}

function parseActivityId(value: string): ValidationResult<string> {
  if (!UUID_PATTERN.test(value)) {
    return { response: badRequest("INVALID_ACTIVITY_ID", "activityId must be a UUID") };
  }
  return { value };
}

function parseStepNo(value: string): ValidationResult<ActivityStepNo> {
  if (!/^[1-9]$/.test(value)) {
    return { response: badRequest("INVALID_STEP_NO", "stepNo must be an integer from 1 to 9") };
  }
  return { value: Number(value) as ActivityStepNo };
}

function parseVersion(body: Record<string, unknown>): ValidationResult<number> {
  if (!Number.isSafeInteger(body.version) || (body.version as number) < 1) {
    return { response: badRequest("INVALID_VERSION", "version must be a positive integer") };
  }
  return { value: body.version as number };
}

function parseJsonObject(value: unknown, field: string): ValidationResult<JsonObject> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { response: badRequest("INVALID_REQUEST_BODY", `${field} must be a JSON object`) };
  }
  return { value: value as JsonObject };
}

async function parseBody(request: Request): Promise<ValidationResult<Record<string, unknown>>> {
  const body = await readJsonObject(request);
  if (!body) return { response: badRequest("INVALID_REQUEST_BODY", "request body must be a JSON object") };
  return { value: body };
}

function rejectUnknownFields(
  body: Record<string, unknown>,
  allowedFields: readonly string[]
): ValidationResult<undefined> {
  const allowed = new Set(allowedFields);
  const unknownFields = Object.keys(body).filter((field) => !allowed.has(field));
  if (unknownFields.length > 0) {
    return {
      response: badRequest(
        "UNKNOWN_FIELD",
        `Unknown request field${unknownFields.length > 1 ? "s" : ""}: ${unknownFields.join(", ")}`
      )
    };
  }
  return { value: undefined };
}

export async function resolveActivityRoute(
  context: ActivityRouteContext
): Promise<ValidationResult<{ activityId: string }>> {
  const { activityId: rawActivityId } = await context.params;
  const activityId = parseActivityId(rawActivityId);
  if (activityId.response) return activityId;
  return { value: { activityId: activityId.value } };
}

export async function resolveStepRoute(
  context: StepRouteContext
): Promise<ValidationResult<{ activityId: string; stepNo: ActivityStepNo }>> {
  const { activityId: rawActivityId, stepNo: rawStepNo } = await context.params;
  const activityId = parseActivityId(rawActivityId);
  if (activityId.response) return activityId;
  const stepNo = parseStepNo(rawStepNo);
  if (stepNo.response) return stepNo;
  return { value: { activityId: activityId.value, stepNo: stepNo.value } };
}

export function stepsPath(activityId: string) {
  return `/api/activities/${encodeURIComponent(activityId)}/steps`;
}

export function stepPath(activityId: string, stepNo: ActivityStepNo, action?: "generate" | "confirm" | "reopen" | "generate/stream" | "generate/progress") {
  const path = `${stepsPath(activityId)}/${stepNo}`;
  return action ? `${path}/${action}` : path;
}

export async function parsePatchStepRequest(request: Request): Promise<ValidationResult<PatchStepRequest>> {
  const parsed = await parseBody(request);
  if (parsed.response) return parsed;
  const fields = rejectUnknownFields(parsed.value, ["version", "inputJson", "outputJson"]);
  if (fields.response) return fields;
  const version = parseVersion(parsed.value);
  if (version.response) return version;

  const result: PatchStepRequest = { version: version.value };
  if (Object.hasOwn(parsed.value, "inputJson")) {
    const inputJson = parseJsonObject(parsed.value.inputJson, "inputJson");
    if (inputJson.response) return inputJson;
    result.inputJson = inputJson.value;
  }
  if (Object.hasOwn(parsed.value, "outputJson")) {
    const outputJson = parseJsonObject(parsed.value.outputJson, "outputJson");
    if (outputJson.response) return outputJson;
    result.outputJson = outputJson.value;
  }
  if (result.inputJson === undefined && result.outputJson === undefined) {
    return {
      response: badRequest("INVALID_REQUEST_BODY", "inputJson or outputJson is required")
    };
  }
  return { value: result };
}

export async function parseGenerateStepRequest(request: Request): Promise<ValidationResult<GenerateStepRequest>> {
  const parsed = await parseBody(request);
  if (parsed.response) return parsed;
  const fields = rejectUnknownFields(parsed.value, ["version", "model"]);
  if (fields.response) return fields;
  const version = parseVersion(parsed.value);
  if (version.response) return version;

  const model = parsed.value.model;
  if (typeof model !== "string" || !model.trim() || model !== model.trim() || model.length > 200) {
    return {
      response: badRequest(
        "INVALID_MODEL",
        "model must be a non-empty string of at most 200 characters without surrounding whitespace"
      )
    };
  }

  return { value: { version: version.value, model } };
}

async function parseCommentRequest<T extends ConfirmStepRequest | ReopenStepRequest>(
  request: Request
): Promise<ValidationResult<T>> {
  const parsed = await parseBody(request);
  if (parsed.response) return parsed;
  const fields = rejectUnknownFields(parsed.value, ["version", "comment"]);
  if (fields.response) return fields;
  const version = parseVersion(parsed.value);
  if (version.response) return version;

  const result: ConfirmStepRequest = { version: version.value };
  if (Object.hasOwn(parsed.value, "comment")) {
    if (typeof parsed.value.comment !== "string") {
      return { response: badRequest("INVALID_REQUEST_BODY", "comment must be a string") };
    }
    const comment = parsed.value.comment.trim();
    if (!comment) {
      return { response: badRequest("INVALID_REQUEST_BODY", "comment must not be blank") };
    }
    result.comment = comment;
  }
  return { value: result as T };
}

export function parseConfirmStepRequest(request: Request) {
  return parseCommentRequest<ConfirmStepRequest>(request);
}

export function parseReopenStepRequest(request: Request) {
  return parseCommentRequest<ReopenStepRequest>(request);
}

export async function proxyAuthenticated(path: string, init?: RequestInit) {
  const upstream = await authenticatedFastApiFetch(path, init);
  if (!upstream) return authenticationRequired();
  return forwardFastApiResponse(upstream);
}

export function jsonRequest(method: "PATCH" | "POST", body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  };
}
