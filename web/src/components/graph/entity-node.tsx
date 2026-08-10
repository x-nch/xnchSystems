"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { Node } from "@xyflow/react";
import { cn } from "@/lib/utils/cn";
import { colorForEntityType } from "./force-layout";

export type EntityNodeData = {
  label: string;
  entityType: string;
  degree?: number;
  selected?: boolean;
  connected?: boolean;
  focused?: boolean;
  dimmed?: boolean;
  hovered?: boolean;
};

export function EntityNode({ data }: NodeProps<Node<EntityNodeData>>) {
  const color = colorForEntityType(data.entityType);
  const selected = data.selected;
  const connected = data.connected && !selected;
  const hot = selected || data.focused || data.hovered || connected;

  return (
    <div
      className={cn(
        "group flex w-[108px] flex-col items-center gap-1.5 transition-all duration-300",
        data.dimmed && "opacity-[0.2]",
        selected && "scale-110 z-10",
        connected && "scale-[1.04]",
        data.hovered && !selected && "scale-105"
      )}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!top-3 !h-2 !w-2 !border-cyan-300/40 !bg-cyan-300/30 !opacity-100"
        style={{ boxShadow: hot ? `0 0 6px ${color}` : undefined }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className="!bottom-8 !h-2 !w-2 !border-cyan-300/40 !bg-cyan-300/30 !opacity-100"
        style={{ boxShadow: hot ? `0 0 6px ${color}` : undefined }}
      />

      {/* Outer glow ring — selected */}
      {selected && (
        <div
          className="node-active pointer-events-none absolute left-1/2 top-3 h-10 w-10 -translate-x-1/2 rounded-full"
          style={{
            boxShadow: `0 0 28px 8px ${color}66, 0 0 0 2px rgba(245,197,24,0.5)`,
          }}
          aria-hidden
        />
      )}

      {/* Connected neighbor ring */}
      {connected && (
        <div
          className="pointer-events-none absolute left-1/2 top-3 h-10 w-10 -translate-x-1/2 rounded-full"
          style={{
            boxShadow: `0 0 18px 4px ${color}44, 0 0 0 1px rgba(34,211,238,0.35)`,
          }}
          aria-hidden
        />
      )}

      {/* Orb */}
      <div className="relative flex h-10 w-10 items-center justify-center">
        <div
          className={cn(
            "absolute inset-0 rounded-full transition-all duration-300",
            (selected || data.focused) && "orb-halo"
          )}
          style={{
            background: selected
              ? `radial-gradient(circle, ${color}55 0%, rgba(245,197,24,0.15) 45%, transparent 72%)`
              : `radial-gradient(circle, ${color}33 0%, transparent 70%)`,
          }}
        />
        <div
          className={cn(
            "relative rounded-full border transition-all duration-300",
            selected
              ? "h-6 w-6 border-amber-300/70"
              : connected
                ? "h-5 w-5 border-cyan-300/50"
                : "h-5 w-5 border-cyan-300/25"
          )}
          style={{
            background: `radial-gradient(circle at 30% 25%, ${color}, #030712 80%)`,
            boxShadow: selected
              ? `0 0 24px ${color}, 0 0 12px rgba(245,197,24,0.6), 0 0 0 2px ${color}55`
              : connected
                ? `0 0 16px ${color}88, 0 0 0 1px rgba(34,211,238,0.4)`
                : `0 0 10px ${color}44`,
          }}
        />
        {data.degree != null && data.degree > 0 && (
          <span
            className={cn(
              "absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full border px-0.5 font-mono text-[8px]",
              selected
                ? "border-amber-400/50 bg-amber-400/20 text-amber-100"
                : "border-cyan-300/20 bg-card/90 text-cyan-200"
            )}
          >
            {data.degree}
          </span>
        )}
      </div>

      {/* Label card */}
      <div
        className={cn(
          "w-full rounded-lg border px-1.5 py-1 text-center backdrop-blur-sm transition-all duration-300",
          selected
            ? "border-amber-400/50 bg-card/95 glow-border-gold"
            : connected
              ? "border-cyan-300/35 bg-card/90 glow-border"
              : "border-border/50 bg-card/80 hover:border-cyan-300/25 hover:bg-card/90"
        )}
      >
        <p
          className={cn(
            "line-clamp-2 font-mono text-[10px] font-semibold leading-snug",
            selected ? "text-amber-100 glow-text-gold" : "text-foreground"
          )}
          title={data.label}
        >
          {data.label}
        </p>
        <p
          className="mt-0.5 truncate font-mono text-[8px] uppercase tracking-wider"
          style={{ color: selected ? "#f5c518" : `${color}cc` }}
        >
          {data.entityType}
        </p>
      </div>
    </div>
  );
}
