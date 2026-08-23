import { describe, expect, it } from "vitest";
import {
  approvalDtoToHitl,
  workflowDtoToLocal,
  hitlDecisionFromRow,
} from "./adapters";
import type { ApprovalDTO } from "../api/workflows";

const dto: ApprovalDTO = {
  id: "apr_1",
  producer_type: "workflow_step",
  producer_id: "step_uuid",
  status: "AWAITING_APPROVAL",
  risk_class: "elevated",
  decision_note: null,
  decided_by: null,
  decided_at: null,
  expires_at: Date.now() + 60_000,
  created_at: Date.now() - 120_000,
  payload: {
    run_id: "run_1",
    workflow_id: "wf_1",
    workflow_name: "Weekly Digest",
    step_index: 2,
    kind: "send_email",
    summary: "Send email to team@",
    target: "team@x",
    args: { to: "team@x" },
    preview: "Subject: hi",
  },
};

describe("approvalDtoToHitl", () => {
  it("maps server DTO into the queue row shape", () => {
    const hitl = approvalDtoToHitl(dto);
    expect(hitl.id).toBe("apr_1");
    expect(hitl.status).toBe("pending");
    expect(hitl.action.kind).toBe("send_email");
    expect(hitl.action.summary).toBe("Send email to team@");
    expect(hitl.agent_id).toBe("workflow:wf_1");
    expect(hitl.goal_label).toBe("Weekly Digest");
    expect(hitl.trigger?.kind).toBe("workflow");
    expect(hitl.risk_notes?.[0]).toMatch(/elevated/i);
  });

  it("preserves pending/expired status mapping", () => {
    expect(approvalDtoToHitl({ ...dto, status: "EXPIRED" }).status).toBe(
      "expired"
    );
    expect(approvalDtoToHitl({ ...dto, status: "REJECTED" }).status).toBe(
      "rejected"
    );
  });
});

describe("hitlDecisionFromRow", () => {
  it("round-trips an approve decision back to the server contract", () => {
    const body = hitlDecisionFromRow(approvalDtoToHitl(dto), "approve", "ok");
    expect(body.decision).toBe("approve");
    expect(body.note).toBe("ok");
  });
});

describe("workflowDtoToLocal", () => {
  it("maps snake_case DTO to the local camelCase workflow view model", () => {
    const local = workflowDtoToLocal({
      id: "wf_1",
      owner_actor_id: "operator",
      name: "Digest",
      description: "d",
      trigger: { kind: "schedule", cron: "0 9 * * 1" },
      steps: [
        {
          id: "s1",
          kind: "exec_tool",
          summary: "go",
          target: "web_search",
          requires_approval: true,
        },
      ],
      created_at: 1_700_000_000,
      updated_at: 1_700_000_100,
    });
    expect(local.id).toBe("wf_1");
    expect(local.trigger.kind).toBe("schedule");
    expect(local.steps[0].requiresApproval).toBe(true);
    expect(local.created_at).toBe(new Date(1_700_000_000 * 1000).toISOString());
  });
});
