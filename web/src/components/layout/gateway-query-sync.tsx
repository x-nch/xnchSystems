"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useHealth } from "@/lib/api/hooks";

/** Refetch subsystem data when the gateway comes back online. */
export function GatewayQuerySync() {
  const health = useHealth();
  const queryClient = useQueryClient();
  const wasOnline = useRef(false);

  useEffect(() => {
    const online = health.data?.status === "ok";
    if (online && !wasOnline.current) {
      void queryClient.invalidateQueries({
        predicate: (query) => query.queryKey[0] !== "health",
      });
    }
    wasOnline.current = online;
  }, [health.data?.status, queryClient]);

  return null;
}
