"use client";

import {
  BaseEdge,
  EdgeLabelRenderer,
  getStraightPath,
  type EdgeProps,
} from "@xyflow/react";
import { useReducedMotion } from "@/lib/hooks/use-reduced-motion";

type GraphEdgeData = {
  active?: boolean;
  dimmed?: boolean;
  confidence?: number;
  relType?: string;
};

export function GraphEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  style = {},
  data,
}: EdgeProps) {
  const [path, labelX, labelY] = getStraightPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
  });
  const edgeData = data as GraphEdgeData | undefined;
  const active = edgeData?.active ?? false;
  const dimmed = edgeData?.dimmed ?? false;
  const conf = edgeData?.confidence ?? 0.5;
  const relType = edgeData?.relType;
  // SMIL <animateMotion> is not reachable from CSS reduced-motion rules,
  // so the moving dots are dropped entirely when the OS prefers reduction.
  const reduceMotion = useReducedMotion();

  if (dimmed) {
    return (
      <BaseEdge
        id={id}
        path={path}
        style={{
          ...style,
          stroke: "rgba(34, 211, 238, 0.06)",
          strokeWidth: 0.4,
          opacity: 0.35,
        }}
      />
    );
  }

  const stroke = active
    ? "rgba(245, 197, 24, 0.95)"
    : `rgba(34, 211, 238, ${0.22 + conf * 0.35})`;
  const glow = active
    ? "rgba(245, 197, 24, 0.55)"
    : `rgba(34, 211, 238, ${0.15 + conf * 0.2})`;

  return (
    <>
      <BaseEdge
        id={`${id}-glow`}
        path={path}
        style={{
          ...style,
          stroke: glow,
          strokeWidth: active ? 6 : 2,
          opacity: active ? 0.65 : 0.35,
          filter: active ? "blur(4px)" : "blur(2px)",
        }}
      />
      <BaseEdge
        id={id}
        path={path}
        style={{
          ...style,
          stroke,
          strokeWidth: active ? 2 : 0.8,
        }}
      />
      {active && !reduceMotion && (
        <>
          <circle r="3" fill="#f5c518" opacity={0.95}>
            <animateMotion dur="2.2s" repeatCount="indefinite" path={path} />
          </circle>
          <circle r="2" fill="#22d3ee" opacity={0.7}>
            <animateMotion
              dur="2.2s"
              begin="1.1s"
              repeatCount="indefinite"
              path={path}
            />
          </circle>
        </>
      )}
      {active && reduceMotion && (
        <circle r="2.5" fill="#f5c518" opacity={0.6} cx={labelX} cy={labelY} />
      )}
      {active && relType && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: "none",
            }}
            className="rounded border border-[var(--state-attention)] bg-card/95 px-1.5 py-0.5 font-mono text-[8px] font-semibold uppercase tracking-wider text-[var(--accent)] "
          >
            {relType}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
