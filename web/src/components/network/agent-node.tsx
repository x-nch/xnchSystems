"use client";

import { useRouter } from "next/navigation";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { Node } from "@xyflow/react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils/cn";

export type AgentNodeData = {
  label: string;
  desc: string;
  href: string;
  icon: LucideIcon;
  meta?: string;
  alert?: boolean;
  active?: boolean;
  online?: boolean;
};

export function AgentNode({ data }: NodeProps<Node<AgentNodeData>>) {
  const router = useRouter();
  const Icon = data.icon;
  const online = data.online ?? false;

  const navigate = () => router.push(data.href);

  // State-driven border — solid hex, ≥3:1 vs bg. No glow, no drift, no opacity-only state.
  const containerBorder = data.active
    ? "border-[var(--state-attention)] bg-card"
    : data.alert
      ? "border-[var(--state-degraded)] bg-card"
      : online
        ? "border-[var(--state-healthy)] bg-card"
        : "border-[var(--state-offline)] bg-card";

  // Offline is NOT opacity-45 — it's a distinct border + muted icon, still legible.
  return (
    <div
      onClick={navigate}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          navigate();
        }
      }}
      tabIndex={0}
      className={cn(
        "group relative flex w-[148px] cursor-pointer flex-col items-center gap-1.5 rounded-xl border px-3 py-3 transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60",
        "hover:bg-[var(--bg-raised)]",
        containerBorder,
        !online && "bg-muted/30"
      )}
      role="button"
      aria-label={`Open ${data.label}${online ? "" : " (offline)"}`}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{ top: "50%", left: "50%" }}
        className="!border-none !bg-transparent"
      />

      <div
        className={cn(
          "flex h-9 w-9 items-center justify-center rounded-lg",
          data.active
            ? "bg-[var(--accent-subtle)] text-[var(--accent)]"
            : data.alert
              ? "bg-amber-500/10 text-amber-300"
              : online
                ? "bg-emerald-500/10 text-emerald-300"
                : "bg-muted text-muted-foreground"
        )}
      >
        <Icon className="h-[18px] w-[18px]" />
      </div>

      <div className="flex flex-col items-center gap-0.5 text-center">
        <span
          className={cn(
            "font-mono text-[12px] font-semibold tracking-tight",
            data.active
              ? "text-[var(--accent)]"
              : data.alert
                ? "text-amber-200"
                : online
                  ? "text-foreground"
                  : "text-muted-foreground"
          )}
        >
          {data.label}
        </span>
        <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
          {data.desc}
        </span>
      </div>

      {data.meta && (
        <span
          className={cn(
            "mt-0.5 rounded-md border px-1.5 py-px font-mono text-[11px]",
            data.active
              ? "border-[var(--state-attention)] bg-[var(--accent-subtle)] text-[var(--accent)]"
              : data.alert
                ? "border-[var(--state-degraded)] bg-amber-500/10 text-amber-200"
                : online
                  ? "border-[var(--state-healthy)] bg-emerald-500/10 text-emerald-300"
                  : "border-[var(--state-offline)] bg-muted text-muted-foreground"
          )}
        >
          {data.meta}
        </span>
      )}
      {!online && <span className="font-mono text-[10px] text-muted-foreground">Offline</span>}
    </div>
  );
}
