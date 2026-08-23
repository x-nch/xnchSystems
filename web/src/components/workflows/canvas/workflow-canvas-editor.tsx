"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
  type EdgeRemoveChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ArrowRightFromLine, ListPlus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { HitlActionKind } from "@/lib/approvals/types";
import type { WorkflowStep } from "@/lib/workflows/types";
import {
  ELEVATED_KINDS,
  KIND_LABELS,
  STEP_KINDS,
  connectionIsValid,
  graphToSteps,
  newStep,
  stepsToGraph,
  validateGraph,
  type GraphCompileResult,
  type StepFlowNode,
} from "@/lib/workflows/graph";
import { KIND_ICONS } from "./step-icons";
import { StepNode } from "./step-node";

const nodeTypes = { wfStep: StepNode };

export function WorkflowCanvasEditor(props: {
  initialSteps: WorkflowStep[];
  onChange: (result: GraphCompileResult) => void;
}) {
  return (
    <ReactFlowProvider>
      <CanvasInner {...props} />
    </ReactFlowProvider>
  );
}

function CanvasInner({
  initialSteps,
  onChange,
}: {
  initialSteps: WorkflowStep[];
  onChange: (result: GraphCompileResult) => void;
}) {
  const initial = useMemo(() => stepsToGraph(initialSteps), []); // eslint-disable-line react-hooks/exhaustive-deps
  const { screenToFlowPosition } = useReactFlow();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<StepFlowNode>(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initial.edges);
  const [argsText, setArgsText] = useState<string | null>(null);

  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  });

  useEffect(() => {
    onChangeRef.current(graphToSteps(nodes, edges));
  }, [nodes, edges]);

  const errors = useMemo(() => validateGraph(nodes, edges), [nodes, edges]);
  const ordered = useMemo(
    () => graphToSteps(nodes, edges).steps,
    [nodes, edges]
  );
  const selectedId = useMemo(
    () => nodes.find((n) => n.selected)?.id ?? null,
    [nodes]
  );
  const selected = selectedId ? nodes.find((n) => n.id === selectedId) : null;
  const step = selected?.data.step ?? null;

  const selectNode = useCallback(
    (id: string | null) => {
      setNodes((nds) =>
        nds.map((n) => (n.selected || n.id === id ? { ...n, selected: n.id === id } : n))
      );
      setEdges((eds) => eds.map((e) => (e.selected ? { ...e, selected: false } : e)));
    },
    [setNodes, setEdges]
  );

  const addNode = useCallback(
    (kind: HitlActionKind) => {
      const created = newStep(kind);
      const rect = wrapperRef.current?.getBoundingClientRect();
      const center = rect
        ? screenToFlowPosition({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 })
        : { x: 0, y: 0 };
      const jitter = (nodes.length % 4) * 36 - 54;
      setNodes((nds) => [
        ...nds.map((n) => ({ ...n, selected: false })),
        {
          id: created.id,
          type: "wfStep" as const,
          position: { x: center.x - 120 + jitter, y: center.y - 60 + jitter / 2 },
          data: { step: created },
          selected: true,
        },
      ]);
    },
    [nodes.length, screenToFlowPosition, setNodes]
  );

  const removeNode = useCallback(
    (id: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== id));
      setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
    },
    [setNodes, setEdges]
  );

  const isValidConnection = useCallback(
    (c: Connection | Edge) =>
      connectionIsValid(nodes, edges, { source: c.source, target: c.target }),
    [nodes, edges]
  );

  const connect = useCallback(
    (source: string, target: string) => {
      if (!connectionIsValid(nodes, edges, { source, target })) return;
      setEdges((eds) => [...eds.map((e) => ({ ...e, selected: false })), { id: `e_${source}_${target}`, source, target }]);
    },
    [nodes, edges, setEdges]
  );

  const unlinkEdge = useCallback(
    (edgeId: string) => {
      const change: EdgeRemoveChange = { type: "remove", id: edgeId };
      onEdgesChange([change]);
    },
    [onEdgesChange]
  );

  const patchStep = useCallback(
    (patch: Partial<WorkflowStep>) => {
      if (!selectedId) return;
      // Mirror server enforcement: switching kind to an elevated kind
      // re-gates the step client-side too, so local drafts never disagree
      // with what xnch will store.
      const effective: Partial<WorkflowStep> =
        patch.kind && ELEVATED_KINDS.has(patch.kind)
          ? { ...patch, requiresApproval: true }
          : patch;
      setNodes((nds) =>
        nds.map((n) =>
          n.id === selectedId
            ? { ...n, data: { ...n.data, step: { ...n.data.step, ...effective } } }
            : n
        )
      );
    },
    [selectedId, setNodes]
  );

  const onCanvasKeyDown = useCallback(
    (e: ReactKeyboardEvent<HTMLDivElement>) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      const el = (e.target as HTMLElement).closest?.(".react-flow__node") as HTMLElement | null;
      const id = el?.getAttribute("data-id");
      if (!id || (e.target as HTMLElement) !== el) return;
      e.preventDefault();
      selectNode(id);
    },
    [selectNode]
  );

  const outgoing = edges.find((e) => e.source === selectedId) ?? null;
  const incoming = edges.find((e) => e.target === selectedId) ?? null;
  const connectableBefore = nodes.filter(
    (n) =>
      n.id !== selectedId &&
      !edges.some((e) => e.source === n.id) &&
      !edges.some((e) => e.target === selectedId)
  );
  const connectableAfter = nodes.filter(
    (n) =>
      n.id !== selectedId &&
      !edges.some((e) => e.target === n.id) &&
      !edges.some((e) => e.source === selectedId)
  );
  const labelOf = (id: string) => {
    const n = nodes.find((nd) => nd.id === id);
    return n ? `${n.data.step.summary} (${KIND_LABELS[n.data.step.kind]})` : id;
  };

  const selectedIndex = selectedId ? nodes.findIndex((n) => n.id === selectedId) : -1;
  const gotoNeighbor = (delta: number) => {
    if (nodes.length === 0) return;
    const next = ((selectedIndex < 0 ? 0 : selectedIndex + delta) + nodes.length) % nodes.length;
    selectNode(nodes[next].id);
  };

  const argsValue = argsText ?? (step?.args ? JSON.stringify(step.args, null, 2) : "");
  const argsDirty = argsText !== null;

  return (
    <div className="flex h-full min-h-0 gap-3">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-2">
        {/* Palette — full mouse-free creation path */}
        <div className="flex flex-wrap items-center gap-1.5" role="toolbar" aria-label="Add workflow step">
          <span className="mr-1 flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            <ListPlus className="h-3 w-3" aria-hidden /> Add step
          </span>
          {STEP_KINDS.map((kind) => {
            const Icon = KIND_ICONS[kind];
            return (
              <Button
                key={kind}
                type="button"
                size="sm"
                variant="outline"
                onClick={() => addNode(kind)}
                aria-label={`Add ${KIND_LABELS[kind]} step`}
                className="h-7 gap-1 px-2 text-[11px]"
              >
                <Icon className="h-3 w-3" aria-hidden />
                {KIND_LABELS[kind]}
              </Button>
            );
          })}
        </div>

        {errors.length > 0 && (
          <ul
            role="alert"
            aria-label="Workflow structure problems"
            className="space-y-0.5 rounded-lg border border-[var(--state-destructive)] bg-[var(--state-destructive)]/10 px-3 py-2 text-xs leading-5 text-[var(--destructive)]"
          >
            {errors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        )}

        <div
          ref={wrapperRef}
          onKeyDown={onCanvasKeyDown}
          className="workflow-canvas relative min-h-[280px] flex-1 overflow-hidden rounded-xl border border-border bg-background"
        >
          <ReactFlow<StepFlowNode>
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onPaneClick={() => selectNode(null)}
            isValidConnection={isValidConnection}
            deleteKeyCode={["Backspace", "Delete"]}
            connectionLineStyle={{ stroke: "#7A869F", strokeWidth: 1.5 }}
            fitView
            fitViewOptions={{ padding: 0.25, maxZoom: 1 }}
            minZoom={0.2}
            maxZoom={1.75}
            proOptions={{ hideAttribution: true }}
            panOnScroll
            zoomOnDoubleClick={false}
            className="bg-transparent"
          >
            <Background variant={BackgroundVariant.Dots} gap={28} size={0.7} color="rgba(242,244,247,0.07)" />
            <Controls showInteractive={false} position="bottom-right" />
            {nodes.length === 0 && (
              <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">
                <p className="max-w-xs rounded-lg border border-dashed border-border bg-card/80 px-4 py-3 text-center text-xs leading-5 text-muted-foreground">
                  Empty canvas. Use “Add step” above, then connect nodes top-to-bottom — connections define run order.
                </p>
              </div>
            )}
          </ReactFlow>
        </div>
      </div>

      {/* Config panel */}
      <aside
        aria-label="Step configuration"
        className="flex w-72 shrink-0 flex-col gap-3 overflow-y-auto rounded-xl border border-border bg-card p-3"
      >
        {!step ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-1 text-center">
            <p className="text-sm font-medium text-foreground">No step selected</p>
            <p className="text-xs leading-5 text-muted-foreground">
              Select a node on the canvas (click, Tab+Enter, or the chain list below) to edit it.
            </p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Step config</span>
              <span className="flex gap-1">
                <Button type="button" size="sm" variant="outline" className="h-6 px-2 text-[11px]" onClick={() => gotoNeighbor(-1)} aria-label="Select previous step in list">
                  ◀ Prev
                </Button>
                <Button type="button" size="sm" variant="outline" className="h-6 px-2 text-[11px]" onClick={() => gotoNeighbor(1)} aria-label="Select next step in list">
                  Next ▶
                </Button>
              </span>
            </div>

            <label className="grid gap-1">
              <span className="text-xs font-medium text-foreground">Kind</span>
              <select
                value={step.kind}
                onChange={(e) => patchStep({ kind: e.target.value as HitlActionKind })}
                className="h-8 rounded-lg border border-border bg-input px-2 text-sm text-foreground"
                aria-label="Step kind"
              >
                {STEP_KINDS.map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
              </select>
            </label>

            <label className="grid gap-1">
              <span className="text-xs font-medium text-foreground">Summary</span>
              <Input
                value={step.summary}
                onChange={(e) => patchStep({ summary: e.target.value })}
                placeholder="What this step does"
                className="h-8 text-sm"
                aria-label="Step summary"
              />
            </label>

            <label className="grid gap-1">
              <span className="text-xs font-medium text-foreground">Target</span>
              <Input
                value={step.target ?? ""}
                onChange={(e) => patchStep({ target: e.target.value || null })}
                placeholder="path / tool / address"
                className="h-8 font-mono text-xs"
                aria-label="Step target"
              />
            </label>

            <label className="grid gap-1">
              <span className="text-xs font-medium text-foreground">Preview</span>
              <Textarea
                value={step.preview ?? ""}
                onChange={(e) => patchStep({ preview: e.target.value || null })}
                rows={2}
                placeholder="Shown for approval review"
                className="font-mono text-xs"
                aria-label="Step preview"
              />
            </label>

            <label className="grid gap-1">
              <span className="text-xs font-medium text-foreground">Args (JSON)</span>
              <Textarea
                value={argsValue}
                onChange={(e) => setArgsText(e.target.value)}
                onBlur={() => {
                  if (!argsDirty) return;
                  try {
                    const parsed = argsValue.trim() === "" ? null : JSON.parse(argsValue);
                    patchStep({ args: parsed });
                    setArgsText(null);
                  } catch {
                    /* keep editing — invalid JSON not committed */
                  }
                }}
                rows={3}
                placeholder="{}"
                className="font-mono text-xs"
                aria-label="Step arguments as JSON"
              />
              <span className="text-[10px] leading-4 text-muted-foreground">
                Reference secrets by name/id only — resolved server-side at run time.
              </span>
            </label>

            <label className="flex items-start gap-2 text-xs leading-5">
              <input
                type="checkbox"
                checked={step.requiresApproval || ELEVATED_KINDS.has(step.kind)}
                onChange={(e) => patchStep({ requiresApproval: e.target.checked })}
                disabled={ELEVATED_KINDS.has(step.kind)}
                className="mt-0.5 rounded"
                aria-label="Requires approval"
              />
              <span>
                <span className={(step.requiresApproval || ELEVATED_KINDS.has(step.kind)) ? "font-medium text-[var(--accent)]" : "text-muted-foreground"}>
                  Requires approval
                </span>
                {ELEVATED_KINDS.has(step.kind) && (
                  <span className="block text-[10px] text-muted-foreground">
                    Locked on — exec_tool / send_email are always gated server-side.
                  </span>
                )}
              </span>
            </label>

            <div className="rounded-lg border border-border p-2">
              <span className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Connections
              </span>
              <div className="space-y-1 text-xs">
                <div className="flex items-center gap-1">
                  <ArrowRightFromLine className="h-3 w-3 rotate-180 text-muted-foreground" aria-hidden />
                  {incoming ? (
                    <>
                      <span className="truncate text-muted-foreground">from {labelOf(incoming.source)}</span>
                      <Button type="button" size="sm" variant="ghost" className="ml-auto h-6 w-6 shrink-0 p-0" onClick={() => unlinkEdge(incoming.id)} aria-label={`Remove connection from ${labelOf(incoming.source)}`}>
                        <Trash2 className="h-3 w-3" aria-hidden />
                      </Button>
                    </>
                  ) : (
                    <select
                      value=""
                      onChange={(e) => e.target.value && connect(e.target.value, step.id)}
                      className="h-7 w-full rounded-md border border-border bg-input px-1.5 text-xs"
                      aria-label="Run after step"
                    >
                      <option value="">— runs after… —</option>
                      {connectableBefore.map((n) => (
                        <option key={n.id} value={n.id}>{labelOf(n.id)}</option>
                      ))}
                    </select>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <ArrowRightFromLine className="h-3 w-3 text-muted-foreground" aria-hidden />
                  {outgoing ? (
                    <>
                      <span className="truncate text-muted-foreground">to {labelOf(outgoing.target)}</span>
                      <Button type="button" size="sm" variant="ghost" className="ml-auto h-6 w-6 shrink-0 p-0" onClick={() => unlinkEdge(outgoing.id)} aria-label={`Remove connection to ${labelOf(outgoing.target)}`}>
                        <Trash2 className="h-3 w-3" aria-hidden />
                      </Button>
                    </>
                  ) : (
                    <select
                      value=""
                      onChange={(e) => e.target.value && connect(step.id, e.target.value)}
                      className="h-7 w-full rounded-md border border-border bg-input px-1.5 text-xs"
                      aria-label="Run before next step"
                    >
                      <option value="">— runs into… —</option>
                      {connectableAfter.map((n) => (
                        <option key={n.id} value={n.id}>{labelOf(n.id)}</option>
                      ))}
                    </select>
                  )}
                </div>
              </div>
            </div>

            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => removeNode(step.id)}
              className="mt-auto h-7 gap-1 self-start text-xs text-muted-foreground hover:text-destructive"
              aria-label={`Delete step ${step.summary}`}
            >
              <Trash2 className="h-3 w-3" aria-hidden /> Delete step
            </Button>
          </>
        )}

        {/* Chain outline — mouse-free selection over the whole graph */}
        {ordered && ordered.length > 0 && (
          <nav aria-label="Execution order outline" className="border-t border-border pt-2">
            <span className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
              Run order
            </span>
            <ol className="space-y-0.5">
              {ordered.map((s, i) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => selectNode(s.id)}
                    aria-current={s.id === selectedId ? "true" : undefined}
                    className={`w-full truncate rounded px-1.5 py-1 text-left text-[11px] ${s.id === selectedId ? "bg-[var(--accent-subtle)] text-[var(--accent)]" : "text-muted-foreground hover:text-foreground"}`}
                  >
                    {i + 1}. {s.summary}
                  </button>
                </li>
              ))}
            </ol>
          </nav>
        )}
      </aside>
    </div>
  );
}
