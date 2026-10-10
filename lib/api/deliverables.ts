import { parseDeliverables } from "@/lib/api/activity-agent-contract";
import { ApiClient, ApiError } from "@/lib/api/client";

const api = new ApiClient();

export const deliverablesApi = {
  list(activityId: string) {
    return api
      .get<unknown>(`/activities/${encodeURIComponent(activityId)}/deliverables`)
      .then((value) => parseDeliverables(value, activityId));
  },
  generate(activityId: string) {
    return api
      .post<unknown>(`/activities/${encodeURIComponent(activityId)}/deliverables`, {})
      .then((value) => parseDeliverables(value, activityId));
  },
  async download(activityId: string, deliverableId: string) {
    const response = await fetch(`/api/activities/${encodeURIComponent(activityId)}/deliverables/${encodeURIComponent(deliverableId)}/download`);
    if (!response.ok) {
      const contentType = response.headers.get("content-type") ?? "";
      const payload: unknown = contentType.includes("application/json")
        ? await response.json()
        : (await response.text()) || undefined;
      const message =
        payload && typeof payload === "object" && typeof (payload as Record<string, unknown>).detail === "string"
          ? (payload as Record<string, unknown>).detail as string
          : typeof payload === "string" && payload
            ? payload
            : `API request failed: ${response.status}`;
      throw new ApiError(response.status, message, payload);
    }
    return response.blob();
  }
};
