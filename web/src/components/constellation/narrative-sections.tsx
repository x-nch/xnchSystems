"use client";

import { useEffect, useRef, useState } from "react";
import { NARRATIVE } from "@/lib/constellation/data";
import { cn } from "@/lib/utils/cn";

function useInView<T extends HTMLElement>(threshold = 0.25) {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setInView(true);
          io.disconnect();
        }
      },
      { threshold }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [threshold]);

  return { ref, inView };
}

export function NarrativeSections() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-28">
      <div className="mb-16">
        <span className="text-[11px] font-medium uppercase tracking-[0.3em] text-[#6f7566]">
          why it&apos;s built this way
        </span>
        <h2 className="mt-3 font-[family-name:var(--font-space-grotesk)] text-3xl font-bold tracking-tight text-[#eef2e2] sm:text-4xl">
          A decision pipeline, <span className="text-[#c8ff00]">not a prompt.</span>
        </h2>
      </div>

      <div className="space-y-20">
        {NARRATIVE.map((section, i) => (
          <Section key={section.kicker} section={section} index={i} />
        ))}
      </div>
    </div>
  );
}

function Section({
  section,
  index,
}: {
  section: (typeof NARRATIVE)[number];
  index: number;
}) {
  const { ref, inView } = useInView<HTMLDivElement>(0.2);

  return (
    <div
      ref={ref}
      className={cn(
        "const-rise grid gap-6 sm:grid-cols-[auto_1fr_auto] sm:gap-10",
        !inView && "opacity-0"
      )}
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="pt-1 font-mono text-[11px] uppercase tracking-[0.24em] text-[#c8ff00]/70">
        {section.kicker}
      </div>

      <div className="max-w-2xl">
        <h3 className="font-[family-name:var(--font-space-grotesk)] text-xl font-semibold tracking-tight text-[#eef2e2] sm:text-2xl">
          {section.title}
        </h3>
        <p className="mt-3 text-[14px] leading-relaxed text-[#8d9483]">{section.body}</p>
      </div>

      {section.stat && (
        <div
          className={cn(
            "flex h-fit items-center gap-2 rounded-full border px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] sm:self-center",
            section.emphasis
              ? "border-[rgba(200,255,0,0.45)] bg-[rgba(200,255,0,0.08)] text-[#c8ff00]"
              : "border-[rgba(200,255,0,0.16)] text-[#6f7566]"
          )}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", section.emphasis && "const-gate-beacon bg-[#c8ff00]")} />
          {section.stat}
        </div>
      )}
    </div>
  );
}
