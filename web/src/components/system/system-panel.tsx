"use client";

import { Activity, Cpu, Layers, ServerCrash } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { useCapabilities, useGatewayOnline, useHealth, useSystemState } from "@/lib/api/hooks";

export function SystemPanel() {
  const health = useHealth();
  const state = useSystemState();
  const capabilities = useCapabilities();
  const gatewayOk = useGatewayOnline();

  return (
    <div className="grid gap-4 overflow-y-auto p-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-emerald-400" />
            Gateway health
          </CardTitle>
          <CardDescription>
            <code className="rounded bg-muted px-1 font-mono">GET /health</code> — xnch control plane
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!gatewayOk ? (
            <p className="text-[13px] text-muted-foreground">Waiting for gateway connection…</p>
          ) : health.isPending ? (
            <Spinner className="h-4 w-4 text-muted-foreground" />
          ) : health.isError || !health.data ? (
            <div className="flex items-center gap-2 text-[13px] text-red-400">
              <ServerCrash className="h-4 w-4" />
              {health.error instanceof Error ? health.error.message : "Gateway unreachable"}
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Badge tone={health.data.status === "ok" ? "success" : "destructive"}>
                  {health.data.status}
                </Badge>
                <Badge tone={health.data.redis === "ok" ? "success" : "warning"}>
                  redis {health.data.redis}
                </Badge>
              </div>
              <StatusRow label="Version" value={health.data.version} mono />
              <StatusRow label="State version" value={health.data.state_version} mono />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-accent" />
            System state
          </CardTitle>
          <CardDescription>
            <code className="rounded bg-muted px-1 font-mono">GET /system/state</code> — policy + state versions
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!gatewayOk ? (
            <p className="text-[13px] text-muted-foreground">Waiting for gateway connection…</p>
          ) : state.isPending ? (
            <Spinner className="h-4 w-4 text-muted-foreground" />
          ) : state.isError || !state.data ? (
            <div className="flex items-center gap-2 text-[13px] text-red-400">
              <ServerCrash className="h-4 w-4" />
              {state.error instanceof Error ? state.error.message : "System state unavailable"}
            </div>
          ) : (
            <div className="space-y-3">
              <StatusRow label="System state version" value={state.data.system_state_version} mono />
              <StatusRow label="Policy version" value={state.data.policy_version} mono />
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-muted-foreground" />
            nexi capabilities
          </CardTitle>
          <CardDescription>
            <code className="rounded bg-muted px-1 font-mono">GET /nexi/capabilities</code> — what the agent can do
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!gatewayOk ? (
            <p className="text-[13px] text-muted-foreground">Waiting for gateway connection…</p>
          ) : capabilities.isPending ? (
            <Spinner className="h-4 w-4 text-muted-foreground" />
          ) : capabilities.isError || !capabilities.data ? (
            <div className="flex items-center gap-2 text-[13px] text-red-400">
              <ServerCrash className="h-4 w-4" />
              {capabilities.error instanceof Error
                ? capabilities.error.message
                : "Capabilities unavailable"}
            </div>
          ) : (
            <div className="space-y-3">
              {capabilities.data.summary && (
                <p className="text-[13px] leading-relaxed text-card-foreground">
                  {capabilities.data.summary}
                </p>
              )}
              {capabilities.data.tools &&
                Object.entries(capabilities.data.tools).map(([name, tools]) => (
                  <div key={name} className="flex items-baseline gap-3 text-[12px]">
                    <span className="shrink-0 font-mono text-muted-foreground">{name}</span>
                    <span className="truncate text-card-foreground">
                      {Array.isArray(tools) ? tools.join(", ") : String(tools)}
                    </span>
                  </div>
                ))}
              {capabilities.data.hosts && (
                <div className="flex flex-wrap gap-2">
                  {Object.entries(capabilities.data.hosts).map(([name, url]) => (
                    <Badge key={name} tone="muted" className="font-mono">
                      {name}: {String(url)}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-muted-foreground" />
            Control plane surface
          </CardTitle>
          <CardDescription>Routes the web shell targets on the gateway</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="grid gap-1.5 text-[12px] text-muted-foreground md:grid-cols-2">
            {[
              "POST /nexi/chat — chat pipeline (agentic, with tools)",
              "POST /nexi/chat/stream — SSE streaming chat",
              "POST /nexi/memory/recall — semantic recall",
              "GET /nexi/memory/surface — proactive events",
              "GET /mcp/tools — tool inventory by actor tier",
              "POST /mcp/call — tool invocation",
              "GET /health — gateway health",
              "GET /nexi/capabilities — agent capabilities",
            ].map((item) => (
              <li key={item} className="flex items-center gap-2">
                <span className="h-1 w-1 rounded-full bg-muted-foreground/40" />
                <code className="text-muted-foreground/90">{item}</code>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

function StatusRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 text-[12px]">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span
        className={`truncate text-right text-card-foreground ${mono ? "font-mono text-[11px]" : ""}`}
      >
        {value}
      </span>
    </div>
  );
}
