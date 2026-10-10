export type ActivityStatus = "draft" | "running" | "paused" | "completed" | "failed" | "archived";
export type ActivityStepStatus = "locked" | "draft" | "generating" | "review" | "confirmed" | "needs_review" | "failed";
export type ActivityStepNo = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9;
export type ActivityStepKey =
  | "brief"
  | "research"
  | "theme"
  | "content_space"
  | "budget"
  | "promotion"
  | "execution_plan"
  | "channel_business"
  | "review";

export type JsonValue = string | number | boolean | null | JsonObject | JsonValue[];
export interface JsonObject {
  [key: string]: JsonValue;
}

export interface ActivityBriefInput {
  idea: string;
  planningMode?: "single" | "annual";
  annualPeriod?: string;
  annualGoals?: string;
  plannedEventCount?: number;
  location?: string;
  plannedStartAt?: string;
  plannedEndAt?: string;
  target?: string;
  budgetMin?: number;
  budgetMax?: number;
  targetAudience?: string;
  knownConstraints?: string;
}

export interface PlanningGenerationProgress {
  activityId: string;
  generationId: string;
  stepNo: ActivityStepNo;
  status: "running" | "completed" | "failed";
  totalUnits: number;
  completedUnits: number;
  units: Array<{ key: string; label: string; status: "waiting" | "running" | "completed" | "failed" | "cancelled" }>;
  errorCode?: string;
}

export interface ActivityStep {
  id: string;
  activityId: string;
  stepNo: ActivityStepNo;
  stepKey: ActivityStepKey;
  status: ActivityStepStatus;
  inputJson: JsonObject;
  outputJson: JsonObject;
  version: number;
  confirmedBy: string | null;
  confirmedAt: string | null;
  updatedAt: string;
}

export interface PatchStepRequest {
  version: number;
  inputJson?: JsonObject;
  outputJson?: JsonObject;
}

export interface GenerateStepRequest {
  version: number;
  model: string;
}

export interface ConfirmStepRequest {
  version: number;
  comment?: string;
}

export interface ReopenStepRequest {
  version: number;
  comment?: string;
}

export interface Activity {
  id: string;
  title: string;
  status: ActivityStatus;
  currentStep: ActivityStepNo;
  input: ActivityBriefInput;
  searchEnabled: boolean;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  steps: ActivityStep[];
}

export interface CreateActivityRequest {
  title: string;
  input: ActivityBriefInput;
}

export interface UpdateActivityRequest {
  title?: string;
  status?: "draft" | "running";
}
