"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { workflowEndpoints } from "@/lib/api/workflows";
import type { ApprovalDTO } from "@/lib/api/workflows";

const APPROVALS = "approvals";
const DEFAULT_STATUS = "AWAITING_APPROVAL";

export function useServerApprovals(
  enabled: boolean,
  params?: { status?: string; producer_type?: string }
) {
  return useQuery({
    queryKey: [APPROVALS, params?.status ?? DEFAULT_STATUS, params?.producer_type ?? null],
    queryFn: () => workflowEndpoints.listApprovals(params ?? { status: DEFAULT_STATUS }),
    enabled,
    refetchInterval: enabled ? 10_000 : false,
    retry: 1,
  });
}

export function useApprovalDecision() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: { decision: "approve" | "reject"; note?: string };
    }) => workflowEndpoints.decideApproval(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: [APPROVALS] }),
  });
}

export type { ApprovalDTO };