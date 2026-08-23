"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { LineChart } from "@/components/observability/charts";
import { useObsInference } from "@/lib/api/observability-hooks";

const ONE_H = 3600;

function fmtRate(points: [number, number][]): string {
  if (points.length === 0) return "—";
  return points[points.length - 1][1].toFixed(1);
}

export function InferencePanel() {
  const inference = useObsInference(ONE_H, 15);
  const data = inference.data;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card data-testid="obs-inf-tps">
        <CardHeader>
          <CardTitle>Throughput</CardTitle>
          <CardDescription>Ornith generation tokens/s · last hour</CardDescription>
        </CardHeader>
        <CardContent>
          {data?.available ? (
            <>
              <p className="mb-1 font-mono text-2xl">{fmtRate(data.tokens_per_sec_series[0]?.points ?? [])} tok/s</p>
              <LineChart
                series={data.tokens_per_sec_series[0]?.points ?? []}
                ariaLabel="Generation throughput over time"
                label="tokens per second"
                unit=" tok/s"
              />
            </>
          ) : (
            <p className="text-[13px] text-muted-foreground">
              {inference.isPending ? "loading…" : "vLLM metrics unavailable (is the vllm-node-b scrape target up?)"}
            </p>
          )}
        </CardContent>
      </Card>

      <Card data-testid="obs-inf-latency">
        <CardHeader>
          <CardTitle>End-to-end latency</CardTitle>
          <CardDescription>p50 / p95 per request</CardDescription>
        </CardHeader>
        <CardContent className="flex items-end gap-6">
          <div>
            <p className="font-mono text-2xl">
              {data?.latency_p50_s != null ? `${data.latency_p50_s.toFixed(2)}s` : "—"}
            </p>
            <p className="text-[12px] text-muted-foreground">p50</p>
          </div>
          <div>
            <p className="font-mono text-2xl text-[var(--accent)]">
              {data?.latency_p95_s != null ? `${data.latency_p95_s.toFixed(2)}s` : "—"}
            </p>
            <p className="text-[12px] text-muted-foreground">p95</p>
          </div>
        </CardContent>
      </Card>

      <Card data-testid="obs-inf-util">
        <CardHeader>
          <CardTitle>GPU utilization</CardTitle>
          <CardDescription>DCGM · last hour</CardDescription>
        </CardHeader>
        <CardContent>
          {data?.available ? (
            <LineChart
              series={data.gpu_util_series[0]?.points ?? []}
              ariaLabel="GPU utilization over time"
              label="GPU util"
              unit="%"
            />
          ) : (
            <p className="text-[13px] text-muted-foreground">metrics unavailable</p>
          )}
        </CardContent>
      </Card>

      <Card data-testid="obs-inf-vram-queue">
        <CardHeader>
          <CardTitle>VRAM & queue depth</CardTitle>
          <CardDescription>headroom vs budget · running/waiting requests</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {data?.available ? (
            <>
              <LineChart
                series={data.vram_pct_series[0]?.points ?? []}
                threshold={97}
                ariaLabel="VRAM percent used over time with 97% alert threshold"
                label="VRAM used"
                unit="%"
              />
              {data.queue_depth_series.length > 0 ? (
                <ul className="space-y-1 font-mono text-[12px] text-muted-foreground">
                  {data.queue_depth_series.map((s) => {
                    const name = s.metric.__name__?.replace("vllm:num_requests_", "") ?? "?";
                    const latest = s.points[s.points.length - 1]?.[1];
                    return (
                      <li key={name}>
                        {name}: {latest != null ? latest.toFixed(0) : "—"} now · peak{" "}
                        {Math.max(...s.points.map((p) => p[1])).toFixed(0)}
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="text-[12px] text-muted-foreground">no vLLM queue gauges found</p>
              )}
            </>
          ) : (
            <p className="text-[13px] text-muted-foreground">metrics unavailable</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
