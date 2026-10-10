export type AgentRunStatus = "idle" | "running" | "completed" | "failed" | "cancelled";
export type StepStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export interface Agent {
  id: string;
  name: string;
  description: string;
  route: string;
  enabled: boolean;
}

export interface AgentStep {
  id: string;
  name: string;
  status: StepStatus;
  message?: string;
  startedAt?: string;
  completedAt?: string;
}

export interface AgentResult {
  title: string;
  summary: string;
  metrics: Array<{ label: string; value: string; note?: string }>;
}

export interface AgentRun {
  id: string;
  agentId: string;
  status: AgentRunStatus;
  currentStep?: string;
  progress: number;
  steps: AgentStep[];
  result?: AgentResult;
  error?: string;
  createdAt: string;
  updatedAt: string;
}

export interface RunAgentInput {
  fields: Record<string, string>;
  phases?: string[];
}

export type AgentStreamEvent =
  | { type: "step_started"; run: AgentRun }
  | { type: "step_completed"; run: AgentRun }
  | { type: "message"; message: string; run: AgentRun }
  | { type: "progress"; progress: number; run: AgentRun }
  | { type: "result"; run: AgentRun }
  | { type: "error"; message: string; run: AgentRun };
