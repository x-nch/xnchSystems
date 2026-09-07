"use client";

import { useState } from "react";
import {
  Activity,
  Database,
  FileSearch,
  GitBranch,
  Layers,
  ScanSearch,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useGraphStats,
  useMemoryTierHealth,
  useSystemState,
  useContextManifest,
} from "@/lib/api/hooks";
import type {
  ContextEpisode,
  ContextExperience,
  ContextManifest,
  ContextPattern,
  ContextPolicyRef,
} from "@/lib/api/types";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { formatPercent, formatRelativeTime, truncate } from "@/lib/utils/format";

const ACTOR_ROLES = ["ADMIN", "OPERATOR", "VIEWER", "AGENT"];

export function ContextStatePanel() {
  const state = useSystemState();
  const tierHealth = useMemoryTierHealth();
  const graphStats = useGraphStats();
  const manifest = useContextManifest();

  const settingsActor = useSettingsStore((s) => s.actorId);
  const settingsRole = useSettingsStore((s) => s.actorRole);

  const [sessionId, setSessionId] = useState("");
  const [actorId, setActorId] = useState(settingsActor);
  const [actorRole, setActorRole] = useState(
    settingsRole && settingsRole !== "operator" ? settingsRole.toUpperCase() : "OPERATOR"
  );
  const [intentClass, setIntentClass] = useState("");
  const [entityClass, setEntityClass] = useState("");
  const [lookbackDays, setLookbackDays] = useState("30");

  const runAudit = () => {
    if (!sessionId.trim() || !actorId.trim()) return;
    manifest.mutate({
      session_id: sessionId.trim(),
      actor_id: actorId.trim(),
      actor_role: actorRole,
      query: {
        intent_class: intentClass.trim() || undefined,
        target_entity_class: entityClass.trim() || undefined,
        lookback_window_days: Number(lookbackDays) || 30,
      },
    });
  };

  const data = manifest.data;
  const pinnedMatchesLive =
    data != null &&
    state.data != null &&
    data.system_state_version === state.data.system_state_version;

  return (
    <div className="grid gap-4 overflow-y-auto p-4 lg:grid-cols-[1.6fr_1fr]">
      {/* Zone 1 — live state header */}
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-accent" />
            System state
          </CardTitle>
          <CardDescription>
            <code className="rounded bg-muted px-1 font-mono">GET /system/state</code> — live
            versions every decision is pinned against
          </CardDescription>
        </CardHeader>
        <CardContent>
          {state.isPending ? (
            <Spinner className="h-4 w-4 text-muted-foreground" />
          ) : state.isError || !state.data ? (
            <p className="text-[13px] text-red-400">System state unavailable</p>
          ) : (
            <div className="flex flex-wrap items-center gap-x-10 gap-y-3">
              <StatusRow
                label="System state version"
                value={state.data.system_state_version}
              />
              <StatusRow label="Policy version" value={state.data.policy_version} />
              {data && (
                <StalenessBadge
                  stale={!pinnedMatchesLive}
                  manifestVersion={data.system_state_version}
                  liveVersion={state.data.system_state_version}
                />
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Zone 2 — context manifest viewer */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ScanSearch className="h-4 w-4 text-accent" />
            Context manifest
          </CardTitle>
          <CardDescription>
            <code className="rounded bg-muted px-1 font-mono">POST /memory/read</code> — what the
            agent sees for a context tuple
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3">
            <div className="grid gap-2">
              <Label htmlFor="ctx-session">Session ID</Label>
              <Input
                id="ctx-session"
                placeholder="00000000-0000-0000-0000-000000000000"
                value={sessionId}
                onChange={(e) => setSessionId(e.target.value)}
                className="font-mono text-[12px]"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-2">
                <Label htmlFor="ctx-actor-id">Actor ID</Label>
                <Input
                  id="ctx-actor-id"
                  value={actorId}
                  onChange={(e) => setActorId(e.target.value)}
                  className="font-mono text-[12px]"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="ctx-actor-role">Actor role</Label>
                <select
                  id="ctx-actor-role"
                  value={actorRole}
                  onChange={(e) => setActorRole(e.target.value)}
                  className="h-9 w-full rounded-lg border border-border bg-input px-3 text-sm text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
                >
                  {ACTOR_ROLES.map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-2">
                <Label htmlFor="ctx-intent">Intent class</Label>
                <Input
                  id="ctx-intent"
                  placeholder="e.g. RESEARCH"
                  value={intentClass}
                  onChange={(e) => setIntentClass(e.target.value)}
                  className="font-mono text-[12px]"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="ctx-entity">Target entity class</Label>
                <Input
                  id="ctx-entity"
                  placeholder="e.g. ACCOUNT / CMDB"
                  value={entityClass}
                  onChange={(e) => setEntityClass(e.target.value)}
                  className="font-mono text-[12px]"
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="ctx-lookback">Lookback window (days)</Label>
              <Input
                id="ctx-lookback"
                type="number"
                min={1}
                value={lookbackDays}
                onChange={(e) => setLookbackDays(e.target.value)}
                className="font-mono text-[12px]"
              />
            </div>
            <Button
              onClick={runAudit}
              disabled={manifest.isPending || !sessionId.trim() || !actorId.trim()}
              className="w-full"
            >
              {manifest.isPending ? (
                <Spinner className="h-4 w-4" />
              ) : (
                <FileSearch className="h-4 w-4" />
              )}
              {manifest.isPending ? "Assembling manifest…" : "Assemble context"}
            </Button>
            {manifest.isError && (
              <p className="text-[12px] leading-relaxed text-red-400">
                {manifest.error instanceof Error
                  ? manifest.error.message
                  : "Failed to assemble manifest"}
              </p>
            )}
          </div>

          {data && <ManifestViewer manifest={data} />}
        </CardContent>
      </Card>

      {/* Zone 3 — tier health + graph */}
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-muted-foreground" />
              Memory tier health
            </CardTitle>
            <CardDescription>
              <code className="rounded bg-muted px-1 font-mono">
                GET /system/memory-tier-health
              </code>{" "}
              — live probe per store
            </CardDescription>
          </CardHeader>
          <CardContent>
            {tierHealth.isPending ? (
              <Spinner className="h-4 w-4 text-muted-foreground" />
            ) : tierHealth.isError || !tierHealth.data ? (
              <p className="text-[13px] text-red-400">Memory tier health unavailable</p>
            ) : !tierHealth.data.enabled ? (
              <p className="text-[13px] text-muted-foreground">Deep health runner not enabled</p>
            ) : (
              <div className="space-y-2.5">
                {Object.entries(tierHealth.data.tiers).map(([tier, probe]) => (
                  <div key={tier} className="flex items-start gap-2">
                    <Badge tone={probe.ok ? "success" : "destructive"}>
                      {probe.ok ? "ok" : "down"}
                    </Badge>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="font-mono text-[12px] text-card-foreground">{tier}</span>
                        <span className="font-mono text-[11px] text-muted-foreground">
                          {probe.latency_ms.toFixed(1)}ms
                        </span>
                      </div>
                      {probe.detail && (
                        <p className="truncate text-[11px] text-muted-foreground/70">
                          {probe.detail}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-muted-foreground" />
              Knowledge graph
            </CardTitle>
            <CardDescription>
              <code className="rounded bg-muted px-1 font-mono">GET /memory/graph/stats</code>
            </CardDescription>
          </CardHeader>
          <CardContent>
            {graphStats.isPending ? (
              <Spinner className="h-4 w-4 text-muted-foreground" />
            ) : graphStats.isError || !graphStats.data ? (
              <p className="text-[13px] text-red-400">Graph stats unavailable</p>
            ) : (
              <div className="space-y-3">
                <div className="flex gap-6">
                  <StatusRow
                    label="Entities"
                    value={String(graphStats.data.entity_count)}
                  />
                  <StatusRow
                    label="Relations"
                    value={String(graphStats.data.relation_count)}
                  />
                </div>
                {Object.keys(graphStats.data.types).length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(graphStats.data.types).map(([type, count]) => (
                      <Badge key={type} tone="muted" className="font-mono">
                        {type}: {count}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StalenessBadge({
  stale,
  manifestVersion,
  liveVersion,
}: {
  stale: boolean;
  manifestVersion: string;
  liveVersion: string | null | undefined;
}) {
  const heading = stale
    ? "Manifest pinned to a stale state version"
    : "Manifest matches live state version";
  const detail = stale
    ? `Pinned ${manifestVersion} · live ${liveVersion ?? "unknown"}`
    : manifestVersion;
  return (
    <div className="flex items-center gap-2 text-[12px]">
      <Badge tone={stale ? "warning" : "success"}>{stale ? "stale" : "current"}</Badge>
      <div>
        <p className="text-card-foreground">{heading}</p>
        <p className="font-mono text-[11px] text-muted-foreground">{detail}</p>
      </div>
    </div>
  );
}

function ManifestViewer({ manifest }: { manifest: ContextManifest }) {
  const total =
    manifest.episodes.length + manifest.patterns.length +
    manifest.experiences.length + manifest.policies.length;

  return (
    <div className="mt-4 space-y-3 border-t border-border pt-3">
      <div className="flex items-center gap-2">
        <Database className="h-3.5 w-3.5 text-muted-foreground" />
        <Badge tone="muted" className="font-mono">
          {manifest.manifest_id.slice(0, 8)}
        </Badge>
        <span className="font-mono text-[11px] text-muted-foreground">
          {manifest.system_state_version}
        </span>
        <span className="ml-auto font-mono text-[11px] text-muted-foreground">
          {formatRelativeTime(manifest.pinned_at)}
        </span>
      </div>

      {total === 0 ? (
        <p className="text-[13px] text-muted-foreground">
          No episodes, patterns, experiences, or policies matched this context tuple.
        </p>
      ) : (
        <Tabs defaultValue="episodes">
          <TabsList className="w-full">
            <TabTrigger label="Episodes" count={manifest.episodes.length} value="episodes" />
            <TabTrigger label="Patterns" count={manifest.patterns.length} value="patterns" />
            <TabTrigger label="Experience" count={manifest.experiences.length} value="experiences" />
            <TabTrigger label="Policies" count={manifest.policies.length} value="policies" />
          </TabsList>
          <TabsContent value="episodes">
            <EpisodesTable episodes={manifest.episodes} />
          </TabsContent>
          <TabsContent value="patterns">
            <PatternsTable patterns={manifest.patterns} />
          </TabsContent>
          <TabsContent value="experiences">
            <ExperiencesTable experiences={manifest.experiences} />
          </TabsContent>
          <TabsContent value="policies">
            <PoliciesTable policies={manifest.policies} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}

function TabTrigger({ label, count, value }: { label: string; count: number; value: string }) {
  return (
    <TabsTrigger value={value} className="flex-1">
      {label}
      <span className="rounded-sm bg-muted px-1 font-mono text-[10px] text-muted-foreground">
        {count}
      </span>
    </TabsTrigger>
  );
}

function EmptyRow() {
  return <p className="py-2 text-[12px] text-muted-foreground/70">Nothing in this tier.</p>;
}

function EpisodesTable({ episodes }: { episodes: ContextEpisode[] }) {
  if (episodes.length === 0) return <EmptyRow />;
  return (
    <div className="space-y-1.5">
      {episodes.map((ep) => (
        <RowLine
          key={ep.episode_id ?? `${ep.created_at}`}
          title={ep.action_type ?? "—"}
          subtitle={`${ep.entity_class ?? "*"} · ${ep.outcome ?? "pending"} · ${ep.duration_ms != null ? `${ep.duration_ms}ms` : "—"}`}
          meta={ep.created_at ? formatRelativeTime(ep.created_at) : ""}
        />
      ))}
    </div>
  );
}

function PatternsTable({ patterns }: { patterns: ContextPattern[] }) {
  if (patterns.length === 0) return <EmptyRow />;
  return (
    <div className="space-y-1.5">
      {patterns.map((p) => (
        <RowLine
          key={p.pattern_id ?? p.context_signature ?? "pattern"}
          title={truncate(p.context_signature ?? "") || "—"}
          subtitle={`${p.observation_count ?? 0} observations`}
          meta={p.success_rate != null ? `${formatPercent(p.success_rate)} · conf ${formatPercent(p.confidence ?? 0)}` : ""}
        />
      ))}
    </div>
  );
}

function ExperiencesTable({ experiences }: { experiences: ContextExperience[] }) {
  if (experiences.length === 0) return <EmptyRow />;
  return (
    <div className="space-y-1.5">
      {experiences.map((e) => (
        <RowLine
          key={e.experience_id ?? `${e.created_at}`}
          title={e.lesson ?? e.insight ?? "—"}
          subtitle={`${e.intent_class ?? "?"}/${e.action_type ?? "?"} · ${e.actor_role ?? "?"} · ${e.outcome ?? "?"}`}
          meta={formatPercent(e.confidence ?? 0)}
        />
      ))}
    </div>
  );
}

function PoliciesTable({ policies }: { policies: ContextPolicyRef[] }) {
  if (policies.length === 0) return <EmptyRow />;
  return (
    <div className="space-y-1.5">
      {policies.map((p) => (
        <RowLine
          key={p.policy_id ?? p.rule_expression ?? "policy"}
          title={p.policy_id ?? "—"}
          subtitle={p.rule_expression ?? ""}
          meta={p.enforcement_level ?? ""}
        />
      ))}
    </div>
  );
}

function RowLine({
  title,
  subtitle,
  meta,
}: {
  title: string;
  subtitle: string;
  meta?: string;
}) {
  return (
    <div className="rounded-lg border border-border/60 bg-muted/30 px-2.5 py-2">
      <div className="flex items-baseline justify-between gap-3">
        <p className="min-w-0 flex-1 truncate text-[12px] font-medium text-card-foreground">
          {title}
        </p>
        {meta && (
          <span className="shrink-0 font-mono text-[10px] text-muted-foreground/70">{meta}</span>
        )}
      </div>
      <p className="truncate text-[11px] text-muted-foreground">{subtitle}</p>
    </div>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2 text-[12px]">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className="truncate font-mono text-[11px] text-card-foreground">{value}</span>
    </div>
  );
}