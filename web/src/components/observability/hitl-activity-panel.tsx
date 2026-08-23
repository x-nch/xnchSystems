"use client";

import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { HudCard, HudCardDescription, HudCardHeader, HudCardTitle } from "@/components/ui/hud-card";
import { LineChart, TtdHistogram } from "@/components/observability/charts";
import { useObsHitl } from "@/lib/api/observability-hooks";

const SIX_H = 6 * 3600;

export function HitlActivityPanel() {
  const hitl = useObsHitl(SIX_H, 60);
  const data = hitl.data;
  const bypassRecent = (data?.bypass_24h ?? 0) > 0 || data?.last_bypass_alert != null;

  const queuePoints: [number, number][] =
    data?.queue_depth_series[0]?.points.map(([t, v]) => [t, v]) ?? [];

  return (
    <div className="space-y-4">
      {bypassRecent && (
        <HudCard glow="attention" role="alert" data-testid="obs-bypass-banner">
          <HudCardHeader>
            <HudCardTitle className="flex items-center gap-2 text-[var(--state-attention)]">
              <ShieldAlert className="h-4 w-4" />
              Gate bypass detected
            </HudCardTitle>
            <HudCardDescription>
              {data!.bypass_24h != null
                ? `${data!.bypass_24h} goal-loop EXECUTION${data!.bypass_24h === 1 ? "" : "s"} allowed outside the gate in the last 24h.`
                : "A gate-bypass alert has fired recently."}{" "}
              Forensics: grep HITL_GATE_BYPASS in ~/.xnch/audit/events.jsonl.
            </HudCardDescription>
          </HudCardHeader>
        </HudCard>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2" data-testid="obs-hitl-queue">
          <CardHeader>
            <CardTitle>Approval queue depth</CardTitle>
            <CardDescription>pending interrupts · last 6h</CardDescription>
          </CardHeader>
          <CardContent>
            {data?.available ? (
              <>
                <LineChart
                  series={queuePoints}
                  ariaLabel="Pending interrupt queue depth over time"
                  label="pending interrupts"
                />
                <p className="mt-2 font-mono text-[12px] text-muted-foreground">
                  now: {data.pending_now.pending_count} pending · oldest{" "}
                  {Math.round(data.pending_now.oldest_age_seconds)}s
                </p>
              </>
            ) : hitl.isPending ? (
              <p className="text-[13px] text-muted-foreground">loading…</p>
            ) : (
              <p className="text-[13px] text-muted-foreground">metrics unavailable</p>
            )}
          </CardContent>
        </Card>

        <Card data-testid="obs-hitl-rates">
          <CardHeader>
            <CardTitle>Decisions · last hour</CardTitle>
            <CardDescription>human gate outcomes</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-[13px]">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">approved</span>
              <Badge tone={(data?.decisions_1h.approved ?? 0) > 0 ? "success" : "muted"}>
                {data?.decisions_1h.approved ?? "—"}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">rejected</span>
              <Badge tone={(data?.decisions_1h.rejected ?? 0) > 0 ? "warning" : "muted"}>
                {data?.decisions_1h.rejected ?? "—"}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">expired</span>
              <Badge tone="muted">{data?.expires_1h ?? 0}</Badge>
            </div>
            {data?.expiry_note && (
              <p className="pt-1 text-[11px] leading-snug text-muted-foreground">{data.expiry_note}</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card data-testid="obs-hitl-ttd">
        <CardHeader>
          <CardTitle>Time to decision</CardTitle>
          <CardDescription>cumulative distribution of human decision latency</CardDescription>
        </CardHeader>
        <CardContent>
          {data?.time_to_decision_buckets.length ? (
            <TtdHistogram buckets={data.time_to_decision_buckets} />
          ) : (
            <p className="text-[13px] text-muted-foreground">
              No decisions recorded since process start.
            </p>
          )}
        </CardContent>
      </Card>

      <p className="text-[12px] text-muted-foreground">
        Aggregate view only — act on individual proposals in the{" "}
        <Link href="/" className="underline decoration-dotted underline-offset-4 hover:text-[var(--accent)]">
          approvals queue
        </Link>
        .
      </p>
    </div>
  );
}
