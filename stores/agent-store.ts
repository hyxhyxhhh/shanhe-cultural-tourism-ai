import { create } from "zustand";
import type { AgentRun } from "@/lib/types/agent";

interface AgentState {
  currentAgentId: string;
  currentRunByAgent: Record<string, string>;
  runs: Record<string, AgentRun>;
  selectedPhaseByAgent: Record<string, number>;
  completedPhasesByAgent: Record<string, number[]>;
  setCurrentAgent: (id: string) => void;
  setRun: (run: AgentRun) => void;
  setSelectedPhase: (agentId: string, phase: number) => void;
  markPhaseComplete: (agentId: string, phase: number) => void;
  resetAgentFlow: (agentId: string) => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  currentAgentId: "event-planning",
  currentRunByAgent: {},
  runs: {},
  selectedPhaseByAgent: {},
  completedPhasesByAgent: {},
  setCurrentAgent: (currentAgentId) => set({ currentAgentId }),
  setRun: (run) => set((state) => ({
    currentRunByAgent: { ...state.currentRunByAgent, [run.agentId]: run.id },
    runs: { ...state.runs, [run.id]: run }
  })),
  setSelectedPhase: (agentId, phase) => set((state) => ({ selectedPhaseByAgent: { ...state.selectedPhaseByAgent, [agentId]: phase } })),
  markPhaseComplete: (agentId, phase) => set((state) => ({
    completedPhasesByAgent: {
      ...state.completedPhasesByAgent,
      [agentId]: Array.from(new Set([...(state.completedPhasesByAgent[agentId] ?? []), phase])).sort((a, b) => a - b)
    }
  })),
  resetAgentFlow: (agentId) => set((state) => {
    const nextRuns = { ...state.currentRunByAgent };
    delete nextRuns[agentId];
    return {
      currentRunByAgent: nextRuns,
      selectedPhaseByAgent: { ...state.selectedPhaseByAgent, [agentId]: 0 },
      completedPhasesByAgent: { ...state.completedPhasesByAgent, [agentId]: [] }
    };
  })
}));
