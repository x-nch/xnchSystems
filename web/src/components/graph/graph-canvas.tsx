"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  type Edge,
  type EdgeTypes,
  type Node,
  type NodeMouseHandler,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { EntityNode, type EntityNodeData } from "./entity-node";
import { GraphEdge } from "./graph-edge";
import { computeForceLayout } from "./force-layout";
import type { GraphEntity, GraphRelation } from "@/lib/api/types";

const nodeTypes: NodeTypes = { entity: EntityNode };
const edgeTypes: EdgeTypes = { graph: GraphEdge };

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

export function GraphCanvas({
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
  const [size, setSize] = useState({ width: 900, height: 600 });
  const [hoveredId, setHoveredId] = useState<string | null>(null);

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

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) setSize({ width, height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const degreeMap = useMemo(() => {
    const d = new Map<string, number>();
    for (const r of relations) {
      d.set(r.from_id, (d.get(r.from_id) ?? 0) + 1);
      d.set(r.to_id, (d.get(r.to_id) ?? 0) + 1);
    }
    return d;
  }, [relations]);

  const layoutKey = useMemo(
    () =>
      `${entities.map((e) => e.entity_id).join(",")}|${relations.length}|${centerId ?? focusId ?? ""}|${size.width}x${size.height}`,
    [entities, relations.length, centerId, focusId, size.width, size.height]
  );

  const { nodes, edges } = useMemo(() => {
    const layoutNodes = entities.map((e) => ({ id: e.entity_id }));
    const layoutEdges = relations.map((r) => ({
      source: r.from_id,
      target: r.to_id,
    }));
    const positions = computeForceLayout(
      layoutNodes,
      layoutEdges,
      size.width,
      size.height,
      centerId ?? focusId ?? selectedId
    );

    const glowNeighbors = buildNeighborSet(edgeActiveId, relations);
    const dimNeighbors = buildNeighborSet(validSelected, relations);

    const flowNodes: Node<EntityNodeData>[] = entities.map((e) => {
      const pos = positions.get(e.entity_id) ?? {
        x: size.width / 2 - 54,
        y: size.height / 2 - 36,
      };
      const isSelected = e.entity_id === validSelected;
      const isNeighbor = Boolean(
        edgeActiveId &&
          glowNeighbors.has(e.entity_id) &&
          e.entity_id !== edgeActiveId
      );

      return {
        id: e.entity_id,
        type: "entity",
        position: pos,
        zIndex: isSelected ? 20 : isNeighbor ? 10 : 0,
        data: {
          label: e.name,
          entityType: e.type,
          degree: degreeMap.get(e.entity_id) ?? 0,
          selected: isSelected,
          connected: isNeighbor,
          focused: e.entity_id === focusId || e.entity_id === centerId,
          hovered: e.entity_id === validHovered,
          dimmed: dimMode && !dimNeighbors.has(e.entity_id),
        },
      };
    });

    const flowEdges: Edge[] = relations.map((r) => {
      const touchesActive = Boolean(
        edgeActiveId &&
          (r.from_id === edgeActiveId || r.to_id === edgeActiveId)
      );
      return {
        id: `${r.from_id}-${r.to_id}-${r.rel_type}`,
        source: r.from_id,
        target: r.to_id,
        type: "graph",
        zIndex: touchesActive ? 15 : 0,
        data: {
          active: touchesActive,
          dimmed: dimMode && !touchesActive,
          confidence: r.confidence,
          relType: r.rel_type,
        },
      };
    });

    return { nodes: flowNodes, edges: flowEdges };
    // layoutKey intentionally drives re-layout on structural changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layoutKey, validSelected, validHovered, edgeActiveId, dimMode, degreeMap]);

  const onNodeClick: NodeMouseHandler = useCallback(
    (_e, node) => {
      onSelect(node.id === selectedId ? null : node.id);
    },
    [onSelect, selectedId]
  );

  const onNodeMouseEnter: NodeMouseHandler = useCallback((_e, node) => {
    setHoveredId(node.id);
  }, []);

  const onNodeMouseLeave: NodeMouseHandler = useCallback(() => {
    setHoveredId(null);
  }, []);

  const clearHover = useCallback(() => setHoveredId(null), []);

  const activeConnections = edgeActiveId
    ? relations.filter(
        (r) => r.from_id === edgeActiveId || r.to_id === edgeActiveId
      ).length
    : 0;

  if (entities.length === 0) return null;

  return (
    <div ref={containerRef} className="absolute inset-0">
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background: edgeActiveId
            ? "radial-gradient(ellipse 50% 40% at 50% 50%, rgba(245,197,24,0.04) 0%, transparent 70%)"
            : "radial-gradient(ellipse 55% 45% at 50% 50%, rgba(34,211,238,0.05) 0%, transparent 70%)",
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

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={onNodeClick}
        onNodeMouseEnter={onNodeMouseEnter}
        onNodeMouseLeave={onNodeMouseLeave}
        onPaneMouseLeave={clearHover}
        onMoveStart={clearHover}
        onPaneClick={() => {
          clearHover();
          onSelect(null);
        }}
        fitView
        fitViewOptions={{ padding: 0.35, maxZoom: 1.2 }}
        minZoom={0.15}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        nodesConnectable={false}
        nodesDraggable
        elementsSelectable={false}
        elevateEdgesOnSelect={false}
        panOnScroll
        zoomOnDoubleClick={false}
        className="bg-transparent"
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={32}
          size={0.8}
          color={
            edgeActiveId
              ? "rgba(245, 197, 24, 0.05)"
              : "rgba(34, 211, 238, 0.06)"
          }
        />
        <Controls
          showInteractive={false}
          position="bottom-right"
          className="!border-border !bg-card/80 !backdrop-blur-md"
        />
      </ReactFlow>
    </div>
  );
}
