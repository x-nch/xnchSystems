import { apiRequest } from "@/lib/api/client";

/** A single time-series as [unix_seconds, value] pairs. */
export interface ObsSeries {
  metric: Record<string, string>;
  points: [number, number][];
}

export interface TierHealth {
  ok: boolean;
  latency_ms: number;
  detail: string;
}

export interface HitlPendingSnapshot {
  pending_count: number;
  oldest_age_seconds: number;
  interrupts: { thread_id: string; age_seconds: number }[];
}

export interface FiringAlert {
  status: string;
  labels: Record<string, string>;
  annotations: Record<string, string>;
  received_at?: number;
}

export interface ObsSummary {
  available: boolean;
  generated_at: number;
  nodes: {
    a: { up: boolean; role: string };
    b: { nexi_up: boolean | null; vllm_up: boolean | null; role: string };
  };
  gpu: { vram_used_pct: number | null; temp_c: number | null; util_pct: number | null };
  lock_holder: "ornith" | "vision_stack" | "none" | "unknown" | "contention";
  memory_tiers: Record<string, TierHealth>;
  hitl: HitlPendingSnapshot;
  alerts_firing: FiringAlert[];
}

export interface TtdBucket {
  le: string;
  count: number;
}

export interface ObsHitl {
  available: boolean;
  window_s?: number;
  step_s?: number;
  queue_depth_series: ObsSeries[];
  decisions_1h: { approved: number | null; rejected: number | null };
  expires_1h: null;
  expiry_note?: string;
  time_to_decision_buckets: TtdBucket[];
  pending_now: HitlPendingSnapshot;
  bypass_24h: number | null;
  last_bypass_alert?: FiringAlert;
}

export interface ObsInference {
  available: boolean;
  window_s?: number;
  step_s?: number;
  gpu_util_series: ObsSeries[];
  vram_pct_series: ObsSeries[];
  tokens_per_sec_series: ObsSeries[];
  queue_depth_series: ObsSeries[];
  latency_p50_s: number | null;
  latency_p95_s: number | null;
}

export const observabilityEndpoints = {
  summary: (query?: { window_s?: number }) =>
    apiRequest<ObsSummary>("/observability/summary", { query }),
  hitl: (query?: { window_s?: number; step_s?: number }) =>
    apiRequest<ObsHitl>("/observability/hitl", { query }),
  inference: (query?: { window_s?: number; step_s?: number }) =>
    apiRequest<ObsInference>("/observability/inference", { query }),
};
