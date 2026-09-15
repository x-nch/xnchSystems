// Optimistic decision cache-stamping tests. The helper is pure/exported so it
// runs without a DOM; the mutation wiring (onMutate/onError/onSettled) is
// exercised implicitly by the queue's invalidation path.
import { describe, expect, it } from "vitest";
import { optimisticDecision } from "@/lib/hooks/use-workflows-api";
import type { ApprovalDTO } from "@/lib/api/workflows";

function approval(id: string, status: ApprovalDTO["status"]): ApprovalDTO {
  return {
    approval_id: id,
    producer_type: "workstream_spawn",
    producer_id: "test",
    status,
    risk_class: "low",
    note: null,
    decided_by: null,
    decided_at: null,
    created_at: 1_700_000_000,
    payload: { type: "workstream_spawn", goal_text: "draft q3", actor: "research" },
  };
}

describe("optimisticDecision", () => {
  it("stamps APPROVED on the matched pending approval", () => {
    const out = optimisticDecision(
      [approval("a1", "AWAITING_APPROVAL"), approval("a2", "AWAITING_APPROVAL")],
      "a1",
      "approve"
    );
    expect(out.map((a) => [a.approval_id, a.status])).toEqual([
      ["a1", "APPROVED"],
      ["a2", "AWAITING_APPROVAL"],
    ]);
  });

  it("stamps REJECTED on the matched pending approval", () => {
    const out = optimisticDecision([approval("a1", "AWAITING_APPROVAL")], "a1", "reject");
    expect(out[0].status).toBe("REJECTED");
  });

  it("never overwrites an already-decided row (server wins)", () => {
    const out = optimisticDecision([approval("a1", "APPROVED")], "a1", "reject");
    expect(out[0].status).toBe("APPROVED");
  });

  it("leaves the list untouched when the id is absent", () => {
    const src = [approval("a1", "AWAITING_APPROVAL")];
    const out = optimisticDecision(src, "nope", "approve");
    expect(out).toEqual(src);
  });

  it("returns a new array (immutable) while keeping unrelated rows by reference", () => {
    const a1 = approval("a1", "AWAITING_APPROVAL");
    const a2 = approval("a2", "AWAITING_APPROVAL");
    const out = optimisticDecision([a1, a2], "a1", "approve");
    expect(out).not.toBe([a1, a2]);
    expect(out[1]).toBe(a2);
    expect(out[0]).not.toBe(a1);
  });
});