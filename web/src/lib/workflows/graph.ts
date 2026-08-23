import type { Edge, Node } from "@xyflow/react";
import type { HitlActionKind } from "@/lib/approvals/types";
import type { WorkflowStep } from "./types";

export const STEP_KINDS: HitlActionKind[] = [
  "write_file",
  "exec_tool",
  "send_email",
  "create_goal",
  "update_memory",
  "other",
];

export const KIND_LABELS: Record<HitlActionKind, string> = {
  write_file: "Write file",
  exec_tool: "Exec tool",
  send_email: "Send email",
  create_goal: "Create goal",
  update_memory: "Update memory",
  other: "Other",
};

export const ELEVATED_KINDS: ReadonlySet<string> = new Set([
  "exec_tool",
  "send_email",
]);

export type StepNodeData = {
  step: WorkflowStep;
};

export type StepFlowNode = Node<StepNodeData, "wfStep">;

export function newStep(kind: HitlActionKind): WorkflowStep {
  return {
    id: `step_${Math.random().toString(36).slice(2, 9)}`,
    kind,
    summary: `New ${KIND_LABELS[kind].toLowerCase()} step`,
    target: null,
    preview: null,
    args: null,
    requiresApproval: true,
    description: null,
  };
}

const NODE_GAP_Y = 130;

export function stepsToGraph(steps: WorkflowStep[]): {
  nodes: StepFlowNode[];
  edges: Edge[];
} {
  const nodes: StepFlowNode[] = steps.map((step, i) => ({
    id: step.id,
    type: "wfStep" as const,
    position: { x: 0, y: i * NODE_GAP_Y },
    data: { step },
  }));
  const edges: Edge[] = [];
  for (let i = 0; i < steps.length - 1; i++) {
    edges.push({
      id: `e_${steps[i].id}_${steps[i + 1].id}`,
      source: steps[i].id,
      target: steps[i + 1].id,
    });
  }
  return { nodes, edges };
}

export type GraphCompileResult = {
  steps: WorkflowStep[] | null;
  errors: string[];
};

function stepLabel(data: StepNodeData | undefined, id: string): string {
  const s = data?.step;
  if (!s) return id;
  return `"${s.summary}" (${s.kind})`;
}

export function validateGraph(
  nodes: StepFlowNode[],
  edges: Edge[]
): string[] {
  const errors: string[] = [];
  const n = nodes.length;
  if (n <= 1) return errors;

  const outCount = new Map<string, number>();
  const inCount = new Map<string, number>();
  const seenIds = new Set<string>();
  for (const node of nodes) {
    if (seenIds.has(node.id)) errors.push(`Duplicate step id: ${node.id}`);
    seenIds.add(node.id);
    outCount.set(node.id, 0);
    inCount.set(node.id, 0);
  }
  const nodeIds = seenIds;
  for (const e of edges) {
    if (!nodeIds.has(e.source) || !nodeIds.has(e.target)) continue;
    if (e.source === e.target) {
      errors.push(`Step cannot connect to itself: ${stepLabel(nodes.find((nd) => nd.id === e.source)?.data, e.source)}`);
      continue;
    }
    outCount.set(e.source, (outCount.get(e.source) ?? 0) + 1);
    inCount.set(e.target, (inCount.get(e.target) ?? 0) + 1);
  }

  for (const node of nodes) {
    if ((outCount.get(node.id) ?? 0) > 1) {
      errors.push(`Branching is not supported yet (v1 runs steps in order): ${stepLabel(node.data, node.id)} has multiple outgoing connections.`);
    }
    if ((inCount.get(node.id) ?? 0) > 1) {
      errors.push(`Merging is not supported yet (v1 runs steps in order): ${stepLabel(node.data, node.id)} has multiple incoming connections.`);
    }
    if ((outCount.get(node.id) ?? 0) === 0 && (inCount.get(node.id) ?? 0) === 0) {
      errors.push(`Unconnected step: ${stepLabel(node.data, node.id)}. Connect it into the chain or delete it.`);
    }
  }
  if (errors.length > 0) return errors;

  const roots = nodes.filter((nd) => (inCount.get(nd.id) ?? 0) === 0);
  const visited = new Set<string>();
  const queue: string[] = roots.map((nd) => nd.id);
  while (queue.length > 0) {
    const id = queue.shift() as string;
    if (visited.has(id)) continue;
    visited.add(id);
    for (const e of edges) {
      if (e.source === id && !visited.has(e.target)) queue.push(e.target);
    }
  }
  if (visited.size < n) {
    errors.push("Cycle detected — connections must form a single start-to-end path.");
  }
  return errors;
}

export function graphToSteps(
  nodes: StepFlowNode[],
  edges: Edge[]
): GraphCompileResult {
  const errors = validateGraph(nodes, edges);
  if (errors.length > 0 || nodes.length === 0) {
    return { steps: errors.length > 0 ? null : [], errors };
  }

  const byId = new Map(nodes.map((nd) => [nd.id, nd]));
  const outgoing = new Map<string, string>();
  for (const e of edges) {
    if (!byId.has(e.source) || !byId.has(e.target) || e.source === e.target) continue;
    outgoing.set(e.source, e.target);
  }
  let root = nodes.find((nd) => ![...outgoing.values()].includes(nd.id));
  if (!root) root = nodes[0];

  const ordered: WorkflowStep[] = [];
  const walked = new Set<string>();
  let cursor: string | undefined = root.id;
  while (cursor && byId.has(cursor) && !walked.has(cursor)) {
    walked.add(cursor);
    ordered.push(byId.get(cursor)!.data.step);
    cursor = outgoing.get(cursor);
  }
  return { steps: ordered, errors: [] };
}

export type ConnectionCheckParams = {
  source: string;
  target: string;
};

export function connectionIsValid(
  nodes: StepFlowNode[],
  edges: Edge[],
  { source, target }: ConnectionCheckParams
): boolean {
  if (source === target) return false;
  if (!nodes.some((nd) => nd.id === source) || !nodes.some((nd) => nd.id === target)) return false;
  if (edges.some((e) => e.source === source && e.target === target)) return false;
  if (edges.some((e) => e.source === source)) return false;
  if (edges.some((e) => e.target === target)) return false;
  return true;
}
