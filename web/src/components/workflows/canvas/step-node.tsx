"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { ShieldAlert, Zap } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import {
  ELEVATED_KINDS,
  KIND_LABELS,
  type StepFlowNode,
} from "@/lib/workflows/graph";
import { KIND_ICONS } from "./step-icons";

export function StepNode({ data, selected }: NodeProps<StepFlowNode>) {
  const step = data.step;
  const Icon = KIND_ICONS[step.kind];
  const gated = step.requiresApproval;
  const elevated = ELEVATED_KINDS.has(step.kind);

  return (
    <div
      aria-label={`${KIND_LABELS[step.kind]} step: ${step.summary}. ${gated ? "Requires approval" : "Runs automatically"}${elevated ? ". Server enforces approval for this kind." : ""}`}
      className={cn(
        "flex min-w-[220px] max-w-[260px] flex-col gap-1.5 rounded-xl border bg-card px-3 py-2.5",
        selected
          ? "border-[var(--accent)] shadow-[0_0_0_2px_var(--accent-subtle)]"
          : "border-border hover:border-[var(--state-offline)]"
      )}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!h-2.5 !w-2.5 !rounded-full !border-[1.5px] !border-[var(--state-attention)] !bg-[var(--muted)]"
      />
      <div className="flex items-center gap-1.5">
        <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
        <span className="rounded border border-border bg-muted px-1 py-px font-mono text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">
          {KIND_LABELS[step.kind]}
        </span>
        <span className="flex-1" />
        {gated ? (
          <span className="flex items-center gap-0.5 rounded border border-[var(--state-attention)] bg-[var(--accent-subtle)] px-1 py-px font-mono text-[9px] font-bold uppercase text-[var(--accent)]">
            <ShieldAlert className="h-2.5 w-2.5" aria-hidden /> Gated
          </span>
        ) : (
          <span className="flex items-center gap-0.5 rounded border border-border px-1 py-px font-mono text-[9px] uppercase text-muted-foreground">
            <Zap className="h-2.5 w-2.5" aria-hidden /> Auto
          </span>
        )}
      </div>
      <p className="line-clamp-2 text-[13px] font-medium leading-tight text-foreground">
        {step.summary}
      </p>
      {step.target && (
        <p className="truncate rounded bg-code-bg px-1 py-0.5 font-mono text-[10px] text-muted-foreground">
          {step.target}
        </p>
      )}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2.5 !w-2.5 !rounded-full !border-[1.5px] !border-[var(--state-attention)] !bg-[var(--muted)]"
      />
    </div>
  );
}
