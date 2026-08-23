// Agent dispatch endpoints (mirrors xnch/routes/agents.py).
import { apiRequest } from "@/lib/api/client";

export interface AgentRunDTO {
  id: string;
  status: "QUEUED" | "RUNNING" | "DONE" | "FAILED";
  prompt: string;
  workspace: string;
  runner_id: string | null;
  lease_expires_at: number | null;
  exit_code: number | null;
  output_path: string | null;
  error: string | null;
  created_at: number;
  updated_at: number;
}

export const agentsApi = {
  listRuns: (status?: string) =>
    apiRequest<AgentRunDTO[]>(
      `/agents/runs${status ? `?status=${encodeURIComponent(status)}` : ""}`
    ),
  dispatch: (prompt: string, workspace?: string) =>
    apiRequest<AgentRunDTO>("/agents/dispatch", {
      method: "POST",
      body: workspace?.trim() ? { prompt, workspace: workspace.trim() } : { prompt },
    }),
};
