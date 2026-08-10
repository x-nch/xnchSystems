"use client";

import {
  useCapabilities,
  useGatewayOnline,
  useHealth,
  useGraphStats,
  useMcpTools,
  useMemorySurface,
  useSystemState,
} from "@/lib/api/hooks";
import { useChatStore } from "@/lib/stores/chat-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import type { SubsystemId } from "@/lib/stores/ui-store";

export type SubsystemStatus = {
  online: boolean;
  active: boolean;
  meta?: string;
  alert?: boolean;
};

export function useSubsystemStatuses(): Record<SubsystemId, SubsystemStatus> & {
  memoryCount: number;
  toolCount: number;
  gatewayOk: boolean;
} {
  const gatewayOk = useGatewayOnline();
  const health = useHealth();
  const state = useSystemState();
  const capabilities = useCapabilities();
  const surface = useMemorySurface();
  const graphStats = useGraphStats();
  const actorRole = useSettingsStore((s) => s.actorRole);
  const mcpTools = useMcpTools(actorRole);
  const streamingId = useChatStore((s) => s.streamingConversationId);

  const memoryCount =
    surface.data && Array.isArray(surface.data)
      ? surface.data.filter((e) => e.priority >= 1).length
      : 0;
  const toolCount = mcpTools.data?.tools.length ?? 0;
  const surfaceTotal = surface.data?.length ?? 0;

  const systemOnline = gatewayOk && !health.isError;
  const policyOnline = gatewayOk && !state.isError && Boolean(state.data);
  const capabilitiesOnline =
    gatewayOk && !capabilities.isError && Boolean(capabilities.data);
  const memoryOnline = gatewayOk && !surface.isError;
  const graphEntityCount = graphStats.data?.entity_count ?? 0;
  const toolsOnline = gatewayOk && !mcpTools.isError && Boolean(mcpTools.data);
  const voiceOnline = capabilitiesOnline && Boolean(capabilities.data?.voice);

  return {
    gatewayOk,
    memoryCount,
    toolCount,
    memory: {
      online: memoryOnline,
      active: memoryCount > 0,
      meta: memoryOnline
        ? memoryCount > 0
          ? `${memoryCount} surfaced`
          : graphEntityCount > 0
            ? `${graphEntityCount} in graph`
            : surfaceTotal > 0
              ? `${surfaceTotal} events`
              : "online"
        : "offline",
      alert: memoryCount > 0,
    },
    tools: {
      online: toolsOnline,
      active: toolCount > 0,
      meta: toolsOnline
        ? toolCount > 0
          ? `${toolCount} ready`
          : "online"
        : "offline",
    },
    policy: {
      online: policyOnline,
      active: false,
      meta: policyOnline
        ? `v${state.data?.policy_version ?? "—"}`
        : "offline",
    },
    voice: {
      online: voiceOnline,
      active: false,
      meta: voiceOnline ? "PTT ready" : "offline",
    },
    capabilities: {
      online: capabilitiesOnline,
      active: false,
      meta: capabilitiesOnline ? "loaded" : "offline",
    },
    system: {
      online: systemOnline,
      active: false,
      meta: systemOnline ? health.data?.status ?? "ok" : "offline",
    },
    chat: {
      online: systemOnline,
      active: Boolean(streamingId),
      meta: streamingId ? "streaming" : systemOnline ? "ready" : "offline",
    },
  };
}
