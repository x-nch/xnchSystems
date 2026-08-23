"use client";

import { cn } from "@/lib/utils/cn";

export type BeaconState = "online" | "degraded" | "offline" | "checking";

const stateConfig: Record<BeaconState, { label: string; border: string; icon: React.ReactNode; sub: string }> = {
  online: {
    label: "Gateway online",
    border: "border-[var(--state-healthy)]",
    icon: <span className="h-2 w-2 rounded-full bg-[var(--state-healthy)] beacon-dot" aria-hidden />,
    sub: "operational",
  },
  degraded: {
    label: "Gateway degraded",
    border: "border-[var(--state-degraded)]",
    icon: (
      <span
        className="h-0 w-0 border-x-[6px] border-b-[10px] border-x-transparent border-b-[var(--state-degraded)]"
        aria-hidden
      />
    ),
    sub: "slow / retrying",
  },
  offline: {
    label: "Gateway offline",
    border: "border-[var(--state-offline)]",
    icon: <span className="h-2.5 w-2.5 rounded-sm bg-[var(--state-offline)]" aria-hidden />,
    sub: "no heartbeat",
  },
  checking: {
    label: "Checking…",
    border: "border-border",
    icon: <span className="h-2 w-2 animate-pulse rounded-full bg-muted-foreground" aria-hidden />,
    sub: "…",
  },
};

export function StatusBeacon({
  state,
  version,
  lastSeen,
  className,
}: {
  state: BeaconState;
  version?: string;
  lastSeen?: string;
  className?: string;
}) {
  const cfg = stateConfig[state];

  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-xl border bg-card px-3 py-2",
        cfg.border,
        state === "offline" && "bg-[repeating-linear-gradient(45deg,var(--card),var(--card)_6px,var(--muted)_6px,var(--muted)_7px)]",
        className
      )}
      role="status"
      aria-live="polite"
      aria-label={cfg.label}
    >
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-background">
        {cfg.icon}
      </div>
      <div className="min-w-0 flex flex-col">
        <span
          className={cn(
            "text-xs font-semibold tracking-tight",
            state === "online"
              ? "text-emerald-300"
              : state === "degraded"
                ? "text-amber-300"
                : state === "offline"
                  ? "text-muted-foreground"
                  : "text-muted-foreground"
          )}
        >
          {cfg.label}
        </span>
        <span className="truncate font-mono text-xs text-muted-foreground">
          {state === "offline" && lastSeen ? `Last seen ${lastSeen}` : version ?? cfg.sub}
        </span>
      </div>
      {/* subtle dot breathe only when online — CSS handles reduced-motion */}
      <style>{`
        @media (prefers-reduced-motion: no-preference) {
          .beacon-dot { animation: beacon-breathe 1.5s ease-in-out infinite; }
          @keyframes beacon-breathe { 0%,100% { opacity: 1 } 50% { opacity: 0.6 } }
        }
      `}</style>
    </div>
  );
}
