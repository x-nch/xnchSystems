"use client";

import { useEffect, useRef } from "react";

const GLITCH_MS = 280;

/**
 * Brief glitch distortion for display headings ONLY.
 * Trigger rules (spec §4): pointer-enter only; ≤280ms; one shot per enter;
 * clip-path/transform only — zero brightness or inversion steps.
 * NEVER wrap nav links, CTAs, form labels, or body copy in this.
 *
 * Reduced motion: handlers become no-ops — the resting heading IS the
 * static equivalent.
 */
export function GlitchText({
  text,
  className = "",
}: {
  text: string;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const reducedRef = useRef(true);
  const timerRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => {
      reducedRef.current = mq.matches;
    };
    sync();
    mq.addEventListener("change", sync);
    return () => {
      mq.removeEventListener("change", sync);
      window.clearTimeout(timerRef.current);
    };
  }, []);

  const onPointerEnter = () => {
    const el = ref.current;
    if (!el || reducedRef.current) return;
    if (el.classList.contains("mkt-glitch--on")) return;
    el.classList.add("mkt-glitch--on");
    timerRef.current = window.setTimeout(
      () => el.classList.remove("mkt-glitch--on"),
      GLITCH_MS,
    );
  };

  return (
    <span
      ref={ref}
      onPointerEnter={onPointerEnter}
      data-text={text}
      className={`mkt-glitch ${className}`}
    >
      {text}
    </span>
  );
}
