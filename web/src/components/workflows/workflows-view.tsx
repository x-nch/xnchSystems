"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Clock3, Copy, FilePlus, Play, Pencil, Trash2, Workflow as WorkflowIcon, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { useWorkflowStore } from "@/lib/stores/workflow-store";
import { useServerWorkflows, useServerRuns, useWorkflowMutations } from "@/lib/hooks/use-workflows-api";
import { workflowDtoToLocal } from "@/lib/approvals/adapters";
import { useConnectionState } from "@/components/layout/connection-status";
import { WorkflowCanvasEditor } from "@/components/workflows/canvas/workflow-canvas-editor";
import type { GraphCompileResult } from "@/lib/workflows/graph";
import type { Workflow, WorkflowStep, WorkflowTrigger } from "@/lib/workflows/types";
import type { HitlActionKind } from "@/lib/approvals/types";

function kindLabel(k: HitlActionKind): string {
  switch (k) {
    case "write_file": return "WRITE FILE";
    case "exec_tool": return "EXEC TOOL";
    case "send_email": return "SEND EMAIL";
    case "create_goal": return "CREATE GOAL";
    case "update_memory": return "UPDATE MEMORY";
    default: return k.toUpperCase();
  }
}

function triggerLabel(t: WorkflowTrigger): string {
  if (t.kind === "schedule") return t.cron ? `schedule · ${t.cron}` : "schedule";
  return "manual";
}

function useDraftWorkflow(initial?: Workflow | null) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [triggerKind, setTriggerKind] = useState<WorkflowTrigger["kind"]>(initial?.trigger.kind ?? "manual");
  const [cron, setCron] = useState(initial?.trigger.cron ?? "0 9 * * 1");
  const [steps, setSteps] = useState<WorkflowStep[]>(initial?.steps ?? []);
  /* eslint-disable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */
  useEffect(() => {
    if (initial) {
      setName(initial.name);
      setDescription(initial.description ?? "");
      setTriggerKind(initial.trigger.kind);
      setCron(initial.trigger.cron ?? "0 9 * * 1");
      setSteps(initial.steps);
    } else {
      setName("");
      setDescription("");
      setTriggerKind("manual");
      setCron("0 9 * * 1");
      setSteps([]);
    }
  }, [initial?.id]);
  /* eslint-enable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */
  return { name, setName, description, setDescription, triggerKind, setTriggerKind, cron, setCron, steps, setSteps };
}

export function WorkflowsView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const localWorkflows = useWorkflowStore((s) => s.workflows);
  const runs = useWorkflowStore((s) => s.runs);

  // P4: gateway-first with local fallback while offline
  const connection = useConnectionState();
  const online = connection === "online";
  const serverWfs = useServerWorkflows(online);
  const serverRuns = useServerRuns(online);
  const api = useWorkflowMutations();

  const serverMapped = (serverWfs.data ?? []).map(workflowDtoToLocal);
  const workflows = online && serverWfs.data ? serverMapped : localWorkflows;
  const runsView =
    online && serverRuns.data
      ? serverRuns.data.map((r) => ({
          id: r.id,
          workflowId: r.workflow_id,
          workflowName:
            (r.steps?.[0] as unknown as { summary?: string } | undefined)?.summary ??
            r.id,
          status: r.status.toLowerCase() as "running" | "completed" | "failed" | "cancelled",
          created_at: new Date(r.created_at * 1000).toISOString(),
          stepCount: r.steps?.length ?? 0,
          approvalsCreated:
            r.steps?.filter((s) => s.status === "AWAITING_APPROVAL").length ?? 0,
        }))
      : runs;
  const createWorkflow = useWorkflowStore((s) => s.createWorkflow);
  const updateWorkflow = useWorkflowStore((s) => s.updateWorkflow);
  const deleteWorkflow = useWorkflowStore((s) => s.deleteWorkflow);
  const duplicateWorkflow = useWorkflowStore((s) => s.duplicateWorkflow);
  const runWorkflow = useWorkflowStore((s) => s.runWorkflow);

  const selectedId = searchParams.get("selected");
  const selected = useMemo(() => workflows.find((w) => w.id === selectedId) ?? null, [workflows, selectedId]);
  const [builderOpen, setBuilderOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const editingWorkflow = useMemo(() => workflows.find((w) => w.id === editingId) ?? null, [workflows, editingId]);
  const draft = useDraftWorkflow(editingWorkflow);
  const [compiled, setCompiled] = useState<GraphCompileResult>({ steps: [], errors: [] });
  const saveSteps = compiled.steps;
  const [toast, setToast] = useState<string | null>(null);

  const openCreate = () => {
    setEditingId(null);
    setCompiled({ steps: [], errors: [] });
    setBuilderOpen(true);
  };
  const openEdit = (id: string) => {
    setEditingId(id);
    setCompiled({ steps: workflows.find((w) => w.id === id)?.steps ?? [], errors: [] });
    setBuilderOpen(true);
  };
  const setSelected = (id: string | null) => {
    const p = new URLSearchParams(searchParams.toString());
    if (id) p.set("selected", id); else p.delete("selected");
    const qs = p.toString();
    router.replace(qs ? `?${qs}` : "?", { scroll: false });
  };

  const handleSaveOnline = async () => {
    if (!saveSteps) return;
    const trigger =
      draft.triggerKind === "schedule"
        ? { kind: "schedule" as const, cron: draft.cron.trim() || "0 9 * * 1" }
        : { kind: "manual" as const };
    const steps = saveSteps.map((s) => ({
      id: s.id,
      kind: s.kind,
      summary: s.summary,
      target: s.target ?? null,
      args: s.args ?? null,
      preview: s.preview ?? null,
      requires_approval: s.requiresApproval,
      description: s.description ?? null,
    }));
    try {
      if (editingId) {
        await api.update.mutateAsync({
          id: editingId,
          body: {
            name: draft.name.trim(),
            description: draft.description.trim() || null,
            trigger,
            steps,
          },
        });
      } else {
        const createdWf = await api.create.mutateAsync({
          name: draft.name.trim(),
          description: draft.description.trim() || null,
          trigger,
          steps,
          owner_actor_id: "operator",
        });
        setSelected(createdWf.id);
      }
      setBuilderOpen(false);
    } catch {
      setToast("Gateway rejected workflow change — staying in builder");
      setTimeout(() => setToast(null), 4000);
    }
  };

  const handleRunOnline = async (id: string) => {
    try {
      const res = await api.run.mutateAsync(id);
      const n = res.steps?.filter((s) => s.status === "AWAITING_APPROVAL").length ?? 0;
      setToast(`Workflow ran — ${n} approval${n === 1 ? "" : "s"} created · check Approvals`);
      setTimeout(() => setToast(null), 4000);
    } catch {
      setToast("Run failed — gateway error");
      setTimeout(() => setToast(null), 4000);
    }
  };

  const handleSave = () => {
    if (online) return void handleSaveOnline();
    const nameTrim = draft.name.trim();
    if (!nameTrim || !saveSteps || saveSteps.length === 0) return;
    const trigger: WorkflowTrigger = draft.triggerKind === "schedule" ? { kind: "schedule", cron: draft.cron.trim() || "0 9 * * 1" } : { kind: "manual" };
    if (editingId) {
      updateWorkflow(editingId, { name: nameTrim, description: draft.description.trim() || null, trigger, steps: saveSteps });
    } else {
      const id = createWorkflow({ name: nameTrim, description: draft.description.trim() || null, trigger, steps: saveSteps });
      setSelected(id);
    }
    setBuilderOpen(false);
  };

  const handleRun = (id: string) => {
    if (online) return void handleRunOnline(id);
    const res = runWorkflow(id);
    if (res) {
      setToast(`Workflow ran — ${res.approvalsCreated} approval${res.approvalsCreated===1?"":"s"} created · check Approvals`);
      setTimeout(() => setToast(null), 4000);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      {/* Header */}
      <div className="flex shrink-0 flex-wrap items-center gap-3 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent/15">
            <WorkflowIcon className="h-3.5 w-3.5 text-accent" />
          </span>
          <h1 className="font-display text-xl font-semibold tracking-tight text-foreground">Workflows</h1>
          <Badge tone="muted" className="hidden md:inline-flex">{workflows.length} total</Badge>
        </div>
        <span className="hidden text-xs text-muted-foreground md:inline">Playbooks → approvals (HITL-gated)</span>
        <span className="flex-1" />
        <Button onClick={openCreate} size="sm" className="btn-accent gap-1.5">
          <FilePlus className="h-3.5 w-3.5" /> New workflow
        </Button>
      </div>

      <div className="border-b border-[var(--state-attention)] bg-[var(--accent-subtle)] px-4 py-2 text-xs leading-5">
        <span className="font-medium text-[var(--accent)]">Builder</span>
        <span className="text-muted-foreground"> — canvas editing saves locally this phase; runs create approvals in </span>
        <button onClick={() => router.push("/")} className="underline decoration-[var(--state-attention)] underline-offset-4 text-foreground hover:text-[var(--accent)]">Approvals</button>
        <span className="text-muted-foreground">. Server-side validation re-checks every step on save.</span>
      </div>

      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        {/* List */}
        <div className="flex min-h-0 flex-1 flex-col border-border md:max-w-[520px] md:border-r">
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {workflows.length === 0 ? (
              <Card className="border-dashed">
                <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
                  <WorkflowIcon className="h-8 w-8 text-muted-foreground/40" />
                  <p className="text-sm font-medium text-foreground">No workflows yet</p>
                  <p className="max-w-sm text-xs leading-5 text-muted-foreground">Create a playbook — e.g. “Research → Draft → Send”. Each step with “requires approval” will become a pending item in Approvals when you Run.</p>
                  <Button onClick={openCreate} size="sm" variant="outline">Create first workflow</Button>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-3">
                {workflows.map((wf, i) => {
                  const isSelected = wf.id === selectedId;
                  const gated = wf.steps.filter((s) => s.requiresApproval).length;
                  return (
                    <div
                      key={wf.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelected(wf.id)}
                      onKeyDown={(e) => { if (e.key==="Enter"||e.key===" ") { e.preventDefault(); setSelected(wf.id);} }}
                      style={{ ["--stagger-index" as string]: String(i)} as React.CSSProperties}
                      className={cn(
                        "motion-row-enter motion-hover-lift group relative flex flex-col gap-2 rounded-xl border bg-card p-4 text-left",
                        isSelected ? "border-[var(--state-attention)] bg-[var(--accent-subtle)]/40" : "border-border hover:bg-muted/30"
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="truncate font-display text-[13px] font-semibold text-foreground">{wf.name}</span>
                            <Badge tone={wf.trigger.kind==="schedule" ? "warning" : "muted"} className="shrink-0 gap-1">
                              {wf.trigger.kind==="schedule" ? <Clock3 className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                              {triggerLabel(wf.trigger)}
                            </Badge>
                          </div>
                          {wf.description && <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{wf.description}</p>}
                        </div>
                        <span className="shrink-0 rounded-md bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">{wf.steps.length} steps · {gated} gated</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {wf.steps.slice(0,4).map((s) => (
                          <span key={s.id} className={cn("rounded-md border px-1.5 py-0.5 font-mono text-[10px]", s.requiresApproval ? "border-[var(--state-attention)] bg-[var(--accent-subtle)] text-[var(--accent)]" : "border-border bg-muted text-muted-foreground")}>
                            {kindLabel(s.kind)}
                          </span>
                        ))}
                        {wf.steps.length>4 && <span className="text-[10px] text-muted-foreground">+{wf.steps.length-4}</span>}
                      </div>
                      <div className="mt-1 flex flex-wrap gap-2">
                        <Button size="sm" onClick={(e)=>{e.stopPropagation(); handleRun(wf.id);}} className="btn-accent h-7 gap-1.5 px-3 text-xs">
                          <Play className="h-3 w-3" /> Run
                        </Button>
                        <Button size="sm" variant="ghost" onClick={(e)=>{e.stopPropagation(); openEdit(wf.id);}} className="h-7 gap-1 text-xs">
                          <Pencil className="h-3 w-3" /> Edit
                        </Button>
                        <Button size="sm" variant="ghost" onClick={(e)=>{
                  e.stopPropagation();
                  if(online){
                    void api.create.mutateAsync({
                      name:`${wf.name} (copy)`,
                      description: wf.description ?? null,
                      trigger:{kind:wf.trigger.kind, cron:"cron" in wf.trigger ? String((wf.trigger as {cron?:string}).cron ?? "") : undefined},
                      steps: wf.steps.map(s=>({id:s.id, kind:s.kind, summary:s.summary, target:s.target??null, args:s.args??null, preview:s.preview??null, requires_approval:s.requiresApproval, description:s.description??null})),
                      owner_actor_id:"operator",
                    }).then(()=>undefined).catch(()=>undefined);
                  } else duplicateWorkflow(wf.id);
                }} className="h-7 gap-1 text-xs">
                          <Copy className="h-3 w-3" /> Duplicate
                        </Button>
                        <Button size="sm" variant="ghost" onClick={(e)=>{
                  e.stopPropagation();
                  if(!confirm(`Delete "${wf.name}"?`)) return;
                  if(online) void api.remove.mutateAsync(wf.id);
                  else deleteWorkflow(wf.id);
                }} className="h-7 gap-1 text-xs text-muted-foreground hover:text-destructive">
                          <Trash2 className="h-3 w-3" /> Delete
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            {runsView.length>0 && (
              <div className="mt-6">
                <h3 className="px-1 pb-2 font-mono text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Recent runs</h3>
                <div className="space-y-1">
                  {runsView.slice(0,6).map((r)=> (
                    <div key={r.id} className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs">
                      <span className="h-1.5 w-1.5 rounded-full bg-[var(--state-healthy)]" />
                      <span className="truncate font-medium text-foreground">{r.workflowName}</span>
                      <span className="text-muted-foreground">· {r.approvalsCreated} approvals · {new Date(r.created_at).toLocaleTimeString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Detail */}
        <div className={cn("flex min-h-0 flex-1 flex-col bg-background", !selected && "hidden md:flex")}>
          {!selected ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
              <ShieldCheck className="h-8 w-8 text-muted-foreground/30" />
              <p className="text-sm font-medium text-foreground">Select a workflow</p>
              <p className="max-w-sm text-xs leading-5 text-muted-foreground">Workflows are HITL playbooks. “Run” creates one approval per gated step — approve/reject them in Approvals.</p>
            </div>
          ) : (
            <div key={selected.id} className="motion-pane-enter flex min-h-0 flex-1 flex-col overflow-hidden">
              <div className="flex items-center gap-2 border-b border-border px-4 py-3">
                <button onClick={()=>setSelected(null)} className="inline-flex h-7 items-center rounded-md border border-border px-2 text-xs text-muted-foreground hover:text-foreground md:hidden">← Back</button>
                <div className="min-w-0">
                  <h2 className="font-display truncate text-sm font-semibold text-foreground">{selected.name}</h2>
                  <p className="truncate font-mono text-xs text-muted-foreground">{triggerLabel(selected.trigger)} · {selected.steps.length} steps</p>
                </div>
                <span className="ml-auto" />
                <Button size="sm" variant="outline" onClick={()=>openEdit(selected.id)}><Pencil className="h-3.5 w-3.5" /> Edit</Button>
                <Button size="sm" onClick={()=>handleRun(selected.id)} className="btn-accent gap-1.5"><Play className="h-3.5 w-3.5" /> Run</Button>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto p-4">
                <div className="space-y-4">
                  {selected.description && <p className="rounded-lg border border-border bg-card p-3 text-xs leading-5 text-muted-foreground">{selected.description}</p>}
                  <div className="space-y-2">
                    {selected.steps.map((s, idx)=> (
                      <div key={s.id} className="flex gap-3 rounded-xl border border-border bg-card p-3">
                        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent text-[11px] font-bold text-accent-foreground">{idx+1}</div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-md border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">{kindLabel(s.kind)}</span>
                            {s.requiresApproval ? <span className="rounded-md border border-[var(--state-attention)] bg-[var(--accent-subtle)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--accent)]">gated</span> : <span className="rounded-md border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">auto</span>}
                            {s.target && <span className="truncate rounded bg-code-bg px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">{s.target}</span>}
                          </div>
                          <p className="mt-1 text-sm font-medium text-foreground">{s.summary}</p>
                          {s.preview && <pre className="mt-1 max-h-[120px] overflow-auto rounded border border-border bg-background p-2 font-mono text-xs text-muted-foreground">{s.preview}</pre>}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="rounded-xl border border-dashed border-border p-3 text-xs leading-5 text-muted-foreground">
                    On Run, each <span className="rounded bg-[var(--accent-subtle)] px-1 py-px font-mono text-[var(--accent)]">gated</span> step becomes a <span className="font-medium text-foreground">pending approval</span> (trigger <span className="font-mono">workflow:{selected.id}</span>) — decide in Approvals. Non-gated steps are skipped in this prototype (future: auto-execute).
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Builder */}
      <Dialog open={builderOpen} onOpenChange={setBuilderOpen}>
        <DialogContent className="flex max-h-[90vh] flex-col overflow-hidden p-0 sm:max-w-[1060px]">
          <DialogHeader>
            <DialogTitle>{editingId ? "Edit workflow" : "New workflow"}</DialogTitle>
            <DialogDescription>
              Drag nodes to arrange, connect top-to-bottom — the chain defines run order. Fully keyboard-operable: Tab to the canvas, Enter selects a node; add via palette, wire via Connections.
            </DialogDescription>
          </DialogHeader>
          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-5 pb-2">
            <div className="grid gap-4">
              <div className="grid gap-4 md:grid-cols-[1fr_1fr_auto]">
                <label className="grid gap-1.5">
                  <span className="text-xs font-medium text-foreground">Name *</span>
                  <Input value={draft.name} onChange={(e)=>draft.setName(e.target.value)} placeholder="e.g. Weekly Digest" />
                </label>
                <label className="grid gap-1.5">
                  <span className="text-xs font-medium text-foreground">Description</span>
                  <Input value={draft.description} onChange={(e)=>draft.setDescription(e.target.value)} placeholder="What this playbook does…" />
                </label>
                <div className="flex items-end gap-2">
                  <label className="grid gap-1.5">
                    <span className="text-xs font-medium text-foreground">Trigger</span>
                    <select value={draft.triggerKind} onChange={(e)=>draft.setTriggerKind(e.target.value as WorkflowTrigger["kind"])} aria-label="Trigger kind" className="h-9 rounded-lg border border-border bg-input px-2 text-sm text-foreground">
                      <option value="manual">manual</option>
                      <option value="schedule">schedule</option>
                    </select>
                  </label>
                  {draft.triggerKind==="schedule" && (
                    <label className="grid gap-1.5">
                      <span className="sr-only">Cron expression</span>
                      <Input value={draft.cron} onChange={(e)=>draft.setCron(e.target.value)} placeholder="0 9 * * 1" className="h-9 w-32 font-mono" aria-label="Cron expression" />
                    </label>
                  )}
                </div>
              </div>
              <div className="h-[52vh] min-h-[380px]">
                <WorkflowCanvasEditor
                  key={editingId ?? "new"}
                  initialSteps={editingWorkflow?.steps ?? []}
                  onChange={(result) => setCompiled(result)}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={()=>setBuilderOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={!draft.name.trim() || !saveSteps || saveSteps.length===0} className="btn-accent">Save workflow</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {toast && (
        <div className="motion-toast pointer-events-auto fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 shadow-xl">
          <span className="text-sm text-foreground">{toast}</span>
          <Button size="sm" variant="outline" onClick={()=>router.push("/")} className="h-7">Open Approvals</Button>
        </div>
      )}
    </div>
  );
}
