"use client";

import { useMutation } from "@tanstack/react-query";
import { useAgentStore } from "@/stores/agent-store";
import { agentApi } from "@/lib/api/agents";
import type { RunAgentInput } from "@/lib/types/agent";

export function useAgentRun(agentId: string) {
  const setRun = useAgentStore((state) => state.setRun);
  const mutation = useMutation({ mutationFn: (input: RunAgentInput) => agentApi.run(agentId, input), onSuccess: setRun });
  return { ...mutation, run: mutation.data };
}
