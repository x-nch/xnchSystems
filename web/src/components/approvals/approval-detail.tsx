"use client";

import { useState } from "react";
import { cn } from "@/lib/utils/cn";
import type { HitlRequest } from "@/lib/approvals/types";
import { useApprovalStore } from "@/lib/stores/approval-store";
import { useConnectionState } from "@/components/layout/connection-status";

function formatIso(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export function ApprovalDetail({
  req,
  onClose,
}: {
  req: HitlRequest | null;
  onClose: () => void;
}) {
  const decide = useApprovalStore((s) => s.decide);
  const connection = useConnectionState();
  const offline = connection === "offline";
  const [rejectNote, setRejectNote] = useState("");
  const [showNote, setShowNote] = useState(false);

  if (!req) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
        <span className="text-sm text-muted-foreground">Select a request to review</span>
        <span className="max-w-[28ch] text-xs leading-5 text-muted-foreground/70">
          Approvals are the HITL gate — every consequential action waits here until you approve or reject it.
        </span>
      </div>
    );
  }

  const isPending = req.status === "pending";

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <button
          onClick={onClose}
          className="inline-flex h-7 items-center justify-center rounded-md border border-border px-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted md:hidden"
        >
          ← Back
        </button>
        <span className="font-mono text-xs text-muted-foreground">{req.id}</span>
        <span
          className={cn(
            "ml-auto rounded-md border px-2 py-1 text-xs font-medium",
            req.status === "pending"
              ? "border-[var(--state-attention)] bg-[var(--accent-subtle)] text-[var(--accent)]"
              : req.status === "approved"
                ? "border-[var(--state-healthy)] bg-emerald-500/10 text-emerald-300"
                : req.status === "rejected"
                  ? "border-[var(--state-destructive)] bg-red-500/10 text-red-300"
                  : "border-[var(--state-offline)] bg-muted text-muted-foreground"
          )}
        >
          {req.status}
        </span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-6 p-4">
          {/* Title */}
          <div>
            <h2 className="font-display text-[15px] font-semibold leading-6 text-foreground">
              {req.action.summary}
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Agent <span className="font-mono text-foreground">{req.agent_id}</span>
              {req.goal_label ? (
                <>
                  {" "}
                  · Goal <span className="font-mono text-foreground">{req.goal_label}</span>
                </>
              ) : null}{" "}
              · Policy <span className="font-mono text-foreground">{req.policy_version}</span>
            </p>
          </div>

          {/* Proposed action */}
          <div className="overflow-hidden rounded-xl border border-border bg-code-bg">
            <div className="border-b border-border bg-card px-3 py-2 text-xs font-medium text-muted-foreground">
              Proposed action
            </div>
            <div className="p-3">
              <div className="grid gap-2 font-mono text-xs">
                <div className="flex gap-2">
                  <span className="text-muted-foreground">kind:</span>
                  <span className="text-foreground">{req.action.kind}</span>
                </div>
                {req.action.target && (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">target:</span>
                    <span className="text-foreground">{req.action.target}</span>
                  </div>
                )}
                {req.action.args != null && (
                  <div className="flex gap-2">
                    <span className="text-muted-foreground">args:</span>
                    <span className="break-all text-foreground">
                      {typeof req.action.args === "string"
                        ? (req.action.args as string)
                        : JSON.stringify(req.action.args as unknown)}
                    </span>
                  </div>
                )}
              </div>
              {req.action.preview && (
                <pre className="mt-3 max-h-[220px] overflow-auto rounded-lg border border-border bg-background p-3 font-mono text-xs leading-5 text-muted-foreground">
                  {req.action.preview}
                </pre>
              )}
            </div>
          </div>

          {/* Provenance */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Provenance</h3>
            <div className="mt-2 grid gap-1.5 rounded-xl border border-border bg-card p-3 text-xs leading-5">
              <div className="flex justify-between gap-4">
                <span className="text-muted-foreground">Agent</span>
                <span className="font-mono text-foreground">{req.agent_id}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-muted-foreground">Goal</span>
                <span className="font-mono text-foreground">{req.goal_id ?? "—"}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-muted-foreground">Trigger</span>
                <span className="font-mono text-foreground">
                  {req.trigger ? `${req.trigger.kind}:${req.trigger.id}` : "—"}
                </span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-muted-foreground">Requested</span>
                <span className="font-mono text-foreground">{formatIso(req.created_at)}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-muted-foreground">Expires</span>
                <span className="font-mono text-foreground">{formatIso(req.expires_at)}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-muted-foreground">Policy</span>
                <span className="font-mono text-foreground">{req.policy_version}</span>
              </div>
            </div>
          </div>

          {/* Risks */}
          {req.risk_notes && req.risk_notes.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Risks / policy notes</h3>
              <ul className="mt-2 list-disc space-y-1 rounded-xl border border-[var(--state-degraded)] bg-amber-500/5 p-3 pl-6 text-xs leading-5 text-amber-200/90">
                {req.risk_notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Decision */}
          <div className="rounded-xl border border-border bg-card p-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Decision</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                onClick={() => decide(req.id, "approve")}
                disabled={!isPending || offline}
                className="btn-accent inline-flex h-9 items-center justify-center rounded-md bg-accent px-4 text-sm font-semibold text-accent-foreground hover:bg-accent/90 disabled:opacity-40"
              >
                Approve and execute
              </button>
              <button
                onClick={() => decide(req.id, "reject", showNote ? rejectNote : undefined)}
                disabled={!isPending || offline}
                className="motion-press inline-flex h-9 items-center justify-center rounded-md border border-border px-4 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-40"
              >
                Reject
              </button>
              <button
                onClick={() => setShowNote((v) => !v)}
                disabled={!isPending}
                className="inline-flex h-9 items-center justify-center rounded-md px-3 text-sm text-muted-foreground hover:text-foreground disabled:opacity-40"
              >
                {showNote ? "Hide note" : "Reject with note…"}
              </button>
            </div>
            {showNote && (
              <textarea
                value={rejectNote}
                onChange={(e) => setRejectNote(e.target.value)}
                placeholder="Optional note for audit log…"
                rows={3}
                className="mt-3 w-full rounded-md border border-border bg-background p-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
              />
            )}
            {offline && isPending && (
              <p className="mt-2 text-xs text-muted-foreground">Gateway offline — decisions are disabled.</p>
            )}
            {!isPending && (
              <p className="mt-2 text-xs text-muted-foreground">
                This request is {req.status}. Use Undo within 8s if this was a mistake (see queue toast).
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
