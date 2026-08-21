"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { streamGraphEvents } from "@/lib/api/client";
import { useGraphStreamStore } from "@/lib/stores/graph-stream-store";
import type { GraphEntity, GraphRelation, GraphStats } from "@/lib/api/types";

const RECONNECT_MS = 3000;

export function useGraphStream(enabled: boolean) {
  const queryClient = useQueryClient();
  const connected = useGraphStreamStore((s) => s.connected);
  const [reconnecting, setReconnecting] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!enabled) {
      useGraphStreamStore.getState().setConnected(false);
      return;
    }

    let cancelled = false;
    const ac = new AbortController();

    const connect = () => {
      if (cancelled) return;
      setReconnecting(false);

      void streamGraphEvents({
        signal: ac.signal,
        onEvent: (event) => {
          const store = useGraphStreamStore.getState();
          switch (event.type) {
            case "stats": {
              const { type: _t, ...stats } = event as GraphStats & { type: "stats" };
              store.setStats(stats);
              queryClient.setQueryData(["graph-stats"], stats);
              break;
            }
            case "entity":
              store.upsertEntity(event.entity);
              break;
            case "relation":
              store.upsertRelation(event.relation);
              break;
            case "ready":
              store.setConnected(true);
              break;
            case "sync":
              void queryClient.invalidateQueries({ queryKey: ["graph-entities"] });
              void queryClient.invalidateQueries({ queryKey: ["graph-relations"] });
              store.clearLive();
              break;
            case "heartbeat":
              store.touch();
              break;
            case "error":
              store.setConnected(false);
              break;
            case "done":
              store.setConnected(false);
              break;
          }
        },
      }).then(() => {
        if (cancelled || ac.signal.aborted) return;
        useGraphStreamStore.getState().setConnected(false);
        setReconnecting(true);
        timerRef.current = setTimeout(connect, RECONNECT_MS);
      });
    };

    connect();

    return () => {
      cancelled = true;
      ac.abort();
      if (timerRef.current) clearTimeout(timerRef.current);
      useGraphStreamStore.getState().setConnected(false);
    };
  }, [enabled, queryClient]);

  return { connected, reconnecting };
}
