// Approval endpoints (P2/P4 contract, mirrors xnch/routes/approvals.py).
// Workflow CRUD endpoints were removed — the backend retired the workflow
// store (f991e5f); the canvas editor is local-only. Types below document the
// legacy P4 DTO shape for adapters+tests until a real workflow endpoint returns.
import { apiRequest } from "@/lib/api/client";

export interface WorkflowTrigger {
  kind: "manual" | "schedule";
  cron?: string | null;
}

export interface WorkflowStepDef {
  id: string;
  kind:
    | "write_file"
    | "exec_tool"
    | "send_email"
    | "create_goal"
    | "update_memory"
    | "other";
  summary: string;
  target?: string | null;
  args?: unknown;
  preview?: string | null;
  requires_approval?: boolean;
  description?: string | null;
  model_provider?: string | null;
  model_id?: string | null;
}

export interface WorkflowDTO {
  id: string;
  owner_actor_id: string;
  name: string;
  description: string | null;
  trigger: WorkflowTrigger;
  steps: WorkflowStepDef[];
  created_at: number;
  updated_at: number;
}

export interface RunStepDTO {
  step_uuid: string;
  index: number;
  kind: WorkflowStepDef["kind"];
  summary: string;
  status:
    | "PENDING"
    | "AWAITING_APPROVAL"
    | "APPROVED"
    | "CLAIMED"
    | "EXECUTING"
    | "RETRYING"
    | "DONE"
    | "REJECTED"
    | "EXPIRED"
    | "CANCELLED"
    | "FAILED";
  approval_id: string | null;
  payload?: {
    target?: string | null;
    args?: unknown;
    preview?: string | null;
    model_provider?: string | null;
    model_id?: string | null;
  };
}

export interface WorkflowRunDTO {
  id: string;
  workflow_id: string;
  status: "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED";
  trigger: WorkflowTrigger;
  steps: RunStepDTO[];
  created_at: number;
}

export interface ApprovalDTO {
  id: string;
  producer_type: "chat" | "tool_call" | "goal_step" | "workflow_step";
  producer_id: string;
  status:
    | "AWAITING_APPROVAL"
    | "APPROVED"
    | "REJECTED"
    | "EXPIRED"
    | "CANCELLED";
  risk_class: "low" | "elevated";
  decision_note: string | null;
  decided_by: string | null;
  decided_at: number | null;
  expires_at: number | null;
  created_at: number;
  payload: {
    run_id?: string;
    workflow_id?: string;
    workflow_name?: string;
    step_index?: number;
    kind?: WorkflowStepDef["kind"];
    summary?: string;
    target?: string | null;
    args?: unknown;
    preview?: string | null;
  };
}

export const workflowEndpoints = {
  listApprovals: (params?: {
    status?: string;
    producer_type?: string;
  }) =>
    apiRequest<ApprovalDTO[]>("/approvals", {
      query: params ?? { status: "pending" },
    }),
  decideApproval: (
    id: string,
    body: { decision: "approve" | "reject"; note?: string }
  ) =>
    apiRequest<ApprovalDTO>(`/approvals/${id}/decide`, {
      method: "POST",
      body,
      headers: {
        "Idempotency-Key": crypto.randomUUID(),
        // muse is the operator console; xnch requires this role on
        // elevated-risk approvals (2026-08-24 audit P1).
        "X-Actor-Role": "admin",
      },
    }),
};
