"use client";

import { useHealth } from "@/lib/api/hooks";
import { cn } from "@/lib/utils/cn";

export type ConnectionState = "online" | "degraded" | "offline" | "checking";

export function useConnectionState(): ConnectionState {
  const { data, isPending, isError } = useHealth();
  if (isError) return "offline";
  if (isPending) return "checking";
  if (data?.status === "ok") return "online";
  return "degraded";
}

const dotClass: Record<ConnectionState, string> = {
  online: "bg-success shadow-[0_0_8px] shadow-success/50",
  degraded: "bg-warning shadow-[0_0_8px] shadow-warning/50",
  offline: "bg-destructive shadow-[0_0_8px] shadow-destructive/50",
  checking: "bg-muted-foreground animate-pulse",
};

const labelClass: Record<ConnectionState, string> = {
  online: "text-emerald-400",
  degraded: "text-amber-400",
  offline: "text-red-400",
  checking: "text-muted-foreground",
};

const labelText: Record<ConnectionState, string> = {
  online: "gateway online",
  degraded: "gateway degraded",
  offline: "gateway offline",
  checking: "checking…",
};

export function ConnectionStatus({
  className,
  showLabel = true,
}: {
  className?: string;
  showLabel?: boolean;
}) {
  const state = useConnectionState();
  return (
    <span
      className={cn("inline-flex items-center gap-2", className)}
      title={labelText[state]}
    >
      <span className={cn("h-2 w-2 rounded-full", dotClass[state])} />
      {showLabel && (
        <span className={cn("text-xs font-medium", labelClass[state])}>
          {labelText[state]}
        </span>
      )}
    </span>
  );
}
