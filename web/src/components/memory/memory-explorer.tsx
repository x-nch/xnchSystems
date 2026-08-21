"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Database, Search, Bell, Link2, GitBranch } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useMemoryRecall, useMemorySurface, useGatewayOnline } from "@/lib/api/hooks";
import type { MemoryRecallResult } from "@/lib/api/types";
import { formatPercent, formatRelativeTime } from "@/lib/utils/format";

export function MemoryExplorer() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [submittedQuery, setSubmittedQuery] = useState("");
  const recall = useMemoryRecall();
  const surface = useMemorySurface();
  const gatewayOk = useGatewayOnline();

  const runRecall = () => {
    const q = query.trim();
    if (!q) return;
    setSubmittedQuery(q);
    recall.mutate({ query: q, top_k: topK });
  };

  return (
    <div className="grid h-full gap-4 overflow-y-auto p-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      {/* Recall */}
      <div className="min-h-0">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-base font-semibold tracking-tight">
              <Database className="h-4 w-4 text-accent" />
              Memory Explorer
            </h1>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Semantic recall over episodic memory via <code className="rounded bg-muted px-1 font-mono">POST /nexi/memory/recall</code>
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="glow-border-gold border-amber-400/30 text-amber-200 hover:bg-amber-400/10"
            onClick={() => router.push("/graph")}
          >
            <GitBranch className="h-3.5 w-3.5" />
            Kuzu Graph
          </Button>
        </div>

        <div className="mb-4 flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runRecall()}
              placeholder="What did we discuss about…"
              className="pl-9"
            />
          </div>
          <select
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="h-9 rounded-lg border border-border bg-input px-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
            aria-label="Result count"
          >
            {[3, 5, 10].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <Button onClick={runRecall} disabled={!query.trim() || recall.isPending}>
            {recall.isPending ? <Spinner className="h-4 w-4" /> : <Search className="h-4 w-4" />}
            Recall
          </Button>
        </div>

        {recall.isError && (
          <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-[13px] text-red-300">
            Recall failed — {recall.error instanceof Error ? recall.error.message : "unknown error"}
          </div>
        )}

        <div className="space-y-2.5">
          {recall.isPending && (
            <div className="space-y-2.5">
              {[0, 1, 2].map((i) => (
                <Card key={i} className="h-28 animate-pulse bg-muted/40" />
              ))}
            </div>
          )}

          {recall.data && recall.data.length === 0 && (
            <Card>
              <CardContent className="flex flex-col items-center gap-2 py-10 text-center">
                <Database className="h-6 w-6 text-muted-foreground/50" />
                <p className="text-[13px] text-muted-foreground">
                  No episodes matched “{submittedQuery}”.
                </p>
              </CardContent>
            </Card>
          )}

          {recall.data?.map((result, i) => (
            <RecallCard key={result.id ?? i} result={result} />
          ))}

          {!recall.data && !recall.isPending && (
            <Card>
              <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
                <Search className="h-7 w-7 text-muted-foreground/40" />
                <p className="text-[13px] text-muted-foreground">
                  Run a recall query to surface similar episodes from pgvector.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Surface */}
      <div className="min-h-0">
        <Card className="h-full">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bell className="h-3.5 w-3.5 text-warning" />
              Proactive surface
            </CardTitle>
            <CardDescription>
              Pending events from <code className="rounded bg-muted px-1 font-mono">GET /nexi/memory/surface</code>
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {!gatewayOk && (
              <p className="text-[12px] text-muted-foreground">
                Waiting for gateway connection…
              </p>
            )}
            {surface.isError && gatewayOk && (
              <p className="text-[12px] text-red-400">
                Unavailable — {surface.error instanceof Error ? surface.error.message : "error"}
              </p>
            )}
            {surface.isPending && <Spinner className="h-4 w-4 text-muted-foreground" />}
            {surface.data && surface.data.length === 0 && (
              <p className="py-4 text-center text-[12px] text-muted-foreground/70">
                No pending proactive events.
              </p>
            )}
            {surface.data?.map((event, i) => (
              <div
                key={i}
                className="rounded-lg border border-border bg-muted/30 p-2.5"
              >
                <div className="mb-1 flex items-center gap-2">
                  <Badge
                    tone={
                      event.priority >= 5
                        ? "destructive"
                        : event.priority >= 1
                          ? "warning"
                          : "muted"
                    }
                  >
                    p{event.priority}
                  </Badge>
                  <span className="truncate font-mono text-[10px] text-muted-foreground">
                    {event.trigger}
                  </span>
                  <span className="ml-auto shrink-0 text-[10px] text-muted-foreground/60">
                    {formatRelativeTime(event.expires_at)}
                  </span>
                </div>
                <p className="text-[12px] leading-relaxed text-card-foreground">
                  {event.message}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function RecallCard({ result }: { result: MemoryRecallResult }) {
  return (
    <Card>
      <CardContent className="pt-3">
        <div className="mb-1.5 flex items-center gap-2">
          <Badge tone="accent">{result.type}</Badge>
          {result.timestamp && (
            <span className="text-[10px] text-muted-foreground/60">
              {formatRelativeTime(result.timestamp)}
            </span>
          )}
          <span className="flex-1" />
          <Metric label="sim" value={result.similarity} tone="accent" />
          <Metric label="imp" value={result.importance} tone="muted" />
        </div>
        <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-card-foreground">
          {result.content}
        </p>
        {result.relationships && result.relationships.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <Link2 className="h-3 w-3 text-muted-foreground" />
            {result.relationships.map((rel, i) => (
              <span
                key={i}
                className="rounded border border-border bg-muted/40 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
              >
                {rel.type} · {rel.strength.toFixed(2)}
              </span>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "accent" | "muted";
}) {
  const width = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <span
      className={`inline-flex items-center gap-1 font-mono text-[10px] ${tone === "accent" ? "text-accent" : "text-muted-foreground"}`}
      title={`${label} ${formatPercent(value)}`}
    >
      {label}
      <span className="h-1 w-8 overflow-hidden rounded-full bg-muted">
        <span
          className={`block h-full rounded-full ${tone === "accent" ? "bg-accent" : "bg-muted-foreground/50"}`}
          style={{ width: `${width}%` }}
        />
      </span>
    </span>
  );
}
