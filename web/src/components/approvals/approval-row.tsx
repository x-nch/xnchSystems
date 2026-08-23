"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils/cn";
import type { HitlRequest } from "@/lib/approvals/types";
import { useApprovalStore } from "@/lib/stores/approval-store";
import { useConnectionState } from "@/components/layout/connection-status";

function waitingLabel(createdAt: string): string {
  const diff = Date.now() - new Date(createdAt).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `Waiting ${mins}m`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `Waiting ${h}h ${m}m`;
}

function expiresLabel(expiresAt: string | null): string | null {
  if (!expiresAt) return null;
  const diff = new Date(expiresAt).getTime() - Date.now();
  const mins = Math.round(diff / 60000);
  if (mins < 0) return `Overdue by ${Math.abs(mins)}m`;
  if (mins < 60) return `Expires in ${mins}m`;
  const h = Math.floor(mins / 60);
  return `Expires in ${h}h ${mins % 60}m`;
}

function isOverdue(req: HitlRequest): boolean {
  if (!req.expires_at) return false;
  return new Date(req.expires_at).getTime() < Date.now();
}

function isDegraded(req: HitlRequest): boolean {
  const age = Date.now() - new Date(req.created_at).getTime();
  return age > 2 * 60 * 60 * 1000;
}

export function ApprovalRow({
  req,
  selected,
  onSelect,
  index = 0,
  onDecide,
}: {
  req: HitlRequest;
  selected: boolean;
  onSelect: () => void;
  index?: number;
  /** P4: route to API when provided; local store fallback otherwise. */
  onDecide?: (id: string, action: "approve" | "reject") => void;
}) {
  const storeDecide = useApprovalStore((s) => s.decide);
  const decide = (id: string, action: "approve" | "reject") =>
    onDecide ? onDecide(id, action) : storeDecide(id, action);
  const connection = useConnectionState();
  const gatewayOffline = connection === "offline";
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 60_000);
    return () => clearInterval(id);
  }, []);

  const overdue = isOverdue(req);
  const degraded = isDegraded(req) && !overdue;
  const border =
    overdue || req.status === "pending"
      ? degraded
        ? "border-[var(--state-degraded)]"
        : "border-[var(--state-attention)]"
      : "border-border";

  // Left accent bar: solid chartreuse for attention, degraded amber for old
  const accentBar =
    overdue || req.status === "pending"
      ? degraded
        ? "bg-[var(--state-degraded)]"
        : "bg-[var(--accent)]"
      : "bg-transparent";

  const isPending = req.status === "pending";

  return (
    <div
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      data-selected={selected ? "true" : "false"}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      style={{ ["--stagger-index" as string]: String(index) } as React.CSSProperties}
      className={cn(
        "motion-row-enter motion-hover-lift group relative flex overflow-hidden rounded-xl border bg-card text-left",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60",
        border,
        selected ? "bg-[rgba(200,255,0,0.06)]" : "hover:bg-muted/40",
        isPending ? "border-l-0" : ""
      )}
    >
      {/* Left bar */}
      <div className={cn("w-1 shrink-0", accentBar)} aria-hidden />

      <div className="min-w-0 flex-1 px-4 py-3">
        {/* Top meta */}
        <div className="flex flex-wrap items-center gap-2 text-[11px] leading-none">
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-1.5 py-1 font-medium",
              isPending
                ? degraded
                  ? "border-[var(--state-degraded)] bg-amber-500/10 text-amber-300"
                  : "border-[var(--state-attention)] bg-[var(--accent-subtle)] text-[var(--accent)]"
                : "border-border bg-muted text-muted-foreground"
            )}
          >
            <span
              className={cn(
                "h-2 w-2 rounded-sm",
                isPending
                  ? degraded
                    ? "bg-[var(--state-degraded)]"
                    : "bg-[var(--accent)]"
                  : "bg-muted-foreground"
              )}
              aria-hidden
            />
            {req.action.kind === "exec_tool"
              ? "EXECUTE TOOL"
              : req.action.kind === "write_file"
                ? "WRITE FILE"
                : req.action.kind === "send_email"
                  ? "SEND EMAIL"
                  : req.action.kind.toUpperCase().replace("_", " ")}
          </span>

          <span className="text-muted-foreground">·</span>
          <span className="font-mono text-muted-foreground">agent:{req.agent_id}</span>
          {req.goal_label && (
            <>
              <span className="text-muted-foreground">·</span>
              <span className="truncate rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                {req.goal_label}
              </span>
            </>
          )}
          <span className="ml-auto font-mono text-muted-foreground">
            {waitingLabel(req.created_at)} · {expiresLabel(req.expires_at) ?? "no expiry"} {overdue && "· overdue"}
          </span>
        </div>

        {/* Title */}
        <div className="mt-2 flex items-center gap-2">
          <span className="truncate font-[Inter] text-[13px] font-medium leading-5 text-foreground">
            {req.action.summary}
          </span>
          {req.action.target && (
            <span className="hidden truncate rounded bg-code-bg px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground md:inline">
              {req.action.target}
            </span>
          )}
        </div>

        {/* Preview */}
        {req.action.preview && (
          <p className="mt-1 line-clamp-2 text-[12px] leading-5 text-muted-foreground">
            {req.action.preview}
          </p>
        )}

        {/* Actions */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              decide(req.id, "approve");
            }}
            disabled={!isPending || gatewayOffline}
            className={cn(
              "btn-accent inline-flex h-7 items-center justify-center rounded-md bg-accent px-3 text-[12px] font-semibold text-accent-foreground hover:bg-accent/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 disabled:pointer-events-none disabled:opacity-40",
            )}
            aria-label={`Approve ${req.id}`}
          >
            Approve
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              decide(req.id, "reject");
            }}
            disabled={!isPending || gatewayOffline}
            className="motion-press inline-flex h-7 items-center justify-center rounded-md border border-border bg-transparent px-3 text-[12px] font-medium text-foreground hover:bg-muted disabled:opacity-40"
            aria-label={`Reject ${req.id}`}
          >
            Reject
          </button>
          <button
            onClick={onSelect}
            className="ml-auto inline-flex h-7 items-center justify-center rounded-md px-2 text-[12px] font-medium text-muted-foreground hover:text-foreground"
          >
            View detail →
          </button>
          {gatewayOffline && isPending && (
            <span className="text-[11px] text-muted-foreground">(offline — actions disabled)</span>
          )}
        </div>
      </div>
    </div>
  );
}
