export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export type JobEventType = "job_started" | "progress" | "step_output_updated" | "job_completed" | "job_failed";

export interface JobRecord {
  id: string;
  activityId: string;
  kind: string;
  stepNo?: number | null;
  status: JobStatus;
  percent: number;
  message: string;
  result?: Record<string, unknown> | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface JobEvent {
  eventId: string;
  activityId: string;
  jobId: string;
  stepNo?: number | null;
  type: JobEventType;
  createdAt: string;
  payload: { percent?: number; message?: string; [key: string]: unknown };
}

export type ResearchScope = "weather" | "holiday" | "similar_events" | "public_trend";
export interface ResearchGenerationProgress {
  activityId: string;
  generationId: string;
  status: "running" | "completed" | "failed";
  totalScopes: number;
  completedScopes: number;
  scopes: Array<{
    scope: ResearchScope;
    status: "waiting" | "running" | "completed" | "failed" | "cancelled";
    sourceCount: number;
  }>;
  errorCode?: string;
}
export type ResearchSourceType = "actual" | "public" | "calculated" | "missing";
export type ResearchAuthorityLevel = "very_high" | "high" | "normal";

export interface ResearchRequest {
  version: number;
  useWebSearch: boolean;
  queryScope: ResearchScope[];
  query?: string;
}

export interface ResearchSourceReference {
  sourceType: ResearchSourceType;
  label: string;
  url?: string;
  capturedAt?: string;
  excerpt?: string;
  reasoning?: string;
  publishedAt?: string;
  siteName?: string;
  authorityLevel?: ResearchAuthorityLevel;
  rank?: number;
  providerRequestId?: string;
  scope?: ResearchScope;
}

export interface ResearchItem {
  label: string;
  summary: string;
  url: string;
  capturedAt: string;
  publishedAt?: string;
  siteName?: string;
  authorityLevel?: ResearchAuthorityLevel;
  rank: number;
  providerRequestId: string;
  scope: ResearchScope;
}

export interface ResearchResult {
  activityId: string;
  useWebSearch: boolean;
  query: string;
  queryScope: ResearchScope[];
  sourceType: "public" | "missing";
  items: ResearchItem[];
  sourceReferences: ResearchSourceReference[];
  warning?: string | null;
}

export interface ResearchEvidenceEntry {
  label: string;
  url: string;
  capturedAt: string;
  excerpt: string;
  providerRequestId: string;
  publishedAt?: string;
  siteName?: string;
  authorityLevel?: ResearchAuthorityLevel;
  scope: ResearchScope;
  rank: number;
}

export interface ResearchEvidenceSelection {
  activityId: string;
  totalCount: number;
  selectedCount: number;
  omittedCount: number;
  selected: ResearchEvidenceEntry[];
  omitted: Array<ResearchEvidenceEntry & { reason: string }>;
}

export type ExecutionTaskStatus = "draft" | "pending_confirmation" | "ready" | "in_progress" | "blocked" | "completed";

export interface ExecutionTask {
  id: string;
  activityId: string;
  stepNo: number;
  title: string;
  description: string | null;
  owner: string | null;
  dueAt: string | null;
  status: ExecutionTaskStatus;
  attachmentFileIds: string[];
}

export interface ExecutionTaskUpdateInput {
  owner?: string | null;
  dueAt?: string | null;
  status?: ExecutionTaskStatus;
}

export interface ExecutionTaskInput {
  title: string;
  description?: string;
  owner?: string;
  dueAt?: string;
  attachmentFileIds?: string[];
}

export interface Deliverable {
  id: string;
  activityId: string;
  filename: "event-plan.docx" | "budget.xlsx" | "execution-tasks.xlsx";
  contentType: string;
  storageKey: string;
  version: number;
  createdAt: string;
}
