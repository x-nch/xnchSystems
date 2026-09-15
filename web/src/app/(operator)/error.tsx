"use client";

import { AlertTriangle, CloudOff, RefreshCw, Settings, ShieldAlert } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { useUiStore } from "@/lib/stores/ui-store";
import { Button } from "@/components/ui/button";

type StatusCase = "auth" | "gateway" | "generic";

function caseOf(error: Error): StatusCase {
  if (error instanceof ApiError) {
    if (error.status === 401) return "auth";
    if (error.status === 0 || error.status === 502 || error.status === 503 || error.status === 504)
      return "gateway";
  }
  return "generic";
}

export default function OperatorError({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  const openSettings = () => useUiStore.getState().setSettingsOpen(true);
  const statusCase = caseOf(error);

  return (
    <div className="view-scroll mx-auto w-full max-w-3xl space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between gap-2 border-b border-border pb-2">
        <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-foreground">
          Render error
        </span>
        <span className="font-mono text-[11px] text-muted-foreground">
          {error instanceof ApiError ? `HTTP ${error.status}` : "unhandled"}
        </span>
      </div>

      {statusCase === "auth" && (
        <div className="overflow-hidden rounded-xl border border-[var(--state-attention)] bg-card">
          <div className="p-5">
            <div className="flex items-start gap-4">
              <ShieldAlert className="mt-0.5 h-8 w-8 shrink-0 text-[var(--state-attention)]" />
              <div className="space-y-2">
                <h2 className="text-lg font-semibold text-foreground">
                  Authorization rejected
                </h2>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  The gateway returned{" "}
                  <span className="font-mono text-foreground">HTTP 401</span> —
                  your identity was not accepted. Re-enter your actor ID, the
                  shared JWT secret, or a valid bearer token, then retry.
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 border-t border-border bg-muted/40 px-5 py-3">
            <Button size="sm" variant="outline" onClick={openSettings}>
              <Settings className="h-3.5 w-3.5" />
              Open settings
            </Button>
            <Button size="sm" onClick={reset}>
              <RefreshCw className="h-3.5 w-3.5" />
              Try again
            </Button>
          </div>
        </div>
      )}

      {statusCase === "gateway" && (
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          <div className="flex items-center gap-2 border-b border-[var(--state-offline)] bg-[var(--muted)] px-4 py-2 text-xs text-foreground">
            <span className="h-2 w-2 rounded-sm bg-[var(--state-offline)]" aria-hidden />
            Gateway offline — this view cannot load while xnch is unreachable.
          </div>
          <div className="p-5">
            <div className="flex items-start gap-4">
              <CloudOff className="mt-0.5 h-8 w-8 shrink-0 text-[var(--state-offline)]" />
              <div className="space-y-2">
                <h2 className="text-lg font-semibold text-foreground">
                  Gateway unreachable
                </h2>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  The request could not reach the xnch gateway. The controller
                  auto-refreshes when it comes back online.
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 border-t border-border bg-muted/40 px-5 py-3">
            <Button size="sm" onClick={reset}>
              <RefreshCw className="h-3.5 w-3.5" />
              Try again
            </Button>
          </div>
        </div>
      )}

      {statusCase === "generic" && (
        <div className="overflow-hidden rounded-xl border border-[var(--state-destructive)] bg-card">
          <div className="p-5">
            <div className="flex items-start gap-4">
              <AlertTriangle className="mt-0.5 h-8 w-8 shrink-0 text-[var(--state-destructive)]" />
              <div className="space-y-2">
                <h2 className="text-lg font-semibold text-foreground">
                  This view hit an unexpected error
                </h2>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {error.message || "A render threw outside the normal request path."}
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 border-t border-border bg-muted/40 px-5 py-3">
            <Button size="sm" onClick={reset}>
              <RefreshCw className="h-3.5 w-3.5" />
              Try again
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}