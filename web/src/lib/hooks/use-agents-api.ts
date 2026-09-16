"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { agentsApi } from "@/lib/api/agents";
import type { AgentRunDTO } from "@/lib/api/agents";

const AGENT_RUNS = "agent-runs";

export function useAgentRuns(enabled: boolean) {
  return useQuery({
    queryKey: [AGENT_RUNS],
    queryFn: () => agentsApi.listRuns(),
    enabled,
    refetchInterval: enabled ? 5000 : false,
    retry: 1,
  });
}

export function useAgentDispatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ prompt, workspace }: { prompt: string; workspace?: string }) =>
      agentsApi.dispatch(prompt, workspace),
    onSuccess: () => qc.invalidateQueries({ queryKey: [AGENT_RUNS] }),
  });
}

export type { AgentRunDTO };
