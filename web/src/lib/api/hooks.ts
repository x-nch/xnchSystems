"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { endpoints } from "@/lib/api/endpoints";
import type { McpCallRequest } from "@/lib/api/types";

const HEALTH_MS = 5_000;
const SURFACE_MS = 15_000;
const LLM_STATUS_MS = 15_000;

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: endpoints.health,
    refetchInterval: HEALTH_MS,
    retry: 2,
  });
}

/** True once the gateway health check reports ok. */
export function useGatewayOnline(): boolean {
  const { data, isError } = useHealth();
  return !isError && data?.status === "ok";
}

export function useLlmStatus() {
  const online = useGatewayOnline();
  return useQuery({
    queryKey: ["llm-status"],
    queryFn: endpoints.llmStatus,
    enabled: online,
    refetchInterval: online ? LLM_STATUS_MS : false,
    retry: 1,
  });
}

export function useSystemState() {
  const online = useGatewayOnline();
  return useQuery({
    queryKey: ["system-state"],
    queryFn: endpoints.systemState,
    enabled: online,
    refetchInterval: online ? 30_000 : false,
    retry: 2,
  });
}

export function useCapabilities() {
  const online = useGatewayOnline();
  return useQuery({
    queryKey: ["capabilities"],
    queryFn: endpoints.capabilities,
    enabled: online,
    staleTime: 60_000,
    refetchInterval: online ? 120_000 : false,
    retry: 2,
  });
}

export function useSystemPrompt() {
  const online = useGatewayOnline();
  return useQuery({
    queryKey: ["system-prompt"],
    queryFn: endpoints.systemPrompt,
    enabled: online,
    staleTime: 60_000,
    retry: 2,
  });
}

export function useMcpTools(actorRole: string) {
  const online = useGatewayOnline();
  return useQuery({
    queryKey: ["mcp-tools", actorRole],
    queryFn: () => endpoints.mcpTools(actorRole),
    enabled: online,
    staleTime: 60_000,
    refetchInterval: online ? 60_000 : false,
    retry: 2,
  });
}

export function useMcpServers() {
  const online = useGatewayOnline();
  return useQuery({
    queryKey: ["mcp-servers"],
    queryFn: endpoints.mcpServers,
    enabled: online,
    staleTime: 60_000,
    refetchInterval: online ? 60_000 : false,
    retry: 2,
  });
}

export function useMemorySurface() {
  const online = useGatewayOnline();
  return useQuery({
    queryKey: ["memory-surface"],
    queryFn: endpoints.memorySurface,
    enabled: online,
    refetchInterval: online ? SURFACE_MS : false,
    retry: 2,
  });
}

export function useMemoryRecall() {
  return useMutation({
    mutationFn: (body: { query: string; top_k?: number }) =>
      endpoints.memoryRecall(body),
  });
}

export function useMcpCall() {
  return useMutation({
    mutationFn: (body: McpCallRequest) => endpoints.mcpCall(body),
  });
}

export function useGraphStats() {
  const online = useGatewayOnline();
  return useQuery({
    queryKey: ["graph-stats"],
    queryFn: endpoints.graphStats,
    enabled: online,
    retry: 2,
  });
}

export function useGraphEntities(params: {
  type?: string;
  search?: string;
  limit?: number;
  enabled?: boolean;
}) {
  const online = useGatewayOnline();
  const { type, search, limit = 200, enabled = true } = params;
  return useQuery({
    queryKey: ["graph-entities", type, search, limit],
    queryFn: () => endpoints.graphEntities({ type, search, limit }),
    enabled: online && enabled,
    retry: 2,
  });
}

export function useGraphRelations(params?: { limit?: number; enabled?: boolean }) {
  const online = useGatewayOnline();
  const limit = params?.limit ?? 400;
  const enabled = params?.enabled ?? true;
  return useQuery({
    queryKey: ["graph-relations", limit],
    queryFn: () => endpoints.graphRelations({ limit }),
    enabled: online && enabled,
    retry: 2,
  });
}

export function useGraphSubgraph(entityId: string | null, depth: 1 | 2) {
  const online = useGatewayOnline();
  return useQuery({
    queryKey: ["graph-subgraph", entityId, depth],
    queryFn: () => endpoints.graphSubgraph(entityId!, depth),
    enabled: online && Boolean(entityId),
    retry: 2,
  });
}
