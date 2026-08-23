"use client";

import { useQuery } from "@tanstack/react-query";
import { observabilityEndpoints } from "@/lib/api/observability";

const SUMMARY_MS = 10_000;
const HITL_MS = 10_000;
const INFERENCE_MS = 15_000;

export function useObsSummary() {
  return useQuery({
    queryKey: ["obs-summary"],
    queryFn: () => observabilityEndpoints.summary(),
    refetchInterval: SUMMARY_MS,
    retry: 1,
  });
}

export function useObsHitl(windowS?: number, stepS?: number) {
  return useQuery({
    queryKey: ["obs-hitl", windowS ?? null, stepS ?? null],
    queryFn: () =>
      observabilityEndpoints.hitl({
        window_s: windowS,
        step_s: stepS,
      }),
    refetchInterval: HITL_MS,
    retry: 1,
  });
}

export function useObsInference(windowS?: number, stepS?: number) {
  return useQuery({
    queryKey: ["obs-inference", windowS ?? null, stepS ?? null],
    queryFn: () =>
      observabilityEndpoints.inference({
        window_s: windowS,
        step_s: stepS,
      }),
    refetchInterval: INFERENCE_MS,
    retry: 1,
  });
}
