"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { endpoints } from "@/lib/api/endpoints";
import type { McpCallRequest } from "@/lib/api/types";

const HEALTH_MS = 5_000;
const SURFACE_MS = 15_000;

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: endpoints.health,
    refetchInterval: HEALTH_MS,
    retry: false,
  });
}

export function useSystemState() {
  return useQuery({
    queryKey: ["system-state"],
    queryFn: endpoints.systemState,
    refetchInterval: 30_000,
    retry: false,
  });
}

export function useCapabilities() {
  return useQuery({
    queryKey: ["capabilities"],
    queryFn: endpoints.capabilities,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useSystemPrompt() {
  return useQuery({
    queryKey: ["system-prompt"],
    queryFn: endpoints.systemPrompt,
    staleTime: 60_000,
    retry: false,
  });
}

export function useMcpTools(actorRole: string) {
  return useQuery({
    queryKey: ["mcp-tools", actorRole],
    queryFn: () => endpoints.mcpTools(actorRole),
    staleTime: 60_000,
    retry: false,
  });
}

export function useMcpServers() {
  return useQuery({
    queryKey: ["mcp-servers"],
    queryFn: endpoints.mcpServers,
    staleTime: 60_000,
    retry: false,
  });
}

export function useMemorySurface() {
  return useQuery({
    queryKey: ["memory-surface"],
    queryFn: endpoints.memorySurface,
    refetchInterval: SURFACE_MS,
    retry: false,
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
