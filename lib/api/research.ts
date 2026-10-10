import { ApiClient } from "@/lib/api/client";
import { parseResearchResult, parseResearchSelection } from "@/lib/api/activity-agent-contract";
import { consumeResearchGenerationStream, parseResearchGenerationEnvelope } from "@/lib/api/research-generation";
import type { GenerateStepRequest } from "@/lib/types/activity";
import type { ResearchEvidenceSelection, ResearchGenerationProgress, ResearchRequest, ResearchResult } from "@/lib/types/activity-agent";

const api = new ApiClient();

export const researchApi = {
  progress(activityId: string): Promise<ResearchGenerationProgress | null> {
    return api.get<unknown>(`/activities/${encodeURIComponent(activityId)}/research/generate/progress`)
      .then((value) => parseResearchGenerationEnvelope(value, activityId));
  },
  async generateGrouped(activityId: string, payload: GenerateStepRequest, onProgress: (progress: ResearchGenerationProgress) => void, signal?: AbortSignal) {
    const response = await fetch(`/api/activities/${encodeURIComponent(activityId)}/research/generate/stream`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(payload),
      signal
    });
    return consumeResearchGenerationStream(response, activityId, onProgress);
  },
  selection(activityId: string): Promise<ResearchEvidenceSelection> {
    return api.get<unknown>(`/activities/${encodeURIComponent(activityId)}/research/selection`)
      .then((value) => parseResearchSelection(value, activityId));
  },
  run(activityId: string, payload: ResearchRequest): Promise<ResearchResult> {
    return api
      .post<unknown>(`/activities/${encodeURIComponent(activityId)}/research`, payload)
      .then((value) => parseResearchResult(value, activityId));
  }
};
