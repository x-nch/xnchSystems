"use client";

import * as React from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, Cpu, Flame, Lock, ShieldAlert, Thermometer } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { HudCard, HudCardDescription, HudCardHeader, HudCardTitle } from "@/components/ui/hud-card";
import { Spinner } from "@/components/ui/spinner";
import { useObsSummary } from "@/lib/api/observability-hooks";
import type { TierHealth } from "@/lib/api/observability";

function StatusDot({ ok }: { ok: boolean | null }) {
  if (ok == null) return <span className="inline-block h-2 w-2 rounded-full bg-muted-foreground/40" aria-label="unknown" />;
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${ok ? "bg-emerald-400" : "bg-red-400"}`}
      aria-label={ok ? "up" : "down"}
    />
  );
}

const LOCK_LABEL: Record<string, string> = {
  ornith: "Ornith (vLLM)",
  vision_stack: "Vision Media Stack",
  none: "none active",
  unknown: "unknown",
  contention: "CONTENTION (both!)",
};

export function SystemHealthPanel() {
  const summary = useObsSummary();
  const data = summary.data;

  return (
    <div className="space-y-4">
      {(data?.alerts_firing.length ?? 0) > 0 && (
        <HudCard glow="attention" role="alert">
          <HudCardHeader>
            <HudCardTitle className="flex items-center gap-2 text-[var(--state-attention)]">
              <ShieldAlert className="h-4 w-4" />
              {data!.alerts_firing.length} firing alert{data!.alerts_firing.length === 1 ? "" : "s"}
            </HudCardTitle>
            <HudCardDescription>
              {data!.alerts_firing
                .map((a) => a.labels.alertname)
                .filter((v, i, arr) => arr.indexOf(v) === i)
                .join(" · ")}
            </HudCardDescription>
          </HudCardHeader>
        </HudCard>
      )}

      {data?.lock_holder === "contention" && (
        <HudCard glow="attention" role="alert">
          <HudCardHeader>
            <HudCardTitle className="flex items-center gap-2 text-[var(--state-attention)]">
              <Lock className="h-4 w-4" />
              GPU exclusivity broken — both workloads active
            </HudCardTitle>
            <HudCardDescription>
              systemd Conflicts= should prevent this. Check for manual starts bypassing units.
            </HudCardDescription>
          </HudCardHeader>
        </HudCard>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card data-testid="obs-nodes">
          <CardHeader>
            <CardTitle>Nodes</CardTitle>
            <CardDescription>control plane + GPU inference</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-[13px]">
            {!summary.isPending && !data ? (
              <p className="text-muted-foreground">gateway offline</p>
            ) : summary.isPending ? (
              <Spinner className="h-4 w-4 text-muted-foreground" />
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Node A · control</span>
                  <span className="flex items-center gap-2">
                    <StatusDot ok={data!.nodes.a.up} /> xnch
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Node B · nexi</span>
                  <span className="flex items-center gap-2">
                    <StatusDot ok={data!.available ? data!.nodes.b.nexi_up : null} />
                    {data!.available ? "engine" : "prom down"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Node B · ornith</span>
                  <span className="flex items-center gap-2">
                    <StatusDot ok={data!.available ? data!.nodes.b.vllm_up : null} />
                    vLLM :8082
                  </span>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card data-testid="obs-gpu">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="h-4 w-4" /> GPU state
            </CardTitle>
            <CardDescription>RTX 3090 · Node B via DCGM</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-[13px]">
            {data?.available ? (
              <>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-muted-foreground">
                    <Flame className="h-3.5 w-3.5" /> VRAM used
                  </span>
                  <Badge tone={(data.gpu.vram_used_pct ?? 0) > 97 ? "destructive" : "success"}>
                    {data.gpu.vram_used_pct != null ? `${data.gpu.vram_used_pct.toFixed(1)}%` : "—"}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-muted-foreground">
                    <Thermometer className="h-3.5 w-3.5" /> temp
                  </span>
                  <span>{data.gpu.temp_c != null ? `${data.gpu.temp_c.toFixed(0)}°C` : "—"}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">utilization</span>
                  <span>{data.gpu.util_pct != null ? `${data.gpu.util_pct.toFixed(0)}%` : "—"}</span>
                </div>
              </>
            ) : (
              <p className="text-muted-foreground">
                {summary.isPending ? <Spinner className="h-4 w-4" /> : "metrics unavailable"}
              </p>
            )}
          </CardContent>
        </Card>

        <Card data-testid="obs-lock">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lock className="h-4 w-4" /> GPU lock holder
            </CardTitle>
            <CardDescription>Ornith ⇄ Vision Media Stack (Conflicts=)</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-mono text-lg">{LOCK_LABEL[data?.lock_holder ?? "unknown"]}</p>
            <p className="mt-1 text-[12px] text-muted-foreground">
              every handoff stops inference and forces a full model reload
            </p>
          </CardContent>
        </Card>
      </div>

      <Card data-testid="obs-tiers">
        <CardHeader>
          <CardTitle>Memory-tier health</CardTitle>
          <CardDescription>real round-trip probes, not just process-up</CardDescription>
        </CardHeader>
        <CardContent>
          {Object.keys(data?.memory_tiers ?? {}).length === 0 ? (
            <p className="text-[13px] text-muted-foreground">
              probes have not run yet (first pass within 30s of xnch start)
            </p>
          ) : (
            <ul className="grid gap-2 sm:grid-cols-3">
              {Object.entries(data!.memory_tiers).map(([tier, t]: [string, TierHealth]) => (
                <li key={tier} className="rounded-md border border-border p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[12px]">{tier}</span>
                    <StatusDot ok={t.ok} />
                  </div>
                  <p className="mt-1 font-mono text-[11px] text-muted-foreground">{t.detail}</p>
                  <p className="font-mono text-[11px] text-muted-foreground">{t.latency_ms.toFixed(1)} ms</p>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Link
          href="/observability/hitl"
          className="group rounded-xl border border-border bg-card p-4 transition-colors hover:border-[var(--accent)]"
        >
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-sm">
              <ShieldAlert className="h-4 w-4" /> HITL activity
            </span>
            <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
          </div>
          <p className="mt-1 text-[12px] text-muted-foreground">
            queue trend, decision rates, gate-bypass signals
          </p>
        </Link>
        <Link
          href="/observability/inference"
          className="group rounded-xl border border-border bg-card p-4 transition-colors hover:border-[var(--accent)]"
        >
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-sm">
              <AlertTriangle className="h-4 w-4 hidden" />
              Ornith inference
            </span>
            <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
          </div>
          <p className="mt-1 text-[12px] text-muted-foreground">throughput, latency, GPU over time</p>
        </Link>
      </div>
    </div>
  );
}
