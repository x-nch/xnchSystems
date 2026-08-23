import { describe, expect, it } from "vitest";
import {
  connectionIsValid,
  graphToSteps,
  newStep,
  stepsToGraph,
  validateGraph,
  type StepFlowNode,
} from "./graph";
import type { WorkflowStep } from "./types";

function makeStep(id: string, summary?: string): WorkflowStep {
  return {
    id,
    kind: "other",
    summary: summary ?? `step ${id}`,
    target: null,
    preview: null,
    args: null,
    requiresApproval: false,
    description: null,
  };
}

function ids(steps: WorkflowStep[] | null): string[] {
  return steps ? steps.map((s) => s.id) : [];
}

describe("stepsToGraph", () => {
  it("chains consecutive steps into edges", () => {
    const { nodes, edges } = stepsToGraph([makeStep("a"), makeStep("b"), makeStep("c")]);
    expect(nodes).toHaveLength(3);
    expect(edges.map((e) => [e.source, e.target])).toEqual([
      ["a", "b"],
      ["b", "c"],
    ]);
  });

  it("returns empty graph for zero steps", () => {
    const { nodes, edges } = stepsToGraph([]);
    expect(nodes).toHaveLength(0);
    expect(edges).toHaveLength(0);
  });
});

describe("graphToSteps", () => {
  it("round-trips a linear chain preserving step data", () => {
    const original = [
      { ...makeStep("a", "first"), kind: "exec_tool" as const, requiresApproval: true },
      makeStep("b", "second"),
      { ...makeStep("c", "third"), target: "reports/x.md" },
    ];
    const { nodes, edges } = stepsToGraph(original);
    const result = graphToSteps(nodes as StepFlowNode[], edges);
    expect(result.errors).toEqual([]);
    expect(ids(result.steps)).toEqual(["a", "b", "c"]);
    expect(result.steps![0].kind).toBe("exec_tool");
    expect(result.steps![2].target).toBe("reports/x.md");
  });

  it("returns ordered steps when user reorders by reconnecting", () => {
    const { nodes } = stepsToGraph([makeStep("a"), makeStep("b")]);
    // user rewires so b runs before a
    const rewired = [
      { id: "e_b_a", source: "b", target: "a" },
    ];
    const result = graphToSteps(nodes as StepFlowNode[], rewired);
    expect(result.errors).toEqual([]);
    expect(ids(result.steps)).toEqual(["b", "a"]);
  });

  it("rejects branching (multiple outgoing)", () => {
    const { nodes } = stepsToGraph([makeStep("a"), makeStep("b"), makeStep("c")]);
    const edges = [
      { id: "e1", source: "a", target: "b" },
      { id: "e2", source: "a", target: "c" },
    ];
    const result = graphToSteps(nodes as StepFlowNode[], edges);
    expect(result.steps).toBeNull();
    expect(result.errors.some((e) => e.includes("Branching"))).toBe(true);
  });

  it("rejects merging (multiple incoming)", () => {
    const { nodes } = stepsToGraph([makeStep("a"), makeStep("b"), makeStep("c")]);
    const edges = [
      { id: "e1", source: "a", target: "c" },
      { id: "e2", source: "b", target: "c" },
    ];
    const result = graphToSteps(nodes as StepFlowNode[], edges);
    expect(result.steps).toBeNull();
    expect(result.errors.some((e) => e.includes("Merging"))).toBe(true);
  });

  it("rejects cycles", () => {
    const { nodes } = stepsToGraph([makeStep("a"), makeStep("b")]);
    const edges = [
      { id: "e1", source: "a", target: "b" },
      { id: "e2", source: "b", target: "a" },
    ];
    const result = graphToSteps(nodes as StepFlowNode[], edges);
    expect(result.steps).toBeNull();
    expect(result.errors.some((e) => e.includes("Cycle"))).toBe(true);
  });

  it("rejects unconnected steps when more than one node", () => {
    const { nodes, edges } = stepsToGraph([makeStep("a"), makeStep("b")]);
    const orphaned = nodes.map((nd, i) =>
      i === 1 ? { ...nd, position: { ...nd.position } } : nd
    );
    const result = graphToSteps(orphaned as StepFlowNode[], []);
    void edges;
    expect(result.steps).toBeNull();
    expect(result.errors.some((e) => e.includes("Unconnected step"))).toBe(true);
  });

  it("accepts a single node with no edges", () => {
    const { nodes } = stepsToGraph([makeStep("solo")]);
    const result = graphToSteps(nodes as StepFlowNode[], []);
    expect(result.errors).toEqual([]);
    expect(ids(result.steps)).toEqual(["solo"]);
  });

  it("returns empty steps for an empty canvas without errors", () => {
    const result = graphToSteps([], []);
    expect(result.errors).toEqual([]);
    expect(result.steps).toEqual([]);
  });
});

describe("connectionIsValid", () => {
  const { nodes } = stepsToGraph([makeStep("a"), makeStep("b"), makeStep("c")]);
  const flowNodes = nodes as StepFlowNode[];
  const existing = [{ id: "e1", source: "a", target: "b" }];

  it("allows connecting c -> nothing-yet-connected pair", () => {
    expect(connectionIsValid(flowNodes, existing, { source: "b", target: "c" })).toBe(true);
  });

  it("rejects self loops, duplicates, branches, merges", () => {
    expect(connectionIsValid(flowNodes, existing, { source: "b", target: "b" })).toBe(false);
    expect(connectionIsValid(flowNodes, existing, { source: "a", target: "b" })).toBe(false);
    expect(connectionIsValid(flowNodes, existing, { source: "a", target: "c" })).toBe(false);
    expect(connectionIsValid(flowNodes, existing, { source: "c", target: "b" })).toBe(false);
  });
});

describe("newStep", () => {
  it("creates unique gated steps with matching kind", () => {
    const a = newStep("send_email");
    const b = newStep("send_email");
    expect(a.id).not.toBe(b.id);
    expect(a.kind).toBe("send_email");
    expect(a.requiresApproval).toBe(true);
  });
});

describe("validateGraph", () => {
  it("passes single-node graphs and reports nothing for empty", () => {
    expect(validateGraph([], [])).toEqual([]);
    const { nodes } = stepsToGraph([makeStep("x")]);
    expect(validateGraph(nodes as StepFlowNode[], [])).toEqual([]);
  });
});
