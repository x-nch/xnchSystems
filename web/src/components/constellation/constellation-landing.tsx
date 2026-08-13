"use client";

import { useState } from "react";
import Link from "next/link";
import { PanelLeft } from "lucide-react";
import { ConstellationStage } from "./constellation-stage";
import { DetailPanel } from "./detail-panel";
import { NarrativeSections } from "./narrative-sections";

export function ConstellationLanding() {
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className="constellation min-h-dvh bg-[#070806] font-[family-name:var(--font-inter)] text-[#eef2e2]">
      {/* Header */}
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-[rgba(200,255,0,0.1)] bg-[rgba(7,8,6,0.82)] px-6 backdrop-blur-md">
        <Link href="/constellation" className="flex items-baseline gap-2.5">
          <span className="font-[family-name:var(--font-space-grotesk)] text-sm font-bold tracking-[0.18em] text-[#c8ff00]">
            XNCH<span className="text-[#eef2e2]">SYSTEMS</span>
          </span>
          <span className="hidden text-[10px] uppercase tracking-[0.28em] text-[#6f7566] sm:inline">
            agent constellation
          </span>
        </Link>

        <Link
          href="/"
          className="const-link-ghost inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-[12px] font-medium"
        >
          <PanelLeft className="h-3.5 w-3.5" />
          control surface
        </Link>
      </header>

      {/* Interactive core + agents */}
      <section className="relative h-[72vh] min-h-[520px] overflow-hidden">
        <ConstellationStage
          selected={selected}
          onSelect={(id) => setSelected(id)}
          onClear={() => setSelected(null)}
        />

        {/* Prompt strip */}
        <div className="pointer-events-none absolute bottom-5 left-1/2 z-30 -translate-x-1/2">
          <p className="rounded-full border border-[rgba(200,255,0,0.14)] bg-[rgba(7,8,6,0.85)] px-4 py-1.5 text-center text-[11px] tracking-wide text-[#6f7566] backdrop-blur-sm">
            <span className="text-[#c8ff00]">Select a node</span> to inspect a subsystem —{" "}
            <span className="text-[#c8ff00]">or the core</span> for the system view.
            <span className="ml-2 hidden text-[#6f7566]/60 md:inline">
              ↵ arrow keys to move focus
            </span>
          </p>
        </div>

        <DetailPanel selected={selected} onClose={() => setSelected(null)} />
      </section>

      {/* Scroll-driven narrative */}
      <NarrativeSections />

      <footer className="border-t border-[rgba(200,255,0,0.08)]">
        <div className="mx-auto flex max-w-5xl flex-col items-start justify-between gap-3 px-6 py-10 sm:flex-row sm:items-center">
          <span className="text-[11px] tracking-wide text-[#6f7566]">
            xnchSystems — an orchestrator that asks before it acts.
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6f7566]/60">
            prototype · static topology
          </span>
        </div>
      </footer>
    </div>
  );
}
