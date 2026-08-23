// Adapters between server DTOs (xnch wire contract) and the local view models
// used by the approval queue / workflow screens. Pure functions.
import type { ApprovalDTO, WorkflowDTO } from "@/lib/api/workflows";
import type { HitlRequest } from "@/lib/approvals/types";
import type { Workflow, WorkflowStep, WorkflowTrigger } from "@/lib/workflows/types";

export function approvalDtoToHitl(dto: ApprovalDTO): HitlRequest {
  const p = dto.payload ?? {};
  const status: HitlRequest["status"] =
    dto.status === "AWAITING_APPROVAL"
      ? "pending"
      : dto.status === "APPROVED"
        ? "approved"
        : dto.status === "REJECTED"
          ? "rejected"
          : "expired";
  return {
    id: dto.id,
    status,
    created_at: new Date(dto.created_at * 1000).toISOString(),
    expires_at:
      dto.expires_at != null
        ? new Date(dto.expires_at * 1000).toISOString()
        : null,
    agent_id: p.workflow_id ? `workflow:${p.workflow_id}` : dto.producer_type,
    goal_id: p.run_id ?? null,
    goal_label: p.workflow_name ?? null,
    trigger: {
      kind: "workflow",
      id: p.workflow_id ?? dto.producer_id,
      label: p.workflow_name ? `${p.workflow_name} · step ${(p.step_index ?? 0) + 1}` : undefined,
    },
    action: {
      kind: p.kind ?? "other",
      summary: p.summary ?? "(no summary)",
      target: p.target ?? null,
      args: p.args ?? null,
      preview: p.preview ?? null,
    },
    policy_version: `risk:${dto.risk_class}`,
    risk_notes: [
      dto.risk_class === "elevated"
        ? "Elevated risk step (external side-effect or tool execution)."
        : "Standard risk.",
    ],
  };
}

export function hitlDecisionFromRow(
  _row: HitlRequest,
  decision: "approve" | "reject",
  note?: string
): { decision: "approve" | "reject"; note?: string } {
  return note ? { decision, note } : { decision };
}

const ACTION_KINDS = new Set([
  "write_file",
  "exec_tool",
  "send_email",
  "create_goal",
  "update_memory",
  "other",
] as const);

function toLocalStep(s: WorkflowDTO["steps"][number]): WorkflowStep {
  return {
    id: s.id,
    kind: ACTION_KINDS.has(s.kind) ? s.kind : "other",
    summary: s.summary,
    target: s.target ?? null,
    args: s.args ?? null,
    preview: s.preview ?? null,
    requiresApproval: s.requires_approval ?? true,
    description: s.description ?? null,
  };
}

function toLocalTrigger(t: WorkflowDTO["trigger"]): WorkflowTrigger {
  return t.kind === "schedule"
    ? { kind: "schedule", cron: t.cron ?? "0 9 * * 1", label: t.cron ?? undefined }
    : { kind: "manual", label: "Run manually" };
}

/** Server workflow DTO → local camelCase view model (workflows-view.tsx shape). */
export function workflowDtoToLocal(dto: WorkflowDTO) {
  return {
    id: dto.id,
    name: dto.name,
    description: dto.description ?? "",
    trigger: toLocalTrigger(dto.trigger),
    steps: (dto.steps ?? []).map(toLocalStep),
    created_at: new Date(dto.created_at * 1000).toISOString(),
    updated_at: new Date(dto.updated_at * 1000).toISOString(),
  } satisfies Workflow;
}
