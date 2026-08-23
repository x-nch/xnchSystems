"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { Node } from "@xyflow/react";
import { cn } from "@/lib/utils/cn";

export type CoreNodeData = {
  status?: "ok" | "degraded" | "offline";
};

const statusMeta = {
  ok: {
    label: "gateway ok",
    border: "border-[var(--state-healthy)]",
    dot: "bg-[var(--state-healthy)]",
    text: "text-emerald-300",
  },
  degraded: {
    label: "gateway degraded",
    border: "border-[var(--state-degraded)]",
    dot: "bg-[var(--state-degraded)]",
    text: "text-amber-300",
  },
  offline: {
    label: "gateway offline",
    border: "border-[var(--state-offline)]",
    dot: "bg-[var(--state-offline)]",
    text: "text-muted-foreground",
  },
} as const;

export function CoreNode({ data }: NodeProps<Node<CoreNodeData>>) {
  const status = data.status ?? "offline";
  const meta = statusMeta[status];

  return (
    <div className="relative flex h-[150px] w-[150px] items-center justify-center">
      <Handle
        type="source"
        position={Position.Top}
        style={{ top: "50%", left: "50%" }}
        className="!border-none !bg-transparent"
      />

      {/* Green halo — only when online, respects reduced-motion */}
      {status === "ok" && (
        <div
          className="pointer-events-none absolute inset-2 rounded-xl bg-[radial-gradient(circle,rgba(200,255,0,0.16),transparent_68%)] motion-halo"
          aria-hidden
        />
      )}
      {status === "degraded" && (
        <div
          className="pointer-events-none absolute inset-3 rounded-xl bg-[radial-gradient(circle,rgba(255,200,87,0.10),transparent_70%)]"
          aria-hidden
        />
      )}

      <div
        className={cn(
          "relative flex h-[110px] w-[110px] flex-col items-center justify-center rounded-xl border bg-card",
          meta.border,
          status === "offline" && "bg-[repeating-linear-gradient(45deg,var(--card),var(--card)_8px,var(--muted)_8px,var(--muted)_9px)]"
        )}
      >
        <div className="flex flex-col items-center gap-1">
          <span className="font-display text-[17px] font-bold tracking-[0.10em] text-foreground">xnch</span>
          <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.28em] text-muted-foreground">
            nexus
          </span>
        </div>
      </div>

      <div className="absolute -bottom-1 flex items-center gap-1.5 rounded-full border bg-card px-2.5 py-1">
        <span className={cn("h-2 w-2 rounded-full", meta.dot)} aria-hidden />
        <span className={cn("font-mono text-[11px] font-medium tracking-wider", meta.text)}>{meta.label}</span>
      </div>
    </div>
  );
}
