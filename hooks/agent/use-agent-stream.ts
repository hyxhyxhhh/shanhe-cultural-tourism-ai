"use client";

import { useCallback, useEffect, useRef } from "react";
import { agentApi } from "@/lib/api/agents";
import { useAgentStore } from "@/stores/agent-store";

export function useAgentStream(agentId: string, runId?: string) {
  const setRun = useAgentStore((state) => state.setRun);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const stop = useCallback(() => { if (timer.current) { clearInterval(timer.current); timer.current = null; } }, []);
  useEffect(() => {
    if (!runId) return;
    timer.current = setInterval(async () => { const next = await agentApi.advance(agentId, runId); setRun(next); if (next.status === "completed" || next.status === "failed") stop(); }, 900);
    return stop;
  }, [agentId, runId, setRun, stop]);
  return { stop };
}
