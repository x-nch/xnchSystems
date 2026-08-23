"use client";
/* eslint-disable react-hooks/purity, react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */

import { useEffect, useMemo, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { cn } from "@/lib/utils/cn";
import { useApprovalStore } from "@/lib/stores/approval-store";
import { useServerApprovals, useWorkflowMutations } from "@/lib/hooks/use-workflows-api";
import { approvalDtoToHitl } from "@/lib/approvals/adapters";
import { useConnectionState } from "@/components/layout/connection-status";
import { ApprovalRow } from "./approval-row";
import { ApprovalDetail } from "./approval-detail";
import type { HitlRequest } from "@/lib/approvals/types";

type Filter = "pending" | "all" | "decided";

export function ApprovalQueue() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const lastDecision = useApprovalStore((s) => s.lastDecision);
  const localItems = useApprovalStore((s) => s.items);
  const undoLast = useApprovalStore((s) => s.undoLast);
  const dismissExpired = useApprovalStore((s) => s.dismissExpired);
  const connection = useConnectionState();
  const online = connection === "online";
  const serverQueue = useServerApprovals(online);
  const { decide: serverDecide } = useWorkflowMutations();
  const [filter, setFilter] = useState<Filter>("pending");
  const [showToast, setShowToast] = useState(false);

  // P4: gateway-first with local fallback while offline
  const items: HitlRequest[] = useMemo(() => {
    if (online && serverQueue.data) {
      const mapped = serverQueue.data.map(approvalDtoToHitl);
      return filter === "all" ? mapped : mapped.filter((r) => r.status === "pending");
    }
    return localItems;
  }, [online, serverQueue.data, localItems, filter]);

  /** Route decisions to the API when online; local store otherwise. */
  const decideRow = (id: string, action: "approve" | "reject", note?: string) => {
    if (online) {
      void serverDecide.mutateAsync({ id, body: { decision: action, note } });
      return;
    }
    useApprovalStore.getState().decide(id, action, note);
  };

  const selectedId = searchParams.get("selected");

  useEffect(() => {
    const id = setInterval(() => dismissExpired(), 60_000);
    return () => clearInterval(id);
  }, [dismissExpired]);

  useEffect(() => {
    if (lastDecision) {
      setShowToast(true);
      const t = setTimeout(() => setShowToast(false), 8000);
      return () => clearTimeout(t);
    }
  }, [lastDecision]);

  const pending = useMemo(() => items.filter((i) => i.status === "pending"), [items]);
  const overdueCount = useMemo(
    () =>
      pending.filter((i) => i.expires_at && new Date(i.expires_at).getTime() < Date.now()).length,
    [pending]
  );

  const filtered: HitlRequest[] = useMemo(() => {
    let base: HitlRequest[];
    if (filter === "pending") base = items.filter((i) => i.status === "pending");
    else if (filter === "decided") base = items.filter((i) => i.status !== "pending");
    else base = items;
    // overdue first, then newest waiting longest? spec: overdue at top then by waiting desc
    return [...base].sort((a, b) => {
      const aOver = a.expires_at ? new Date(a.expires_at).getTime() < Date.now() : false;
      const bOver = b.expires_at ? new Date(b.expires_at).getTime() < Date.now() : false;
      if (aOver !== bOver) return aOver ? -1 : 1;
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
    });
  }, [items, filter]);

  const selected = useMemo(
    () => items.find((i) => i.id === selectedId) ?? null,
    [items, selectedId]
  );

  const setSelected = (id: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (id) params.set("selected", id);
    else params.delete("selected");
    const qs = params.toString();
    router.replace(qs ? `?${qs}` : "?", { scroll: false });
  };

  // keyboard j/k in list
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "INPUT" || (e.target as HTMLElement)?.tagName === "TEXTAREA")
        return;
      if (e.key === "?" ) {
        // could open help — no-op for now
        return;
      }
      if (filtered.length === 0) return;
      const idx = filtered.findIndex((i) => i.id === selectedId);
      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        const next = idx < 0 ? 0 : Math.min(filtered.length - 1, idx + 1);
        setSelected(filtered[next].id);
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        const next = idx < 0 ? 0 : Math.max(0, idx - 1);
        setSelected(filtered[next].id);
      } else if (e.key === "Enter" && selectedId) {
        // already selected — focus detail approve button? handled elsewhere
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [filtered, selectedId, searchParams, router]);

  const gatewayState = connection;
  const isChecking = gatewayState === "checking";
  const isOffline = gatewayState === "offline";
  const isDegraded = gatewayState === "degraded";

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      {/* Top bar */}
      <div className="flex shrink-0 flex-wrap items-center gap-3 border-b border-border px-4 py-3">
        <h1 className="font-display text-xl font-semibold tracking-tight text-foreground">
          Approvals
        </h1>
        <span className="hidden items-center gap-2 text-xs text-muted-foreground md:inline-flex">
          <span className="inline-flex h-2 w-2 rounded-full bg-[var(--state-attention)]" aria-hidden />
          {isChecking ? (
            "Checking for approvals…"
          ) : pending.length === 0 ? (
            "No pending"
          ) : (
            <>
              {pending.length} pending{overdueCount > 0 ? ` · ${overdueCount} overdue` : ""}
            </>
          )}
        </span>
        <span className="flex-1" />
        <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1">
          {(["pending", "all", "decided"] as Filter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium",
                filter === f ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {f === "pending" ? "Pending" : f === "all" ? "All" : "Decided"}
            </button>
          ))}
        </div>
        <span className="hidden font-mono text-xs text-muted-foreground md:inline">⌘K</span>
      </div>

      {/* Gateway banners */}
      {isChecking && (
        <div className="flex items-center gap-2 border-b border-border bg-card px-4 py-2 text-xs text-muted-foreground">
          <span className="h-3 w-3 animate-pulse rounded-full bg-muted-foreground" aria-hidden />
          Checking gateway…
        </div>
      )}
      {isOffline && (
        <div className="flex items-center gap-2 border-b border-[var(--state-offline)] bg-[var(--muted)] px-4 py-2 text-xs text-foreground">
          <span className="h-2 w-2 rounded-sm bg-[var(--state-offline)]" aria-hidden />
          Gateway offline — approvals cannot be executed. Showing {pending.length} cached pending.
        </div>
      )}
      {isDegraded && (
        <div className="flex items-center gap-2 border-b border-[var(--state-degraded)] bg-amber-500/10 px-4 py-2 text-xs text-amber-200">
          <span className="h-0 w-0 border-x-[5px] border-b-[8px] border-x-transparent border-b-[var(--state-degraded)]" aria-hidden />
          Gateway degraded — actions may be slow.
        </div>
      )}

      {/* Content */}
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        {/* List */}
        <div className="flex min-h-0 flex-1 flex-col border-border md:max-w-[640px] md:border-r">
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {isChecking ? (
              <div className="space-y-3">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="h-28 animate-pulse rounded-xl border border-border bg-card" />
                ))}
              </div>
            ) : filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-[var(--state-healthy)] bg-card px-6 py-12 text-center">
                <span className="h-2 w-2 rounded-full bg-[var(--state-healthy)]" aria-hidden />
                <p className="text-sm font-medium text-foreground">No pending approvals</p>
                <p className="max-w-sm text-xs leading-5 text-muted-foreground">
                  System is idle or autonomous within policy. When an agent proposes a write, tool call, or email, it will
                  wait here for your decision.
                </p>
                <p className="font-mono text-xs text-muted-foreground/70">Press j/k to navigate · a approve · r reject · Enter detail</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filtered.map((req, i) => (
                  <ApprovalRow
                    key={req.id}
                    req={req}
                    index={i}
                    selected={req.id === selectedId}
                    onSelect={() => setSelected(req.id)}
                    onDecide={(id, action) => decideRow(id, action)}
                  />
                ))}
              </div>
            )}
          </div>
          {/* Footer helper */}
          <div className="hidden border-t border-border px-4 py-2 font-mono text-xs text-muted-foreground md:block">
            {filtered.length} items · j/k navigate · Enter open · <span className="text-foreground">? help</span>
          </div>
        </div>

        {/* Detail */}
        <div className={cn("flex min-h-0 flex-1 flex-col bg-background", !selected && "hidden md:flex")}>
          <div key={selected?.id ?? "empty"} className={selected ? "motion-pane-enter" : ""}>
            <ApprovalDetail req={selected} onClose={() => setSelected(null)} />
          </div>
        </div>
      </div>

      {/* Toast */}
      {showToast && lastDecision && (
        <div className="motion-toast pointer-events-auto fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 shadow-xl">
          <span className="text-sm text-foreground">
            {lastDecision.action === "approve" ? "Approved" : "Rejected"} {lastDecision.id}
          </span>
          <button
            onClick={() => {
              undoLast();
              setShowToast(false);
            }}
            className="rounded-md bg-accent px-3 py-1 text-xs font-semibold text-accent-foreground"
          >
            Undo
          </button>
          <span className="font-mono text-xs text-muted-foreground">(8s)</span>
        </div>
      )}
    </div>
  );
}
