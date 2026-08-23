export type HitlStatus = "pending" | "approved" | "rejected" | "expired";

export type HitlTrigger = {
  kind: "chat" | "scheduler" | "policy" | "goal" | "manual" | "workflow";
  id: string;
  label?: string;
};

export type HitlActionKind =
  | "write_file"
  | "exec_tool"
  | "send_email"
  | "create_goal"
  | "update_memory"
  | "other";

export interface HitlRequest {
  id: string;
  status: HitlStatus;
  created_at: string; // ISO
  expires_at: string | null;
  agent_id: string;
  goal_id: string | null;
  goal_label?: string | null;
  trigger: HitlTrigger | null;
  action: {
    kind: HitlActionKind;
    summary: string;
    preview?: string | null;
    args?: unknown;
    target?: string | null;
  };
  policy_version: string;
  risk_notes?: string[] | null;
}

export type Decision = "approve" | "reject";
