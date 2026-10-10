import { ApiClient } from "@/lib/api/client";
import { ActivityContractError, parseActivity, parseActivityList, parseActivityStep, parseSteps } from "@/lib/api/activity-contract";
import { consumePlanningGenerationStream, parsePlanningGenerationEnvelope } from "@/lib/api/planning-generation";
import type { PlanningGenerationProgress } from "@/lib/types/activity";
import type {
  ActivityStepNo,
  ConfirmStepRequest,
  CreateActivityRequest,
  GenerateStepRequest,
  PatchStepRequest,
  ReopenStepRequest,
  UpdateActivityRequest
} from "@/lib/types/activity";

const client = new ApiClient();
const MODEL_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:/+\-]*$/;

function parseModelCatalog(value: unknown): string[] {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new ActivityContractError("模型目录响应不符合数据契约。");
  }

  const payload = value as Record<string, unknown>;
  if (
    Object.keys(payload).length !== 1 ||
    !Object.hasOwn(payload, "models") ||
    !Array.isArray(payload.models) ||
    payload.models.length === 0 ||
    payload.models.some(
      (model) =>
        typeof model !== "string" ||
        model.length < 1 ||
        model.length > 200 ||
        model !== model.trim() ||
        !MODEL_ID_PATTERN.test(model)
    ) ||
    new Set(payload.models).size !== payload.models.length
  ) {
    throw new ActivityContractError("模型目录响应不符合数据契约。");
  }

  return payload.models;
}

export const activitiesApi = {
  planningProgress(activityId: string, stepNo: ActivityStepNo) {
    return client.get<unknown>(`/activities/${encodeURIComponent(activityId)}/steps/${stepNo}/generate/progress`).then((value) => parsePlanningGenerationEnvelope(value, activityId, stepNo));
  },
  async generatePlanning(activityId: string, stepNo: ActivityStepNo, request: GenerateStepRequest, onProgress: (progress: PlanningGenerationProgress) => void, signal: AbortSignal) {
    const response = await fetch(`/api/activities/${encodeURIComponent(activityId)}/steps/${stepNo}/generate/stream`, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", Accept: "text/event-stream" }, body: JSON.stringify(request), signal });
    return consumePlanningGenerationStream(response, activityId, stepNo, onProgress);
  },
  createPlanItemActivity(activityId: string, eventId: string, version: number) {
    return client.post<unknown>(`/activities/${encodeURIComponent(activityId)}/plan-items/${encodeURIComponent(eventId)}/activity`, { version }).then(parseActivity);
  },
  listModels() {
    return client.get<unknown>("/models").then(parseModelCatalog);
  },
  list(includeArchived = false) {
    const query = includeArchived ? "?includeArchived=true" : "";
    return client.get<unknown>(`/activities${query}`).then(parseActivityList);
  },
  create(request: CreateActivityRequest) {
    return client.post<unknown>("/activities", request).then(parseActivity);
  },
  get(activityId: string) {
    return client.get<unknown>(`/activities/${encodeURIComponent(activityId)}`).then(parseActivity);
  },
  update(activityId: string, request: UpdateActivityRequest) {
    return client.patch<unknown>(`/activities/${encodeURIComponent(activityId)}`, request).then(parseActivity);
  },
  pause(activityId: string) {
    return client.post<unknown>(`/activities/${encodeURIComponent(activityId)}/pause`).then(parseActivity);
  },
  archive(activityId: string) {
    return client.post<unknown>(`/activities/${encodeURIComponent(activityId)}/archive`).then(parseActivity);
  },
  listSteps(activityId: string) {
    return client.get<unknown>(`/activities/${encodeURIComponent(activityId)}/steps`).then((value) => parseSteps(value, activityId));
  },
  getStep(activityId: string, stepNo: ActivityStepNo) {
    return client.get<unknown>(`/activities/${encodeURIComponent(activityId)}/steps/${stepNo}`).then((value) => parseActivityStep(value, activityId));
  },
  updateStep(activityId: string, stepNo: ActivityStepNo, request: PatchStepRequest) {
    return client.patch<unknown>(`/activities/${encodeURIComponent(activityId)}/steps/${stepNo}`, request).then((value) => parseActivityStep(value, activityId));
  },
  generateStep(activityId: string, stepNo: ActivityStepNo, request: GenerateStepRequest) {
    return client.post<unknown>(
      `/activities/${encodeURIComponent(activityId)}/steps/${stepNo}/generate`,
      request
    ).then((value) => parseActivityStep(value, activityId));
  },
  confirmStep(activityId: string, stepNo: ActivityStepNo, request: ConfirmStepRequest) {
    return client.post<unknown>(
      `/activities/${encodeURIComponent(activityId)}/steps/${stepNo}/confirm`,
      request
    ).then((value) => parseActivityStep(value, activityId));
  },
  reopenStep(activityId: string, stepNo: ActivityStepNo, request: ReopenStepRequest) {
    return client.post<unknown>(
      `/activities/${encodeURIComponent(activityId)}/steps/${stepNo}/reopen`,
      request
    ).then((value) => parseActivityStep(value, activityId));
  }
};
