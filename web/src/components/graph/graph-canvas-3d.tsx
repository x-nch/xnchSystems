"use client";

import { Component, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import ForceGraph3D, {
  type ForceGraphMethods,
  type NodeObject,
} from "react-force-graph-3d";
import type { GraphEntity, GraphRelation } from "@/lib/api/types";
import { colorForEntityType } from "./force-layout";

type GraphNode = NodeObject & {
  id: string;
  name: string;
  entityType: string;
  val: number;
};

type GraphLink = {
  source: string;
  target: string;
  relType: string;
  confidence: number;
};

type Graph3DErrorBoundaryProps = {
  children: ReactNode;
  onError?: (message: string) => void;
};

type Graph3DErrorBoundaryState = {
  error: string | null;
};

class Graph3DErrorBoundary extends Component<
  Graph3DErrorBoundaryProps,
  Graph3DErrorBoundaryState
> {
  state: Graph3DErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): Graph3DErrorBoundaryState {
    return { error: error.message || "3D renderer failed" };
  }

  componentDidCatch(error: Error) {
    this.props.onError?.(error.message);
    console.error("[GraphCanvas3D]", error);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-6 text-center">
          <p className="font-mono text-xs font-semibold text-amber-200">
            3D view unavailable
          </p>
          <p className="max-w-xs font-mono text-[10px] text-muted-foreground">
            {this.state.error}
          </p>
          <p className="font-mono text-[10px] text-cyan-200/70">
            Switch to 2D mode in the toolbar.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

function buildNeighborSet(
  activeId: string | null,
  relations: GraphRelation[]
): Set<string> {
  const set = new Set<string>();
  if (!activeId) return set;
  set.add(activeId);
  for (const r of relations) {
    if (r.from_id === activeId) set.add(r.to_id);
    if (r.to_id === activeId) set.add(r.from_id);
  }
  return set;
}

function linkEndpointId(
  endpoint: string | number | GraphNode | undefined
): string {
  if (endpoint == null) return "";
  if (typeof endpoint === "object") return String(endpoint.id ?? "");
  return String(endpoint);
}

function GraphCanvas3DInner({
  entities,
  relations,
  selectedId,
  focusId,
  centerId,
  onSelect,
}: {
  entities: GraphEntity[];
  relations: GraphRelation[];
  selectedId: string | null;
  focusId: string | null;
  centerId?: string | null;
  onSelect: (id: string | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<ForceGraphMethods<GraphNode, GraphLink> | undefined>(
    undefined
  );
  const fittedRef = useRef(false);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setReady(true);
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const measure = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width > 0 && height > 0) {
        setSize({ width: Math.floor(width), height: Math.floor(height) });
      }
    };

    measure();
    const ro = new ResizeObserver(() => measure());
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const entityIds = useMemo(
    () => new Set(entities.map((e) => e.entity_id)),
    [entities]
  );

  const validSelected =
    selectedId && entityIds.has(selectedId) ? selectedId : null;
  const validHovered =
    hoveredId && entityIds.has(hoveredId) ? hoveredId : null;
  const edgeActiveId = validHovered ?? validSelected;
  const dimMode = Boolean(validSelected);

  const degreeMap = useMemo(() => {
    const d = new Map<string, number>();
    for (const r of relations) {
      d.set(r.from_id, (d.get(r.from_id) ?? 0) + 1);
      d.set(r.to_id, (d.get(r.to_id) ?? 0) + 1);
    }
    return d;
  }, [relations]);

  const glowNeighbors = useMemo(
    () => buildNeighborSet(edgeActiveId, relations),
    [edgeActiveId, relations]
  );
  const dimNeighbors = useMemo(
    () => buildNeighborSet(validSelected, relations),
    [validSelected, relations]
  );

  const graphData = useMemo(() => {
    const anchor = centerId ?? focusId ?? validSelected;
    const nodes: GraphNode[] = entities.map((e) => {
      const degree = degreeMap.get(e.entity_id) ?? 0;
      const isAnchor = e.entity_id === anchor;
      return {
        id: e.entity_id,
        name: e.name,
        entityType: e.type,
        val: isAnchor ? 10 : Math.max(3, 2 + Math.sqrt(degree) * 1.4),
      };
    });
    const nodeIdSet = new Set(nodes.map((n) => n.id));
    const links: GraphLink[] = relations
      .filter((r) => nodeIdSet.has(r.from_id) && nodeIdSet.has(r.to_id))
      .map((r) => ({
        source: r.from_id,
        target: r.to_id,
        relType: r.rel_type,
        confidence: r.confidence,
      }));
    return { nodes, links };
  }, [entities, relations, degreeMap, centerId, focusId, validSelected]);

  const activeConnections = edgeActiveId
    ? relations.filter(
        (r) => r.from_id === edgeActiveId || r.to_id === edgeActiveId
      ).length
    : 0;

  const linkTouchesActive = useCallback(
    (link: GraphLink) => {
      if (!edgeActiveId) return false;
      const src = linkEndpointId(link.source);
      const tgt = linkEndpointId(link.target);
      return src === edgeActiveId || tgt === edgeActiveId;
    },
    [edgeActiveId]
  );

  const nodeColor = useCallback(
    (node: GraphNode) => {
      if (node.id === validSelected) return "#f5c518";
      if (
        edgeActiveId &&
        glowNeighbors.has(node.id) &&
        node.id !== edgeActiveId
      ) {
        return "#22d3ee";
      }
      if (dimMode && !dimNeighbors.has(node.id)) return "#334155";
      return colorForEntityType(node.entityType);
    },
    [validSelected, edgeActiveId, glowNeighbors, dimMode, dimNeighbors]
  );

  const linkColor = useCallback(
    (link: GraphLink) => {
      if (linkTouchesActive(link)) return "#f5c518";
      if (dimMode) return "rgba(34, 211, 238, 0.08)";
      return "rgba(34, 211, 238, 0.35)";
    },
    [linkTouchesActive, dimMode]
  );

  const linkWidth = useCallback(
    (link: GraphLink) => (linkTouchesActive(link) ? 1.8 : 0.35),
    [linkTouchesActive]
  );

  const handleEngineStop = useCallback(() => {
    if (fittedRef.current) return;
    fittedRef.current = true;
    window.setTimeout(() => {
      fgRef.current?.zoomToFit(400, 80);
    }, 200);
  }, []);

  useEffect(() => {
    fittedRef.current = false;
  }, [graphData.nodes.length, graphData.links.length]);

  if (entities.length === 0) return null;

  const canRender = ready && size.width > 0 && size.height > 0;

  return (
    <div ref={containerRef} className="absolute inset-0 h-full w-full">
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background: edgeActiveId
            ? "radial-gradient(ellipse 50% 40% at 50% 50%, rgba(245,197,24,0.05) 0%, transparent 70%)"
            : "radial-gradient(ellipse 55% 45% at 50% 50%, rgba(34,211,238,0.06) 0%, transparent 70%)",
        }}
        aria-hidden
      />

      {edgeActiveId && (
        <div className="pointer-events-none absolute left-1/2 top-3 z-20 -translate-x-1/2">
          <span className="hud-panel rounded-full px-3 py-1 font-mono text-[9px] text-amber-200/90">
            {activeConnections} connection{activeConnections !== 1 ? "s" : ""}{" "}
            highlighted
          </span>
        </div>
      )}

      <div className="pointer-events-none absolute bottom-3 left-3 z-20">
        <span className="hud-panel rounded-full px-2.5 py-1 font-mono text-[9px] text-cyan-200/70">
          drag to orbit · scroll to zoom
        </span>
      </div>

      {!canRender && (
        <div className="absolute inset-0 z-10 flex items-center justify-center">
          <span className="font-mono text-[10px] text-muted-foreground">
            Initializing 3D canvas…
          </span>
        </div>
      )}

      {canRender && (
        <ForceGraph3D<GraphNode, GraphLink>
          ref={fgRef}
          width={size.width}
          height={size.height}
          graphData={graphData}
          backgroundColor="#020617"
          nodeLabel={(node) =>
            `${node.name}\n${node.entityType}${node.id === validSelected ? "\n● selected" : ""}`
          }
          nodeColor={nodeColor}
          nodeVal="val"
          nodeRelSize={5}
          nodeOpacity={dimMode ? 0.85 : 0.95}
          linkColor={linkColor}
          linkWidth={linkWidth}
          linkOpacity={0.75}
          linkDirectionalParticles={(link) =>
            linkTouchesActive(link) ? 2 : 0
          }
          linkDirectionalParticleWidth={2}
          linkDirectionalParticleColor={() => "#f5c518"}
          linkDirectionalParticleSpeed={0.004}
          onNodeClick={(node) => {
            onSelect(node.id === selectedId ? null : node.id);
          }}
          onNodeHover={(node) => setHoveredId(node?.id ?? null)}
          onBackgroundClick={() => {
            setHoveredId(null);
            onSelect(null);
          }}
          onEngineStop={handleEngineStop}
          enableNodeDrag
          showNavInfo={false}
          warmupTicks={80}
          cooldownTicks={60}
          d3AlphaDecay={0.022}
          d3VelocityDecay={0.35}
        />
      )}
    </div>
  );
}

export function GraphCanvas3D(props: {
  entities: GraphEntity[];
  relations: GraphRelation[];
  selectedId: string | null;
  focusId: string | null;
  centerId?: string | null;
  onSelect: (id: string | null) => void;
}) {
  return (
    <Graph3DErrorBoundary>
      <GraphCanvas3DInner {...props} />
    </Graph3DErrorBoundary>
  );
}
