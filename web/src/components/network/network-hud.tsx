"use client";

import { cn } from "@/lib/utils/cn";
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
  const status = health?.status ?? "offline";

  return (
    <div className="pointer-events-none absolute inset-0 z-10 select-none">
      {/* Top-left title block */}
      <div className="absolute left-4 top-4 flex flex-col gap-2">
        <div className="rounded-lg border border-border bg-card/90 px-3 py-2 backdrop-blur-sm">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-sm bg-[var(--state-healthy)]" aria-hidden />
            <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-foreground">
              Agent Network
            </span>
          </div>
          <span className="mt-0.5 block font-mono text-[11px] text-muted-foreground">
            xnch control plane · live topology
          </span>
        </div>
        <span className="font-mono text-[11px] text-muted-foreground">
          {gatewayOk ? "telemetry nominal" : "telemetry offline"}
        </span>
      </div>

      {/* Top-right status strip */}
      <div className="absolute right-16 top-4 hidden items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-muted-foreground md:flex">
        <span
          className={cn(
            "rounded-md border px-2 py-1",
            gatewayOk
              ? "border-[var(--state-healthy)] bg-emerald-500/10 text-emerald-300"
              : "border-[var(--state-offline)] bg-muted text-muted-foreground"
          )}
        >
          {gatewayOk ? `${activeCount} online` : "offline"}
        </span>
      </div>

      {/* Bottom-left readouts */}
      <div className="absolute bottom-4 left-4 flex flex-wrap items-center gap-2 font-mono text-[11px] text-muted-foreground">
        <div
          className={cn(
            "flex items-center gap-1.5 rounded-md border bg-card px-2 py-1",
            status === "ok"
              ? "border-[var(--state-healthy)]"
              : status === "degraded"
                ? "border-[var(--state-degraded)]"
                : "border-[var(--state-offline)]"
          )}
        >
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              status === "ok" ? "bg-[var(--state-healthy)]" : status === "degraded" ? "bg-[var(--state-degraded)]" : "bg-[var(--state-offline)]"
            )}
            aria-hidden
          />
          gateway {status}
        </div>
        <div className="rounded-md border border-border bg-card px-2 py-1">surface {memoryCount}</div>
        <div className="rounded-md border border-border bg-card px-2 py-1">tools {toolCount}</div>
        <div className="hidden rounded-md border border-border bg-card px-2 py-1 sm:block">{health?.version ?? "—"}</div>
      </div>
    </div>
  );
}
