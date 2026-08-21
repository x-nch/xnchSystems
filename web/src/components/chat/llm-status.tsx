"use client";

import { useGatewayOnline, useLlmStatus } from "@/lib/api/hooks";
import { cn } from "@/lib/utils/cn";

export type LlmState = "available" | "unavailable" | "checking" | "hidden";

export function useLlmState(): LlmState {
  const gatewayOnline = useGatewayOnline();
  const { data, isPending, isError } = useLlmStatus();
  if (!gatewayOnline) return "hidden";
  if (isPending) return "checking";
  if (isError) return "unavailable";
  return data?.available ? "available" : "unavailable";
}

const dotClass: Record<LlmState, string> = {
  available: "bg-success shadow-[0_0_8px] shadow-success/50",
  unavailable: "bg-destructive shadow-[0_0_8px] shadow-destructive/50",
  checking: "bg-muted-foreground animate-pulse",
  hidden: "",
};

const labelClass: Record<LlmState, string> = {
  available: "text-emerald-400",
  unavailable: "text-red-400",
  checking: "text-muted-foreground",
  hidden: "",
};

const labelText: Record<LlmState, string> = {
  available: "llm available",
  unavailable: "llm unavailable",
  checking: "checking…",
  hidden: "",
};

export function LlmStatus({ className }: { className?: string }) {
  const state = useLlmState();
  const { data } = useLlmStatus();
  const title =
    state === "available" && data?.latency_ms != null
      ? `${data.model} · ${data.latency_ms}ms`
      : labelText[state];
  if (state === "hidden") return null;
  return (
    <span className={cn("inline-flex items-center gap-2", className)} title={title}>
      <span className={cn("h-2 w-2 rounded-full", dotClass[state])} />
      <span className={cn("text-xs font-medium", labelClass[state])}>
        {labelText[state]}
      </span>
    </span>
  );
}
