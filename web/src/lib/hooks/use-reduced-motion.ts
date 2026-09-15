"use client";

import { useSyncExternalStore } from "react";

function subscribe(callback: () => void): () => void {
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

function getSnapshot(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function getServerSnapshot(): boolean {
  return false;
}

/**
 * True when the OS/assistant prefers reduced motion. SSR-safe: returns
 * `false` on the server and first hydration render, then reconciles to the
 * real media state. Mirrors the CSS `prefers-reduced-motion` rule set in
 * globals.css for animations CSS cannot reach (e.g. SMIL `<animateMotion>`).
 */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}