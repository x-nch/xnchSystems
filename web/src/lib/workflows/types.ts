import type { HitlActionKind } from "@/lib/approvals/types";

export type WorkflowTriggerKind = "manual" | "schedule";
export type WorkflowTrigger = {
  kind: WorkflowTriggerKind;
  cron?: string; // e.g. "0 9 * * 1" for schedule
  label?: string;
};

export type WorkflowStep = {
  id: string;
  kind: HitlActionKind;
  summary: string;
  target?: string | null;
  args?: unknown;
  preview?: string | null;
  requiresApproval: boolean;
  description?: string | null;
};

export type Workflow = {
  id: string;
  name: string;
  description?: string | null;
  trigger: WorkflowTrigger;
  steps: WorkflowStep[];
  created_at: string;
  updated_at: string;
};

export type WorkflowRunStatus = "pending" | "running" | "completed" | "cancelled";

export type WorkflowRun = {
  id: string;
  workflowId: string;
  workflowName: string;
  status: WorkflowRunStatus;
  created_at: string;
  stepCount: number;
  approvalsCreated: number;
};
