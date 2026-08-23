"use client";

import { useEffect, useState } from "react";

const BASE_MS = 18;
const JITTER_MS = 10;
const START_DELAY_MS = 350;

/**
 * Terminal-style typing reveal for the hero subhead. The full sentence is
 * server-rendered AND mirrored in an sr-only node, so screen readers always
 * get the complete sentence regardless of animation state.
 *
 * Reduced motion / no JS: the full sentence renders statically with a
 * steady caret — the static equivalent is the default, not the fallback
 * path of an animation.
 */
export function TypeTerminal({
  text,
  className = "",
}: {
  text: string;
  className?: string;
}) {
  const [visible, setVisible] = useState(text);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let i = 0;
    let timer: number | undefined;
    let cancelled = false;

    const step = () => {
      i += 1;
      setVisible(text.slice(0, i));
      if (i < text.length) {
        timer = window.setTimeout(step, BASE_MS + Math.random() * JITTER_MS);
      }
    };
    // Reset + first character happen inside the timer, never synchronously
    // in the effect body, so the SSR sentence paints before typing begins.
    timer = window.setTimeout(() => {
      if (!cancelled) {
        setVisible("");
        step();
      }
    }, START_DELAY_MS);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [text]);

  return (
    <span className={className}>
      <span className="sr-only">{text}</span>
      <span aria-hidden="true">
        {visible}
        <span className="mkt-caret" />
      </span>
    </span>
  );
}
