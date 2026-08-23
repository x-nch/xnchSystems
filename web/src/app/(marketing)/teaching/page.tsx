import type { Metadata } from "next";
import { GlitchText } from "@/components/marketing/glitch-text";
import { MktCTA } from "@/components/marketing/mkt-cta";
import { NoiseLayer } from "@/components/marketing/noise-layer";

export const metadata: Metadata = {
  title: "Teaching",
  description:
    "Cohort-based courses on HITL systems design, agent operations and memory architecture — built on xnch + nexi.",
};

const MODULES = [
  {
    id: "MODULE 01",
    name: "HITL Systems Design",
    weeks: "3 weeks",
    body: "Approval queues that operators actually use: state indicators, escalation thresholds, and the ergonomics of trust.",
  },
  {
    id: "MODULE 02",
    name: "Policy-Gated Autonomy",
    weeks: "4 weeks",
    body: "Write policy filters as code. Tune option scoring against your own risk register and audit the decisions.",
  },
  {
    id: "MODULE 03",
    name: "Memory Architecture",
    weeks: "3 weeks",
    body: "Episodic, semantic and graph stores in one pipeline — consolidation, provenance, and revocation by design.",
  },
  {
    id: "MODULE 04",
    name: "Agent Ops SRE",
    weeks: "2 weeks",
    body: "Observability for decision pipelines: what to chart, what to alert on, and what belongs in a postmortem.",
  },
];

export default function TeachingPage() {
  return (
    <div>
      <section className="mkt-layered overflow-hidden border-b border-white/10">
        <NoiseLayer sweep />
        <div className="mx-auto max-w-5xl px-6 py-24">
          <p className="mkt-kicker mkt-mono">teaching / cohorts</p>
          <h1 className="mkt-display mt-4 max-w-3xl text-4xl font-bold leading-tight md:text-5xl">
            <GlitchText text="Learn to run agents responsibly." />
          </h1>
          <p className="mkt-muted mt-6 max-w-xl text-base leading-relaxed">
            Small cohorts, real infrastructure. Every exercise runs against a
            live xnch + nexi sandbox with its own approval queue.
          </p>
        </div>
      </section>

      <section className="mkt-layered border-b border-white/10 py-20">
        <NoiseLayer />
        <div className="mx-auto max-w-5xl px-6">
          <h2 className="mkt-display text-2xl font-bold md:text-3xl">
            <GlitchText text="Curriculum" />
          </h2>
          <div className="mt-10 grid gap-5 md:grid-cols-2">
            {MODULES.map((m) => (
              <article key={m.id} className="mkt-card p-6">
                <div className="flex items-baseline justify-between gap-4">
                  <span className="mkt-mono text-[11px] text-[#C8FF00]">
                    {m.id}
                  </span>
                  <span className="mkt-mono text-[11px] text-[#8B96AD]">
                    {m.weeks}
                  </span>
                </div>
                <h3 className="mkt-display mkt-chroma mt-3 text-lg font-bold">
                  {m.name}
                </h3>
                <p className="mkt-muted mt-2 text-sm leading-relaxed">
                  {m.body}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mkt-layered py-24 text-center">
        <NoiseLayer />
        <div className="mx-auto max-w-2xl px-6">
          <h2 className="mkt-display text-2xl font-bold md:text-3xl">
            Next cohort forms in the community.
          </h2>
          <p className="mkt-muted mx-auto mt-3 max-w-md text-base">
            Seats are announced to community members first, always.
          </p>
          <div className="mt-8 flex justify-center gap-4">
            <MktCTA href="/community">Join the waitlist</MktCTA>
            <MktCTA href="/product" variant="outline">
              What you&apos;ll build on
            </MktCTA>
          </div>
        </div>
      </section>
    </div>
  );
}
