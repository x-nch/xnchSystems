"use client";

import { useCallback, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useQueryClient } from "@tanstack/react-query";
import {
  Box,
  GitBranch,
  Layers,
  RefreshCw,
  Search,
  Share2,
  Loader2,
  Filter,
  X,
} from "lucide-react";
import { GraphCanvas } from "./graph-canvas";
import { EntityPanel } from "./entity-panel";
import { colorForEntityType } from "./force-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { HudCard, HudCardContent } from "@/components/ui/hud-card";
import { Spinner } from "@/components/ui/spinner";
import {
  useGatewayOnline,
  useGraphEntities,
  useGraphRelations,
  useGraphStats,
  useGraphSubgraph,
} from "@/lib/api/hooks";
import { useGraphStream } from "@/lib/hooks/use-graph-stream";
import {
  mergeGraphData,
  useGraphStreamStore,
} from "@/lib/stores/graph-stream-store";
import { cn } from "@/lib/utils/cn";

const GraphCanvas3D = dynamic(
  () => import("./graph-canvas-3d").then((m) => m.GraphCanvas3D),
  {
    ssr: false,
    loading: () => (
      <div className="absolute inset-0 flex items-center justify-center">
        <Spinner className="h-6 w-6 text-accent" />
      </div>
    ),
  }
);

type Depth = 1 | 2;
type ViewMode = "2d" | "3d";

export function GraphExplorer() {
  const queryClient = useQueryClient();
  const gatewayOk = useGatewayOnline();
  const stats = useGraphStats();
  const { connected: streamLive, reconnecting } = useGraphStream(gatewayOk);
  const liveEntities = useGraphStreamStore((s) => s.liveEntities);
  const liveRelations = useGraphStreamStore((s) => s.liveRelations);
  const streamStats = useGraphStreamStore((s) => s.stats);

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [depth, setDepth] = useState<Depth>(1);
  const [focusId, setFocusId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("3d");

  const overviewMode = focusId === null;

  const entitiesQuery = useGraphEntities({
    search: search || undefined,
    type: typeFilter || undefined,
    limit: 120,
    enabled: overviewMode,
  });
  const relationsQuery = useGraphRelations({
    limit: 300,
    enabled: overviewMode,
  });
  const subgraphQuery = useGraphSubgraph(focusId, depth);

  const { entities, relations, centerId } = useMemo(() => {
    if (!overviewMode && subgraphQuery.data) {
      return {
        entities: subgraphQuery.data.entities,
        relations: subgraphQuery.data.relations,
        centerId: subgraphQuery.data.center_id,
      };
    }
    const baseEnts = entitiesQuery.data?.entities ?? [];
    const ids = new Set(baseEnts.map((e) => e.entity_id));
    for (const id of Object.keys(liveEntities)) ids.add(id);

    const merged = mergeGraphData(
      baseEnts,
      (relationsQuery.data?.relations ?? []).filter(
        (r) => ids.has(r.from_id) && ids.has(r.to_id)
      ),
      liveEntities,
      liveRelations
    );

    let ents = merged.entities;
    if (typeFilter) ents = ents.filter((e) => e.type === typeFilter);
    if (search) {
      const q = search.toLowerCase();
      ents = ents.filter((e) => e.name.toLowerCase().includes(q));
    }

    const entIds = new Set(ents.map((e) => e.entity_id));
    const rels = merged.relations.filter(
      (r) => entIds.has(r.from_id) && entIds.has(r.to_id)
    );

    return { entities: ents, relations: rels, centerId: null };
  }, [
    overviewMode,
    subgraphQuery.data,
    entitiesQuery.data,
    relationsQuery.data,
    liveEntities,
    liveRelations,
    typeFilter,
    search,
  ]);

  const displayStats = streamStats ?? stats.data;

  const effectiveSelectedId = useMemo(() => {
    if (!selectedId) return null;
    return entities.some((e) => e.entity_id === selectedId) ? selectedId : null;
  }, [entities, selectedId]);

  const selectedEntity = useMemo(
    () => entities.find((e) => e.entity_id === effectiveSelectedId) ?? null,
    [entities, effectiveSelectedId]
  );

  const isLoading =
    !gatewayOk ||
    stats.isPending ||
    (overviewMode
      ? entitiesQuery.isPending || relationsQuery.isPending
      : subgraphQuery.isPending);

  const isError =
    stats.isError ||
    (overviewMode
      ? entitiesQuery.isError || relationsQuery.isError
      : subgraphQuery.isError);

  const refresh = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["graph-stats"] });
    void queryClient.invalidateQueries({ queryKey: ["graph-entities"] });
    void queryClient.invalidateQueries({ queryKey: ["graph-relations"] });
    if (focusId) {
      void queryClient.invalidateQueries({ queryKey: ["graph-subgraph", focusId] });
    }
  }, [queryClient, focusId]);

  const topTypes = useMemo(() => {
    const types = displayStats?.types ?? {};
    return Object.entries(types)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8);
  }, [displayStats?.types]);

  const hasFilters = Boolean(search || typeFilter);
  const connectedInView = relations.length;

  const toggleType = (t: string) => {
    setTypeFilter((prev) => (prev === t ? "" : t));
    setFocusId(null);
    setSelectedId(null);
  };

  const clearFilters = () => {
    setSearch("");
    setTypeFilter("");
    setFocusId(null);
    setSelectedId(null);
  };

  return (
    <div className="flex h-full min-h-0 flex-col bg-[#020617]">
      {/* HUD toolbar */}
      <div className="shrink-0 border-b border-border/60 bg-card/20 backdrop-blur-md">
        <div className="flex flex-wrap items-center gap-2 px-3 py-2">
          <div className="flex items-center gap-2 pr-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-accent/10">
              <GitBranch className="h-3.5 w-3.5 text-cyan-300" />
            </div>
            <div>
              <span className="block font-mono text-[10px] font-semibold uppercase tracking-[0.24em] text-cyan-200 glow-text">
                Semantic Graph
              </span>
              {displayStats && (
                <span className="font-mono text-[9px] text-muted-foreground">
                  {displayStats.entity_count} nodes · {displayStats.relation_count} edges
                </span>
              )}
            </div>
            {streamLive ? (
              <span className="flex items-center gap-1.5 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-0.5 font-mono text-[9px] text-emerald-300">
                <span className="streaming-dot h-1.5 w-1.5 rounded-full bg-emerald-400" />
                live
              </span>
            ) : reconnecting ? (
              <span className="font-mono text-[9px] text-amber-300/80">reconnecting…</span>
            ) : null}
          </div>

          <div className="relative min-w-[160px] flex-1 max-w-sm">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setFocusId(null);
              }}
              placeholder="Search by name…"
              className="h-8 border-border/60 bg-input/80 pl-8 text-xs focus-visible:glow-border"
            />
          </div>

          <div className="flex rounded-md border border-border/60 p-0.5">
            {(
              [
                { id: "3d" as const, label: "3D", icon: Box },
                { id: "2d" as const, label: "2D", icon: Layers },
              ] as const
            ).map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setViewMode(id)}
                className={cn(
                  "flex items-center gap-1 rounded px-2.5 py-1 font-mono text-[10px] transition-colors",
                  viewMode === id
                    ? "bg-cyan-300/15 text-cyan-100"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="h-3 w-3" />
                {label}
              </button>
            ))}
          </div>

          <div className="flex rounded-md border border-border/60 p-0.5">
            {([1, 2] as Depth[]).map((d) => (
              <button
                key={d}
                onClick={() => setDepth(d)}
                disabled={overviewMode}
                title={overviewMode ? "Select a node and use Focus for hop depth" : undefined}
                className={cn(
                  "rounded px-2.5 py-1 font-mono text-[10px] transition-colors",
                  depth === d && !overviewMode
                    ? "bg-amber-400/15 text-amber-200"
                    : "text-muted-foreground hover:text-foreground",
                  overviewMode && "cursor-not-allowed opacity-35"
                )}
              >
                {d}-hop
              </button>
            ))}
          </div>

          {focusId && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setFocusId(null);
                setSelectedId(null);
              }}
              className="h-8 border-cyan-300/20 text-xs"
            >
              <Share2 className="h-3.5 w-3.5" />
              Overview
            </Button>
          )}

          <Button
            size="sm"
            variant="ghost"
            onClick={refresh}
            disabled={isLoading}
            className="h-8 text-xs"
          >
            {isLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>

        {/* Type filter chips */}
        <div className="flex items-center gap-1.5 overflow-x-auto border-t border-border/40 px-3 py-1.5 scrollbar-none">
          <Filter className="h-3 w-3 shrink-0 text-muted-foreground/60" />
          {topTypes.map(([t, n]) => {
            const active = typeFilter === t;
            const c = colorForEntityType(t);
            return (
              <button
                key={t}
                onClick={() => toggleType(t)}
                className={cn(
                  "shrink-0 rounded-full border px-2 py-0.5 font-mono text-[9px] transition-all",
                  active
                    ? "glow-border-gold bg-amber-400/10 text-amber-100"
                    : "border-border/50 text-muted-foreground hover:border-cyan-300/20 hover:text-foreground"
                )}
                style={
                  active
                    ? undefined
                    : { borderColor: `${c}22`, color: `${c}bb` }
                }
              >
                {t}
                <span className="ml-1 opacity-60">{n}</span>
              </button>
            );
          })}
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="ml-1 flex shrink-0 items-center gap-0.5 rounded-full border border-border/50 px-2 py-0.5 font-mono text-[9px] text-muted-foreground hover:text-foreground"
            >
              <X className="h-2.5 w-2.5" />
              clear
            </button>
          )}
        </div>
      </div>

      {/* View context bar */}
      {!isLoading && entities.length > 0 && (
        <div className="flex shrink-0 items-center gap-2 border-b border-border/30 px-3 py-1 font-mono text-[9px] text-muted-foreground">
          <span className="text-cyan-200/80">
            showing {entities.length} nodes
          </span>
          <span>·</span>
          <span>{connectedInView} edges in view</span>
          {streamLive && (
            <>
              <span>·</span>
              <span className="text-emerald-300/80">streaming</span>
            </>
          )}
          {viewMode === "3d" && <span className="text-cyan-200/80">· 3D orbit</span>}
          {focusId && <span className="text-amber-200/80">· focus mode</span>}
          {typeFilter && (
            <span style={{ color: colorForEntityType(typeFilter) }}>
              · type:{typeFilter}
            </span>
          )}
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <div className="relative min-h-[320px] min-w-0 flex-1 overflow-hidden">
          {!gatewayOk && (
            <EmptyState
              title="Gateway offline"
              description="Connect to xnch to explore the Kuzu semantic graph."
            />
          )}
          {gatewayOk && isLoading && entities.length === 0 && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-background/50 backdrop-blur-sm">
              <Spinner className="h-6 w-6 text-accent" />
              <span className="font-mono text-[10px] text-muted-foreground">
                Loading graph topology…
              </span>
            </div>
          )}
          {gatewayOk && isError && (
            <EmptyState
              title="Failed to load graph"
              description="Check that the gateway is running and Kuzu is initialized."
            />
          )}
          {gatewayOk && !isLoading && !isError && entities.length === 0 && (
            <EmptyState
              title={hasFilters ? "No matches" : "Graph is empty"}
              description={
                hasFilters
                  ? "Try clearing filters or broadening your search."
                  : "Entities appear after consolidation extracts them from episodic memory."
              }
              action={hasFilters ? clearFilters : undefined}
              actionLabel="Clear filters"
            />
          )}
          {gatewayOk && entities.length > 0 && (
            <>
              {viewMode === "3d" ? (
                <GraphCanvas3D
                  entities={entities}
                  relations={relations}
                  selectedId={effectiveSelectedId}
                  focusId={focusId}
                  centerId={centerId}
                  onSelect={setSelectedId}
                />
              ) : (
                <GraphCanvas
                  entities={entities}
                  relations={relations}
                  selectedId={effectiveSelectedId}
                  focusId={focusId}
                  centerId={centerId}
                  onSelect={setSelectedId}
                />
              )}
              <div className="pointer-events-none absolute inset-0 z-[1] vignette" aria-hidden />
            </>
          )}
        </div>

        <div
          className={cn(
            "shrink-0 border-t border-border/60 bg-card/10 backdrop-blur-sm lg:w-[300px] lg:border-l lg:border-t-0",
            !selectedEntity && "hidden lg:flex lg:flex-col"
          )}
        >
          {selectedEntity ? (
            <EntityPanel
              entity={selectedEntity}
              relations={relations}
              onClose={() => setSelectedId(null)}
              onFocus={() => setFocusId(selectedEntity.entity_id)}
              onNavigate={(id) => {
                setSelectedId(id);
                setFocusId(id);
              }}
            />
          ) : (
            <HudCard className="m-3 flex flex-1 flex-col border-none bg-transparent shadow-none">
              <HudCardContent className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full border border-cyan-300/15 bg-accent/5">
                  <GitBranch className="h-5 w-5 text-cyan-300/50" />
                </div>
                <div>
                  <p className="font-mono text-[11px] font-medium text-foreground">
                    Select a node
                  </p>
                  <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                    Click any entity — it will glow gold and show connected edges.
                    {viewMode === "3d"
                      ? " Drag to orbit, scroll to zoom."
                      : " Hover to preview connections."}
                  </p>
                </div>
              </HudCardContent>
            </HudCard>
          )}
        </div>
      </div>
    </div>
  );
}

function EmptyState({
  title,
  description,
  action,
  actionLabel,
}: {
  title: string;
  description: string;
  action?: () => void;
  actionLabel?: string;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full border border-border/40 bg-card/30">
        <GitBranch className="h-6 w-6 text-muted-foreground/30" />
      </div>
      <h2 className="font-mono text-sm font-semibold text-foreground">{title}</h2>
      <p className="max-w-xs text-[12px] leading-relaxed text-muted-foreground">
        {description}
      </p>
      {action && actionLabel && (
        <Button size="sm" variant="outline" onClick={action} className="mt-1">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
