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

/**
 * Optimistically stamp the decided status on a cached approval list.
 * Pure and exported for contract tests (no DOM dependency).
 */
export function optimisticDecision(
  list: ApprovalDTO[],
  id: string,
  decision: "approve" | "reject"
): ApprovalDTO[] {
  const next = decision === "approve" ? "APPROVED" : "REJECTED";
  return list.map((a) =>
    a.approval_id === id && a.status === "AWAITING_APPROVAL"
      ? { ...a, status: next }
      : a
  );
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
    onMutate: async ({ id, body: { decision } }) => {
      await qc.cancelQueries({ queryKey: [APPROVALS] });
      const snapshots = qc
        .getQueriesData<ApprovalDTO[]>({ queryKey: [APPROVALS] })
        .filter(([, data]) => data != null);
      for (const [key, data] of snapshots) {
        qc.setQueryData<ApprovalDTO[]>(key, optimisticDecision(data ?? [], id, decision));
      }
      return { snapshots };
    },
    onError: (_err, _vars, ctx) => {
      for (const [key, data] of ctx?.snapshots ?? []) {
        qc.setQueryData<ApprovalDTO[]>(key, data);
      }
    },
    onSuccess: (updated) => {
      qc.setQueriesData<ApprovalDTO[]>({ queryKey: [APPROVALS] }, (old) =>
        old
          ? old.map((a) => (a.approval_id === updated.approval_id ? updated : a))
          : old
      );
    },
    onSettled: () => qc.invalidateQueries({ queryKey: [APPROVALS] }),
  });
}

export type { ApprovalDTO };