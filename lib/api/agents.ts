import type { Agent, AgentRun, RunAgentInput } from "@/lib/types/agent";
import { advanceMockRun, cancelMockRun, completeMockPhase, createMockRun, getMockRun } from "@/mocks/agents";

export const agentApi = {
  async list(): Promise<Agent[]> { return (await import("@/mocks/agents")).agents; },
  async get(agentId: string): Promise<Agent | undefined> { return (await import("@/mocks/agents")).agents.find((agent) => agent.id === agentId); },
  async run(agentId: string, input: RunAgentInput): Promise<AgentRun> { return createMockRun(agentId, input); },
  async getRun(_agentId: string, runId: string): Promise<AgentRun | undefined> { return getMockRun(runId); },
  async advance(_agentId: string, runId: string): Promise<AgentRun> { return advanceMockRun(runId); },
  async completePhase(_agentId: string, runId: string, phaseIndex: number): Promise<AgentRun> { return completeMockPhase(runId, phaseIndex); },
  async cancel(_agentId: string, runId: string): Promise<AgentRun> { return cancelMockRun(runId); }
};
