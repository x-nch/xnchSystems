"use client";

import { useSyncExternalStore } from "react";

const emptySubscribe = () => () => {};

/**
 * True once rendered on the client. During SSR and the initial hydration
 * render it returns `false`, so store-derived markup (zustand `persist`
 * rehydrated from localStorage) never differs between server HTML and the
 * first client paint — which avoids React hydration mismatch warnings.
 */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false
  );
}
