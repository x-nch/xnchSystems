"use client";

import { BaseEdge, getStraightPath, type EdgeProps } from "@xyflow/react";

type GlowEdgeData = {
  active?: boolean;
};

export function GlowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  style = {},
  data,
}: EdgeProps) {
  const [path] = getStraightPath({ sourceX, sourceY, targetX, targetY });
  const edgeData = data as GlowEdgeData | undefined;
  const active = edgeData?.active ?? false;
  const stroke = active ? "rgba(245, 197, 24, 0.65)" : "rgba(34, 211, 238, 0.32)";
  const glow = active ? "rgba(245, 197, 24, 0.5)" : "rgba(34, 211, 238, 0.45)";

  return (
    <>
      <BaseEdge
        id={`${id}-glow`}
        path={path}
        style={{
          ...style,
          stroke: glow,
          strokeWidth: active ? 4 : 3,
          opacity: 0.35,
          filter: "blur(3px)",
        }}
      />
      <BaseEdge
        id={id}
        path={path}
        style={{
          ...style,
          stroke,
          strokeWidth: active ? 1.5 : 1,
        }}
      />
      {active && (
        <circle r="3" fill="#f5c518">
          <animateMotion dur="2.4s" repeatCount="indefinite" path={path} />
        </circle>
      )}
    </>
  );
}
