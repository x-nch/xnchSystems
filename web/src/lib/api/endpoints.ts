import { apiRequest } from "@/lib/api/client";
import type {
  CapabilitiesResponse,
  ChatResponse,
  ChatRequest,
  HealthResponse,
  LlmStatusResponse,
  McpCallRequest,
  McpCallResponse,
  McpServersResponse,
  McpToolsResponse,
  MemoryRecallRequest,
  MemoryRecallResult,
  SessionInitRequest,
  SurfaceEvent,
  SystemStateResponse,
  GraphEntitiesPage,
  GraphRelationsPage,
  GraphSubgraph,
  GraphStats,
} from "@/lib/api/types";

export const endpoints = {
  health: () => apiRequest<HealthResponse>("/health"),
  llmStatus: () => apiRequest<LlmStatusResponse>("/system/llm-status"),
  systemState: () => apiRequest<SystemStateResponse>("/system/state"),
  capabilities: () => apiRequest<CapabilitiesResponse>("/nexi/capabilities"),
  systemPrompt: () => apiRequest<string>("/nexi/system-prompt"),
  chat: (body: ChatRequest) =>
    apiRequest<ChatResponse>("/nexi/chat", { method: "POST", body }),

  memoryRecall: (body: MemoryRecallRequest) =>
    apiRequest<MemoryRecallResult[]>("/nexi/memory/recall", {
      method: "POST",
      body,
    }),
  memorySurface: () => apiRequest<SurfaceEvent[]>("/nexi/memory/surface"),

  graphStats: () => apiRequest<GraphStats>("/memory/graph/stats"),
  graphEntities: (params?: {
    type?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }) =>
    apiRequest<GraphEntitiesPage>("/memory/graph/entities", {
      query: {
        type: params?.type,
        search: params?.search,
        limit: params?.limit,
        offset: params?.offset,
      },
    }),
  graphRelations: (params?: { limit?: number; offset?: number }) =>
    apiRequest<GraphRelationsPage>("/memory/graph/relations", {
      query: {
        limit: params?.limit,
        offset: params?.offset,
      },
    }),
  graphSubgraph: (entityId: string, depth: 1 | 2 = 1) =>
    apiRequest<GraphSubgraph>("/memory/graph/subgraph", {
      query: { entity_id: entityId, depth },
    }),

  mcpTools: (actorRole?: string) =>
    apiRequest<McpToolsResponse>("/mcp/tools", {
      headers: actorRole ? { "X-Actor-Role": actorRole } : {},
    }),
  mcpServers: () => apiRequest<McpServersResponse>("/mcp/servers"),
  mcpCall: (body: McpCallRequest) =>
    apiRequest<McpCallResponse>("/mcp/call", { method: "POST", body }),

  sessionInit: (body: SessionInitRequest) =>
    apiRequest<Record<string, unknown>>("/session/init", {
      method: "POST",
      body,
    }),
};
