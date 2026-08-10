"use client";

import { useState } from "react";
import { Wrench, Server, Search, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ToolCallModal } from "@/components/tools/tool-call-modal";
import { useMcpServers, useMcpTools } from "@/lib/api/hooks";
import { useSettingsStore } from "@/lib/stores/settings-store";
import type { McpTool } from "@/lib/api/types";

const TIER_TONE: Record<string, "accent" | "success" | "warning" | "muted" | "destructive"> = {
  T0_READ: "destructive",
  T1_WRITE: "warning",
  T2_EXEC: "accent",
  T3_SAFE: "muted",
};

export function ToolsPanel() {
  const actorRole = useSettingsStore((s) => s.actorRole);
  const tools = useMcpTools(actorRole);
  const servers = useMcpServers();
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState<McpTool | null>(null);

  const filtered = tools.data?.tools.filter(
    (t) =>
      !filter ||
      t.name.toLowerCase().includes(filter.toLowerCase()) ||
      t.description.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="flex h-full flex-col">
      <div className="mb-4 flex items-end justify-between gap-4 px-4 pt-4">
        <div>
          <h1 className="flex items-center gap-2 text-base font-semibold tracking-tight">
            <Wrench className="h-4 w-4 text-accent" />
            MCP Tools
          </h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Native + bridged tools surfaced by the gateway for actor{" "}
            <code className="rounded bg-muted px-1 font-mono">{actorRole}</code>
          </p>
        </div>
        <div className="relative w-56">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter tools…"
            className="pl-9"
          />
        </div>
      </div>

      <div className="mb-4 px-4">
        <Card className="bg-muted/20">
          <CardContent className="flex items-center gap-3 py-2.5">
            <Server className="h-4 w-4 text-muted-foreground" />
            <span className="text-[12px] text-muted-foreground">MCP bridge</span>
            {servers.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
            ) : servers.data ? (
              <span className="flex flex-wrap items-center gap-1.5">
                {servers.data.enabled ? (
                  <Badge tone="success">enabled</Badge>
                ) : (
                  <Badge tone="muted">disabled</Badge>
                )}
                {servers.data.servers?.map((server, i) => (
                  <Badge key={i} tone="muted" className="font-mono">
                    {String(server.name ?? `server-${i}`)}
                  </Badge>
                ))}
              </span>
            ) : (
              <Badge tone="destructive">unavailable</Badge>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
        {tools.isPending && (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Card key={i} className="h-28 animate-pulse bg-muted/40" />
            ))}
          </div>
        )}

        {tools.isError && (
          <Card>
            <CardContent className="py-10 text-center text-[13px] text-red-400">
              Failed to load tools —{" "}
              {tools.error instanceof Error ? tools.error.message : "unknown error"}
            </CardContent>
          </Card>
        )}

        {filtered && filtered.length === 0 && (
          <Card>
            <CardContent className="py-10 text-center text-[13px] text-muted-foreground">
              No tools match “{filter}”.
            </CardContent>
          </Card>
        )}

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {filtered?.map((tool) => (
            <button
              key={tool.name}
              onClick={() => setSelected(tool)}
              className="group flex flex-col rounded-xl border border-border bg-card text-left transition-colors hover:border-accent/40 hover:bg-accent-subtle/30"
            >
              <CardHeader className="pb-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[12px] font-semibold text-foreground group-hover:text-accent">
                    {tool.name}
                  </span>
                  <span className="flex-1" />
                  <Badge tone={TIER_TONE[tool.tier] ?? "muted"}>{tool.tier}</Badge>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <p className="line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
                  {tool.description || "No description"}
                </p>
              </CardContent>
            </button>
          ))}
        </div>
      </div>

      <ToolCallModal tool={selected} onOpenChange={(open) => !open && setSelected(null)} />
    </div>
  );
}
