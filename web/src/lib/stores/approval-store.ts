"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { HitlRequest } from "@/lib/approvals/types";

function nowIso(offsetMs = 0): string {
  return new Date(Date.now() + offsetMs).toISOString();
}

/** Seed data — visible when gateway has no real approvals yet. */
function seedApprovals(): HitlRequest[] {
  return [
    {
      id: "req_8f31a",
      status: "pending",
      created_at: nowIso(-12 * 60 * 1000),
      expires_at: nowIso(18 * 60 * 1000),
      agent_id: "research",
      goal_id: "goal_9c2d",
      goal_label: "Draft Q3 summary",
      trigger: { kind: "goal", id: "goal_9c2d", label: "goal_9c2d · Draft Q3 summary" },
      action: {
        kind: "write_file",
        summary: "Write file reports/q3.md",
        target: "reports/q3.md",
        preview:
          "# Q3 Summary — Draft\n\n- Revenue +12% QoQ\n- Churn 3.1% → 2.4%\n- Top issue: onboarding drop-off at step 3\n\n> Preview truncated — open detail for full diff ( +42 −3 ).",
        args: { path: "reports/q3.md", bytes: 4200 },
      },
      policy_version: "default@v12",
      risk_notes: ["Writes to git-tracked path.", "No secrets detected."],
    },
    {
      id: "req_7b02c",
      status: "pending",
      created_at: nowIso(-43 * 60 * 1000),
      expires_at: nowIso(47 * 60 * 1000),
      agent_id: "scheduler",
      goal_id: null,
      goal_label: null,
      trigger: { kind: "scheduler", id: "weekly_digest", label: "weekly_digest" },
      action: {
        kind: "send_email",
        summary: "Send email to team@",
        target: "team@xnch.local",
        preview:
          "Subject: Weekly digest — 2026-08-22\n\n3 highlights this week:\n1. 4 approvals pending\n2. Memory surface: 12 items\n3. Governance: policy v12 active",
        args: { to: "team@xnch.local" },
      },
      policy_version: "default@v12",
      risk_notes: ["External side-effect: email."],
    },
    {
      id: "req_3k9de",
      status: "pending",
      created_at: nowIso(-3 * 60 * 60 * 1000 - 12 * 60 * 1000),
      expires_at: nowIso(47 * 60 * 1000),
      agent_id: "code-actor",
      goal_id: "goal_a1f4",
      goal_label: "Refactor graph explorer",
      trigger: { kind: "policy", id: "policy:allow-with-approval", label: "policy gate" },
      action: {
        kind: "exec_tool",
        summary: "Execute tool: web_search — 'xnch competitor teardown'",
        target: "web_search",
        preview: 'args: {"query": "xnch competitor teardown", "limit": 5}',
        args: { tool: "web_search", query: "xnch competitor teardown" },
      },
      policy_version: "default@v12",
      risk_notes: ["Network egress."],
    },
    {
      id: "req_2x44f",
      status: "approved",
      created_at: nowIso(-5 * 60 * 60 * 1000),
      expires_at: null,
      agent_id: "research",
      goal_id: "goal_9c2d",
      goal_label: "Draft Q3 summary",
      trigger: { kind: "chat", id: "sess_abc", label: "chat session" },
      action: {
        kind: "update_memory",
        summary: "Remember: Q3 churn narrative",
        preview: "content: 'Churn improved due to onboarding fix — confirm in next retro.'",
        args: {},
      },
      policy_version: "default@v12",
      risk_notes: [],
    },
  ];
}

interface ApprovalState {
  items: HitlRequest[];
  lastDecision: { id: string; action: "approve" | "reject"; at: number; prev: HitlRequest } | null;
  decide: (id: string, action: "approve" | "reject", note?: string) => void;
  undoLast: () => void;
  dismissExpired: () => void;
  addRequests: (reqs: HitlRequest[]) => void;
  addRequest: (req: HitlRequest) => void;
}

export const useApprovalStore = create<ApprovalState>()(
  persist(
    (set) => ({
      items: seedApprovals(),
      lastDecision: null,
      decide: (id, action, note) =>
        set((s) => {
          const prev = s.items.find((i) => i.id === id);
          if (!prev || prev.status !== "pending") return s;
          const nextStatus = action === "approve" ? "approved" : "rejected";
          const updated: HitlRequest = {
            ...prev,
            status: nextStatus,
            // stash note as preview suffix if provided (minimal)
            risk_notes: note ? [...(prev.risk_notes ?? []), `Operator note: ${note}`] : prev.risk_notes,
          };
          return {
            items: s.items.map((i) => (i.id === id ? updated : i)),
            lastDecision: { id, action, at: Date.now(), prev },
          };
        }),
      undoLast: () =>
        set((s) => {
          const d = s.lastDecision;
          if (!d) return s;
          // only allow undo within 8s
          if (Date.now() - d.at > 8000) return { lastDecision: null };
          return {
            items: s.items.map((i) => (i.id === d.id ? d.prev : i)),
            lastDecision: null,
          };
        }),
      dismissExpired: () =>
        set((s) => ({
          items: s.items.map((i) => {
            if (i.status !== "pending" || !i.expires_at) return i;
            if (new Date(i.expires_at).getTime() < Date.now()) {
              return { ...i, status: "expired" as const };
            }
            return i;
          }),
        })),
      addRequests: (reqs) => set((s) => ({ items: [...reqs, ...s.items] })),
      addRequest: (req) => set((s) => ({ items: [req, ...s.items] })),
    }),
    {
      name: "xnch-approvals",
      partialize: (s) => ({ items: s.items }),
    }
  )
);

export function usePendingCount(): number {
  const items = useApprovalStore((s) => s.items);
  return items.filter((i) => i.status === "pending").length;
}
