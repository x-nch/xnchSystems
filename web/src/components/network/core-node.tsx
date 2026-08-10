"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { Node } from "@xyflow/react";
import { cn } from "@/lib/utils/cn";
import { CoreParticles } from "./core-particles";

export type CoreNodeData = {
  status?: "ok" | "degraded" | "offline";
};

export function CoreNode({ data }: NodeProps<Node<CoreNodeData>>) {
  const status = data.status ?? "offline";
  const statusColor =
    status === "ok"
      ? "text-emerald-300"
      : status === "degraded"
        ? "text-amber-300"
        : "text-red-300";

  return (
    <div className="relative flex h-[150px] w-[150px] items-center justify-center">
      <Handle
        type="source"
        position={Position.Top}
        style={{ top: "50%", left: "50%" }}
        className="!border-none !bg-transparent"
      />

      <div className="orb-halo absolute inset-2 rounded-full bg-[radial-gradient(circle,rgba(34,211,238,0.28),transparent_70%)]" />

      <div
        className={cn(
          "relative flex h-[104px] w-[104px] flex-col items-center justify-center overflow-hidden rounded-full border glow-border",
          status === "ok"
            ? "border-cyan-300/40"
            : "border-red-400/40"
        )}
        style={{
          background:
            "radial-gradient(circle at 35% 30%, rgba(34,211,238,0.45), rgba(3,7,18,0.97) 62%)",
        }}
      >
        <CoreParticles />
        <div className="relative z-10 flex flex-col items-center">
          <span className="glow-text font-mono text-[17px] font-bold tracking-[0.12em] text-cyan-100">
            xnch
          </span>
          <span className="text-[8px] font-semibold uppercase tracking-[0.34em] text-amber-300/90">
            nexus
          </span>
        </div>
      </div>

      <div className="absolute -bottom-1.5 flex items-center gap-1 rounded-full border border-border bg-card/90 px-2 py-0.5">
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            status === "ok" ? "bg-success" : status === "degraded" ? "bg-warning" : "bg-destructive"
          )}
          style={{ boxShadow: "0 0 8px currentColor" }}
        />
        <span className={cn("font-mono text-[9px] uppercase tracking-wider", statusColor)}>
          {status}
        </span>
      </div>
    </div>
  );
}
