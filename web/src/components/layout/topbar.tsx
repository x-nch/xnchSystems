"use client";

import { Settings, Cpu, Shield } from "lucide-react";
import { ConnectionStatus } from "@/components/layout/connection-status";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useHealth, useSystemState, useCapabilities } from "@/lib/api/hooks";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { authModeLabel } from "@/lib/auth/auth";

export function Topbar({ onOpenSettings }: { onOpenSettings: () => void }) {
  const health = useHealth();
  const systemState = useSystemState();
  const capabilities = useCapabilities();
  const { actorId, actorRole, authMode } = useSettingsStore();

  const modelName = capabilities.data?.summary ? "ornith" : "ornith";

  return (
    <header className="flex h-[var(--hud-topbar-height)] shrink-0 items-center gap-2 border-b border-border/80 bg-background/60 px-3 backdrop-blur-md supports-[backdrop-filter]:bg-background/40">
      <ConnectionStatus />

      <div className="flex-1" />

      <Tooltip>
        <TooltipTrigger asChild>
          <Badge tone="accent" className="cursor-default">
            <Cpu className="h-3 w-3" />
            {modelName}
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          Routed model via LiteLLM (classify_request → ornith)
        </TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger asChild>
          <Badge tone="muted" className="cursor-default font-mono">
            {actorId}@{actorRole}
          </Badge>
        </TooltipTrigger>
        <TooltipContent>Auth: {authModeLabel(authMode)} · actor id @ role</TooltipContent>
      </Tooltip>

      {systemState.data && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge tone="muted" className="cursor-default font-mono">
              <Shield className="h-3 w-3" />
              sv {systemState.data.system_state_version.slice(0, 8)}
            </Badge>
          </TooltipTrigger>
          <TooltipContent>
            system_state_version = {systemState.data.system_state_version}
            <br />
            policy_version = {systemState.data.policy_version}
          </TooltipContent>
        </Tooltip>
      )}

      {health.data && (
        <span className="hidden font-mono text-[11px] text-muted-foreground md:inline">
          v{health.data.version}
        </span>
      )}

      <button
        onClick={onOpenSettings}
        className="ml-1 inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
        aria-label="Settings"
      >
        <Settings className="h-4 w-4" />
      </button>
    </header>
  );
}
