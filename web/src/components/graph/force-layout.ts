/** Graph layout — force-directed with connected-component clustering. */

export type LayoutNode = { id: string };
export type LayoutEdge = { source: string; target: string };

const NODE_W = 108;
const NODE_H = 72;

function findComponents(
  nodes: LayoutNode[],
  edges: LayoutEdge[]
): LayoutNode[][] {
  const adj = new Map<string, Set<string>>();
  for (const n of nodes) adj.set(n.id, new Set());
  for (const e of edges) {
    adj.get(e.source)?.add(e.target);
    adj.get(e.target)?.add(e.source);
  }

  const visited = new Set<string>();
  const components: LayoutNode[][] = [];

  for (const n of nodes) {
    if (visited.has(n.id)) continue;
    const stack = [n.id];
    const comp: LayoutNode[] = [];
    visited.add(n.id);
    while (stack.length) {
      const id = stack.pop()!;
      comp.push({ id });
      for (const nb of adj.get(id) ?? []) {
        if (!visited.has(nb)) {
          visited.add(nb);
          stack.push(nb);
        }
      }
    }
    components.push(comp);
  }
  return components;
}

function layoutComponent(
  nodes: LayoutNode[],
  edges: LayoutEdge[],
  width: number,
  height: number,
  centerId?: string | null,
  seed = 1
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number; vx: number; vy: number }>();
  const cx = width / 2;
  const cy = height / 2;
  const n = nodes.length;

  // Radial seed — avoids the "box in corners" artifact
  nodes.forEach((node, i) => {
    const angle = (i / n) * Math.PI * 2 + seed * 0.31;
    const r = 40 + n * 6 + ((seed + i * 7) % 40);
    positions.set(node.id, {
      x: cx + Math.cos(angle) * r,
      y: cy + Math.sin(angle) * r,
      vx: 0,
      vy: 0,
    });
  });

  const compIds = new Set(nodes.map((n) => n.id));
  const compEdges = edges.filter(
    (e) => compIds.has(e.source) && compIds.has(e.target)
  );

  const idealLen = Math.max(90, Math.min(160, 70 + n * 4));
  const iterations = Math.min(180, 60 + n * 2);

  for (let t = 0; t < iterations; t++) {
    const alpha = 1 - t / iterations;
    const ids = nodes.map((n) => n.id);

    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const a = positions.get(ids[i])!;
        const b = positions.get(ids[j])!;
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        const dist = Math.max(1, Math.hypot(dx, dy));
        const repulse = (idealLen * idealLen * 1.8 * alpha) / dist;
        dx = (dx / dist) * repulse;
        dy = (dy / dist) * repulse;
        a.vx += dx;
        a.vy += dy;
        b.vx -= dx;
        b.vy -= dy;
      }
    }

    for (const e of compEdges) {
      const a = positions.get(e.source);
      const b = positions.get(e.target);
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.max(1, Math.hypot(dx, dy));
      const pull = (dist - idealLen) * 0.055 * alpha;
      const fx = (dx / dist) * pull;
      const fy = (dy / dist) * pull;
      a.vx += fx;
      a.vy += fy;
      b.vx -= fx;
      b.vy -= fy;
    }

    for (const id of ids) {
      const p = positions.get(id)!;
      const gravity = id === centerId ? 0.06 : 0.015;
      p.vx += (cx - p.x) * gravity * alpha;
      p.vy += (cy - p.y) * gravity * alpha;
      p.vx *= 0.78;
      p.vy *= 0.78;
      p.x += p.vx;
      p.y += p.vy;
    }
  }

  const out = new Map<string, { x: number; y: number }>();
  for (const [id, p] of positions) {
    out.set(id, { x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 });
  }
  return out;
}

export function computeForceLayout(
  nodes: LayoutNode[],
  edges: LayoutEdge[],
  width: number,
  height: number,
  centerId?: string | null
): Map<string, { x: number; y: number }> {
  if (nodes.length === 0) return new Map();
  if (nodes.length === 1) {
    return new Map([
      [nodes[0].id, { x: width / 2 - NODE_W / 2, y: height / 2 - NODE_H / 2 }],
    ]);
  }

  const components = findComponents(nodes, edges);
  const result = new Map<string, { x: number; y: number }>();

  if (components.length === 1) {
    return layoutComponent(nodes, edges, width, height, centerId);
  }

  const cx = width / 2;
  const cy = height / 2;
  const compRadius = Math.min(width, height) * 0.32;

  components.forEach((comp, ci) => {
    const angle = (ci / components.length) * Math.PI * 2 - Math.PI / 2;
    const ox = cx + Math.cos(angle) * compRadius;
    const oy = cy + Math.sin(angle) * compRadius;
    const subW = Math.max(200, width / Math.max(2, Math.ceil(Math.sqrt(components.length))));
    const subH = Math.max(160, height / Math.max(2, Math.ceil(Math.sqrt(components.length))));
    const local = layoutComponent(comp, edges, subW, subH, centerId, ci + 1);

    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const p of local.values()) {
      minX = Math.min(minX, p.x);
      minY = Math.min(minY, p.y);
      maxX = Math.max(maxX, p.x);
      maxY = Math.max(maxY, p.y);
    }
    const compCx = (minX + maxX) / 2 + NODE_W / 2;
    const compCy = (minY + maxY) / 2 + NODE_H / 2;

    for (const [id, p] of local) {
      result.set(id, {
        x: ox - compCx + p.x + NODE_W / 2,
        y: oy - compCy + p.y + NODE_H / 2,
      });
    }
  });

  return result;
}

export const ENTITY_TYPE_COLORS: Record<string, string> = {
  tool: "#22d3ee",
  system: "#67e8f9",
  memory: "#a78bfa",
  service: "#22d3ee",
  entity: "#94a3b8",
  person: "#f5c518",
  user: "#f5c518",
  project: "#c084fc",
  concept: "#34d399",
  library: "#fb923c",
  organization: "#f472b6",
  location: "#60a5fa",
  event: "#f87171",
  decision: "#fbbf24",
  function: "#7dd3fc",
  database: "#38bdf8",
};

export function colorForEntityType(type: string): string {
  const key = type.toLowerCase();
  if (ENTITY_TYPE_COLORS[key]) return ENTITY_TYPE_COLORS[key];
  // stable hash color for unknown types
  let h = 0;
  for (let i = 0; i < type.length; i++) h = (h * 31 + type.charCodeAt(i)) | 0;
  const hues = ["#22d3ee", "#a78bfa", "#34d399", "#f5c518", "#fb923c"];
  return hues[Math.abs(h) % hues.length];
}
