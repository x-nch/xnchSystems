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
        "group node-drift relative flex w-[140px] cursor-pointer flex-col items-center gap-1.5 rounded-xl border px-3 py-2.5 backdrop-blur transition-all",
        !online && "opacity-45 saturate-50 hover:opacity-70",
        online && "hover:scale-[1.04] hover:bg-card",
        data.active
          ? "node-active border-amber-400/40 bg-card/95"
          : data.alert
            ? "glow-border-gold border-amber-400/30 bg-card/85"
            : online
              ? "glow-border border-cyan-300/20 bg-card/85"
              : "border-border/40 bg-card/50"
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
            ? "bg-amber-400/15 text-amber-300"
            : data.alert
              ? "bg-amber-400/15 text-amber-300"
              : online
                ? "bg-accent/10 text-accent"
                : "bg-muted/40 text-muted-foreground"
        )}
      >
        <Icon className="h-4.5 w-4.5" />
      </div>

      <div className="flex flex-col items-center gap-0.5 text-center">
        <span
          className={cn(
            "font-mono text-[12px] font-semibold tracking-tight",
            data.active || data.alert
              ? "glow-text-gold text-amber-200"
              : online
                ? "glow-text text-cyan-100"
                : "text-muted-foreground"
          )}
        >
          {data.label}
        </span>
        <span className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          {data.desc}
        </span>
      </div>

      {data.meta && (
        <span
          className={cn(
            "mt-0.5 rounded-full border px-1.5 py-px font-mono text-[9px]",
            data.active
              ? "border-amber-400/30 bg-amber-400/10 text-amber-200"
              : online
                ? "border-cyan-300/20 bg-accent/5 text-cyan-200/80"
                : "border-border bg-muted/70 text-muted-foreground"
          )}
        >
          {data.meta}
        </span>
      )}
    </div>
  );
}
