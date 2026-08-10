import { apiRequest } from "@/lib/api/client";
import type {
  CapabilitiesResponse,
  ChatResponse,
  ChatRequest,
  HealthResponse,
  McpCallRequest,
  McpCallResponse,
  McpServersResponse,
  McpToolsResponse,
  MemoryRecallRequest,
  MemoryRecallResult,
  SessionInitRequest,
  SurfaceEvent,
  SystemStateResponse,
} from "@/lib/api/types";

export const endpoints = {
  health: () => apiRequest<HealthResponse>("/health"),
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
