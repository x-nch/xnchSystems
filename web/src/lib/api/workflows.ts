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

// Wire contract (xnch/routes/workflows.py, f991e5f). The backend approval
// store serializes: approval_id, status, producer_type, producer_id,
// risk_class, payload, created_at, decided_at, decided_by, note,
// idempotency_key. "pending" on the wire == "AWAITING_APPROVAL".
// producer_type is a free string (workflow_step, workstream_spawn, …);
// payload tolerates the LangGraph HITL interrupt shape
// ({type:"workstream_spawn", goal_text, actor}) plus legacy workflow fields.
export interface ApprovalDTO {
  approval_id: string;
  producer_type: "workflow_step" | "workstream_spawn" | (string & {});
  producer_id: string;
  status:
    | "AWAITING_APPROVAL"
    | "APPROVED"
    | "REJECTED"
    | "EXPIRED"
    | "CANCELLED"
    | (string & {});
  risk_class: "low" | "elevated" | (string & {});
  note: string | null;
  decided_by: string | null;
  decided_at: number | null;
  created_at: number;
  expires_at?: number | null;
  idempotency_key?: string | null;
  payload: {
    type?: string;
    run_id?: string;
    workflow_id?: string;
    workflow_name?: string;
    step_index?: number;
    kind?: WorkflowStepDef["kind"];
    summary?: string;
    target?: string | null;
    args?: unknown;
    preview?: string | null;
    goal_text?: string;
    actor?: string;
    [key: string]: unknown;
  };
}

export const workflowEndpoints = {
  listApprovals: (params?: {
    status?: string;
    producer_type?: string;
  }) =>
    apiRequest<ApprovalDTO[]>("/approvals", {
      query: params ?? { status: "AWAITING_APPROVAL" },
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
