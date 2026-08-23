"use client";

import { BaseEdge, getStraightPath, type EdgeProps } from "@xyflow/react";

type GlowEdgeData = {
  active?: boolean;
  online?: boolean;
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
  const online = edgeData?.online ?? active;

  // Solid, state-carrying stroke — no blur glow. Offline is dashed muted grey.
  const stroke = active ? "#7A9E0A" : online ? "#2E8B6A" : "#5A6780";
  const width = active ? 1.6 : 1;
  const dash = online ? undefined : "6 4";

  return (
    <BaseEdge
      id={id}
      path={path}
      style={{
        ...style,
        stroke,
        strokeWidth: width,
        strokeDasharray: dash,
        opacity: online ? 0.9 : 0.6,
      }}
    />
  );
}
