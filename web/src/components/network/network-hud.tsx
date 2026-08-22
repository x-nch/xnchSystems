"use client";

import { useRouter } from "next/navigation";
import { CircuitBoard, ScanFace } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { Button } from "@/components/ui/button";
import { Waveform } from "./waveform";
import { useUiStore } from "@/lib/stores/ui-store";
import type { HealthResponse } from "@/lib/api/types";

export function NetworkHud({
  health,
  memoryCount,
  toolCount,
  activeCount,
  gatewayOk,
}: {
  health: HealthResponse | undefined;
  memoryCount: number;
  toolCount: number;
  activeCount: number;
  gatewayOk: boolean;
}) {
  const router = useRouter();
  const setPresenceTransitioning = useUiStore((s) => s.setPresenceTransitioning);
  const status = health?.status ?? "offline";

  const enterPresence = () => {
    setPresenceTransitioning(true);
    router.push("/presence");
  };

  return (
    <div className="pointer-events-none absolute inset-0 z-10 select-none">
      {/* Top-left title block */}
      <div className="absolute left-4 top-4 flex flex-col gap-2">
        <div className="hud-panel rounded-lg px-3 py-2">
          <div className="flex items-center gap-2">
            <CircuitBoard className="h-3.5 w-3.5 text-cyan-300" />
            <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.32em] text-cyan-200 glow-text">
              Agent Network
            </span>
          </div>
          <span className="mt-0.5 block text-[10px] text-muted-foreground">
            xnch control plane · live topology
          </span>
        </div>
        <Waveform className="h-6 w-32 opacity-60" />
      </div>

      {/* Top-right status strip */}
      <div className="absolute right-16 top-4 hidden items-center gap-2 font-mono text-[9px] uppercase tracking-widest text-muted-foreground/70 md:flex">
        <span
          className={cn(
            "rounded border px-1.5 py-0.5",
            gatewayOk
              ? "border-cyan-300/30 text-cyan-200/80"
              : "border-border/60"
          )}
        >
          {gatewayOk ? `${activeCount} online` : "offline"}
        </span>
      </div>

      {/* Bottom-left readouts */}
      <div className="absolute bottom-4 left-4 flex flex-wrap items-center gap-2 font-mono text-[9px] text-muted-foreground">
        <div className="hud-panel flex items-center gap-1.5 rounded-md px-2 py-1">
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              status === "ok" ? "bg-success" : status === "degraded" ? "bg-warning" : "bg-destructive"
            )}
            style={{ boxShadow: "0 0 8px currentColor" }}
          />
          gateway {status}
        </div>
        <div className="hud-panel rounded-md px-2 py-1">
          surface {memoryCount}
        </div>
        <div className="hud-panel rounded-md px-2 py-1">
          tools {toolCount}
        </div>
        <div className="hidden hud-panel rounded-md px-2 py-1 sm:block">
          {health?.version ?? "—"}
        </div>
      </div>

      {/* Presence trigger */}
      <div className="pointer-events-auto absolute bottom-4 right-4">
        <Button
          onClick={enterPresence}
          size="sm"
          className="glow-border-gold border border-amber-400/40 bg-card/80 text-amber-200 backdrop-blur hover:bg-amber-400/10"
        >
          <ScanFace className="h-3.5 w-3.5" />
          Presence
        </Button>
      </div>
    </div>
  );
}
