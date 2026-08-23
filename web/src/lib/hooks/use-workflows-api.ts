"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { workflowEndpoints } from "@/lib/api/workflows";
import type { ApprovalDTO, WorkflowDTO } from "@/lib/api/workflows";

const WF = "workflows";
const APPROVALS = "approvals";
const RUNS = "workflow-runs";

/** Server workflows — only mounted when gateway is online (caller gates `enabled`). */
export function useServerWorkflows(enabled: boolean) {
  return useQuery({
    queryKey: [WF],
    queryFn: () => workflowEndpoints.listWorkflows(),
    enabled,
    refetchInterval: enabled ? 30_000 : false,
    retry: 1,
  });
}

export function useServerRuns(
  enabled: boolean,
  params?: { workflow_id?: string }
) {
  return useQuery({
    queryKey: [RUNS, params?.workflow_id ?? null],
    queryFn: () => workflowEndpoints.listRuns(params),
    enabled,
    refetchInterval: enabled ? 30_000 : false,
    retry: 1,
  });
}

export function useServerApprovals(
  enabled: boolean,
  params?: { status?: string; producer_type?: string }
) {
  return useQuery({
    queryKey: [APPROVALS, params?.status ?? "pending", params?.producer_type ?? null],
    queryFn: () => workflowEndpoints.listApprovals(params ?? { status: "pending" }),
    enabled,
    refetchInterval: enabled ? 10_000 : false,
    retry: 1,
  });
}

export function useWorkflowMutations() {
  const qc = useQueryClient();
  const invalidateAll = async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: [WF] }),
      qc.invalidateQueries({ queryKey: [APPROVALS] }),
      qc.invalidateQueries({ queryKey: [RUNS] }),
    ]);
  };

  const create = useMutation({
    mutationFn: (body: Parameters<typeof workflowEndpoints.createWorkflow>[0]) =>
      workflowEndpoints.createWorkflow(body),
    onSuccess: invalidateAll,
  });
  const update = useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: Parameters<typeof workflowEndpoints.updateWorkflow>[1];
    }) => workflowEndpoints.updateWorkflow(id, body),
    onSuccess: invalidateAll,
  });
  const remove = useMutation({
    mutationFn: (id: string) => workflowEndpoints.deleteWorkflow(id),
    onSuccess: invalidateAll,
  });
  const run = useMutation({
    mutationFn: (id: string) => workflowEndpoints.runWorkflow(id),
    onSuccess: invalidateAll,
  });
  const decide = useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: { decision: "approve" | "reject"; note?: string };
    }) => workflowEndpoints.decideApproval(id, body),
    onSuccess: invalidateAll,
  });

  return { create, update, remove, run, decide };
}

export type { ApprovalDTO, WorkflowDTO };
