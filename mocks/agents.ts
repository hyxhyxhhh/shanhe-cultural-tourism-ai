import type { Agent, AgentRun, AgentStep, RunAgentInput } from "@/lib/types/agent";
import { professionalAgents } from "@/mocks/professional-agents";

export const agents: Agent[] = [
  { id:"event-planning", name:"活动策划Agent", description:"从目标和数据研判出发，自动生成创意、预算、内容、任务并完成经营复盘", route:"/event-agent", enabled:true },
  ...Object.values(professionalAgents).map((agent) => ({ id: agent.id, name: agent.title, description: agent.description, route: `/${agent.id}`, enabled: true }))
];

const runStore = new Map<string, AgentRun>();

function makeSteps(names: string[]): AgentStep[] { return names.map((name, index) => ({ id:`step-${index + 1}`, name, status:"pending" })); }

export function createMockRun(agentId: string, input: RunAgentInput): AgentRun {
  const now = new Date().toISOString();
  const steps = makeSteps(input.phases ?? ["输入校验", "数据与市场研判", "方案结构化", "成果准备", "执行状态同步"]).map((step, index) => index === 0 ? { ...step, status:"running" as const, startedAt:now } : step);
  const run: AgentRun = { id:`run-${Date.now()}`, agentId, status:"running", currentStep:steps[0]?.name, progress:0, steps, createdAt:now, updatedAt:now };
  runStore.set(run.id, run); return run;
}

export function getMockRun(runId: string) { return runStore.get(runId); }

export function advanceMockRun(runId: string): AgentRun {
  const run = runStore.get(runId);
  if (!run) throw new Error("Run not found");
  const nextIndex = run.steps.findIndex((step) => step.status !== "completed");
  const now = new Date().toISOString();
  if (nextIndex === -1) return run;
  const steps = run.steps.map((step, index) => {
    if (index === nextIndex) return { ...step, status:"completed" as const, startedAt:step.startedAt ?? now, completedAt:now, message:"Mock execution complete" };
    if (index === nextIndex + 1) return { ...step, status:"running" as const, startedAt:now };
    return step;
  });
  const progress = Math.round(((nextIndex + 1) / run.steps.length) * 100);
  const updated: AgentRun = { ...run, steps, progress, status: progress === 100 ? "completed" : "running", currentStep: progress === 100 ? undefined : run.steps[Math.min(nextIndex + 1, run.steps.length - 1)]?.name, updatedAt:now, result: progress === 100 ? { title:"Mock execution result", summary:"执行框架已完成，真实业务步骤可由后端替换。", metrics:[{label:"流程状态",value:"完成"},{label:"执行进度",value:"100%"},{label:"输出状态",value:"待接入真实 Agent"}] } : undefined };
  runStore.set(runId, updated); return updated;
}

export function completeMockPhase(runId: string, phaseIndex: number): AgentRun {
  const run = runStore.get(runId);
  if (!run) throw new Error("Run not found");
  const now = new Date().toISOString();
  const completedSteps = run.steps.map((step, index) => index === phaseIndex ? {
    ...step,
    status:"completed" as const,
    startedAt:step.startedAt ?? now,
    completedAt:now,
    message:"Mock phase complete"
  } : step);
  const nextIndex = completedSteps.findIndex((step) => step.status !== "completed");
  const steps = completedSteps.map((step, index) => {
    if (step.status === "completed") return step;
    if (index === nextIndex) return { ...step, status:"running" as const, startedAt:step.startedAt ?? now, completedAt:undefined };
    return { ...step, status:"pending" as const, startedAt:undefined, completedAt:undefined };
  });
  const completedCount = steps.filter((step) => step.status === "completed").length;
  const progress = Math.round((completedCount / steps.length) * 100);
  const updated: AgentRun = {
    ...run,
    steps,
    progress,
    status:completedCount === steps.length ? "completed" : "running",
    currentStep:nextIndex === -1 ? undefined : steps[nextIndex]?.name,
    updatedAt:now,
    result:completedCount === steps.length ? {
      title:"Mock execution result",
      summary:"九步流程已完成，真实业务结果可由后端直接替换。",
      metrics:[{label:"流程状态",value:"完成"},{label:"执行进度",value:"100%"},{label:"输出状态",value:"待接入真实 Agent"}]
    } : undefined
  };
  runStore.set(runId, updated);
  return updated;
}

export function failMockRun(runId: string, message = "Mock execution failed") {
  const run = runStore.get(runId); if (!run) throw new Error("Run not found");
  const updated = { ...run, status:"failed" as const, error:message, updatedAt:new Date().toISOString() }; runStore.set(runId, updated); return updated;
}

export function cancelMockRun(runId: string) {
  const run = runStore.get(runId); if (!run) throw new Error("Run not found");
  const updated: AgentRun = {
    ...run,
    status:"cancelled",
    currentStep:undefined,
    steps:run.steps.map((step) => step.status === "running" ? { ...step, status:"cancelled" as const, completedAt:new Date().toISOString() } : step),
    updatedAt:new Date().toISOString()
  };
  runStore.set(runId, updated); return updated;
}
