"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Workflow, WorkflowRun } from "@/lib/workflows/types";
import type { HitlRequest } from "@/lib/approvals/types";
import { useApprovalStore } from "@/lib/stores/approval-store";

function uid(prefix = "wf"): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 9)}`;
}
function nowIso(offsetMs = 0): string {
  return new Date(Date.now() + offsetMs).toISOString();
}

function seedWorkflows(): Workflow[] {
  return [
    {
      id: "wf_digest",
      name: "Weekly Digest",
      description: "Collect highlights → draft summary → send to team (each step approval-gated)",
      trigger: { kind: "schedule", cron: "0 9 * * 1", label: "Mon 09:00" },
      created_at: nowIso(-7 * 24 * 60 * 60 * 1000),
      updated_at: nowIso(-2 * 60 * 60 * 1000),
      steps: [
        {
          id: "step_collect",
          kind: "exec_tool",
          summary: "Collect highlights via web_search",
          target: "web_search",
          preview: 'args: {"query": "xnch weekly highlights", "limit": 5}',
          args: { tool: "web_search", query: "xnch weekly highlights" },
          requiresApproval: true,
          description: "Agent will search and propose highlights",
        },
        {
          id: "step_draft",
          kind: "write_file",
          summary: "Draft reports/weekly.md",
          target: "reports/weekly.md",
          preview: "# Weekly Digest — template\n\n- Highlights: {{step1.output}}\n- Next steps: ...",
          args: { path: "reports/weekly.md" },
          requiresApproval: true,
          description: "Writes draft, needs human review before send",
        },
        {
          id: "step_send",
          kind: "send_email",
          summary: "Send email to team@",
          target: "team@xnch.local",
          preview: "Subject: Weekly digest\n\n{{step2.output}}",
          args: { to: "team@xnch.local" },
          requiresApproval: true,
          description: "External side-effect — always gated",
        },
      ],
    },
    {
      id: "wf_research",
      name: "Research → Draft → Remember",
      description: "Manual playbook: research a topic, draft a note, remember the insight",
      trigger: { kind: "manual", label: "Run manually" },
      created_at: nowIso(-3 * 24 * 60 * 60 * 1000),
      updated_at: nowIso(-60 * 60 * 1000),
      steps: [
        {
          id: "step_r1",
          kind: "exec_tool",
          summary: "Research via web_search",
          target: "web_search",
          preview: 'args: {"query": "{{topic}}"}',
          args: { tool: "web_search" },
          requiresApproval: false,
          description: "Auto — low risk, no approval needed",
        },
        {
          id: "step_r2",
          kind: "write_file",
          summary: "Draft reports/research.md",
          target: "reports/research.md",
          preview: "Draft from research output",
          args: { path: "reports/research.md" },
          requiresApproval: true,
          description: null,
        },
        {
          id: "step_r3",
          kind: "update_memory",
          summary: "Remember insight",
          target: "memory",
          preview: "content: '{{step2.output}}' → semantic memory",
          args: {},
          requiresApproval: true,
          description: null,
        },
      ],
    },
  ];
}

interface WorkflowState {
  workflows: Workflow[];
  runs: WorkflowRun[];
  createWorkflow: (w: Omit<Workflow, "id" | "created_at" | "updated_at">) => string;
  updateWorkflow: (id: string, patch: Partial<Workflow>) => void;
  deleteWorkflow: (id: string) => void;
  duplicateWorkflow: (id: string) => string | null;
  runWorkflow: (id: string) => { runId: string; approvalsCreated: number } | null;
  addRun: (run: WorkflowRun) => void;
}

export const useWorkflowStore = create<WorkflowState>()(
  persist(
    (set, get) => ({
      workflows: seedWorkflows(),
      runs: [],

      createWorkflow: (w) => {
        const id = uid("wf");
        const now = nowIso();
        const wf: Workflow = {
          id,
          name: w.name,
          description: w.description ?? null,
          trigger: w.trigger,
          steps: w.steps.map((s) => ({ ...s, id: s.id || uid("step") })),
          created_at: now,
          updated_at: now,
        };
        set((s) => ({ workflows: [wf, ...s.workflows] }));
        return id;
      },

      updateWorkflow: (id, patch) =>
        set((s) => ({
          workflows: s.workflows.map((w) =>
            w.id === id ? { ...w, ...patch, updated_at: nowIso(), steps: patch.steps ?? w.steps } : w
          ),
        })),

      deleteWorkflow: (id) =>
        set((s) => ({
          workflows: s.workflows.filter((w) => w.id !== id),
        })),

      duplicateWorkflow: (id) => {
        const w = get().workflows.find((x) => x.id === id);
        if (!w) return null;
        const newId = uid("wf");
        const now = nowIso();
        const copy: Workflow = {
          ...w,
          id: newId,
          name: `${w.name} (copy)`,
          steps: w.steps.map((s) => ({ ...s, id: uid("step") })),
          created_at: now,
          updated_at: now,
        };
        set((s) => ({ workflows: [copy, ...s.workflows] }));
        return newId;
      },

      runWorkflow: (id) => {
        const wf = get().workflows.find((w) => w.id === id);
        if (!wf) return null;
        const runId = uid("run");
        const now = Date.now();
        const approvals: HitlRequest[] = [];
        let approvalsCreated = 0;

        wf.steps.forEach((step, idx) => {
          if (!step.requiresApproval) return;
          const req: HitlRequest = {
            id: `req_${Math.random().toString(36).slice(2, 8)}`,
            status: "pending",
            created_at: new Date(now + idx * 1000).toISOString(),
            expires_at: new Date(now + 60 * 60 * 1000 + idx * 1000).toISOString(),
            agent_id: `workflow:${wf.id}`,
            goal_id: null,
            goal_label: wf.name,
            trigger: { kind: "workflow", id: wf.id, label: `${wf.name} · step ${idx + 1}/${wf.steps.length}` },
            action: {
              kind: step.kind,
              summary: step.summary,
              target: step.target ?? null,
              preview: step.preview ?? null,
              args: step.args ?? null,
            },
            policy_version: "default@v12",
            risk_notes: [`From workflow "${wf.name}" step ${idx + 1}: ${step.summary}`],
          };
          approvals.push(req);
          approvalsCreated++;
        });

        if (approvals.length > 0) {
          // push to approval queue — newest first
          useApprovalStore.getState().addRequests(approvals);
        }

        const run: WorkflowRun = {
          id: runId,
          workflowId: wf.id,
          workflowName: wf.name,
          status: approvalsCreated > 0 ? "running" : "completed",
          created_at: new Date(now).toISOString(),
          stepCount: wf.steps.length,
          approvalsCreated,
        };
        set((s) => ({ runs: [run, ...s.runs].slice(0, 50) }));
        return { runId, approvalsCreated };
      },

      addRun: (run) => set((s) => ({ runs: [run, ...s.runs].slice(0, 50) })),
    }),
    {
      name: "xnch-workflows",
      partialize: (s) => ({ workflows: s.workflows, runs: s.runs }),
    }
  )
);
