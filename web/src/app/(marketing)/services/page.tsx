import type { Metadata } from "next";
import { GlitchText } from "@/components/marketing/glitch-text";
import { MktCTA } from "@/components/marketing/mkt-cta";
import { NoiseLayer } from "@/components/marketing/noise-layer";

export const metadata: Metadata = {
  title: "Services",
  description:
    "Deployment, policy engineering and operations retainers for xnch + nexi control planes.",
};

const TIERS = [
  {
    name: "Deployment & Integration",
    lead: "Your cluster, our runway.",
    points: [
      "k3s / Docker / systemd install with your TLS and identity stack",
      "Gateway wiring between xnch, nexi and your models",
      "Backup, restore and upgrade runbooks handed over in writing",
    ],
  },
  {
    name: "Policy Engineering",
    lead: "Autonomy you can defend on paper.",
    points: [
      "Policy filters drafted from your risk register",
      "Approval thresholds tuned against real HITL queue data",
      "Audit trails mapped to your compliance reviewers",
    ],
  },
  {
    name: "Operations Retainer",
    lead: "We watch the graphs so you don't.",
    points: [
      "Monthly review of system health and inference performance",
      "Memory hygiene: pruning, consolidation, provenance checks",
      "Priority fixes and upgrade escorts for new releases",
    ],
  },
];

export default function ServicesPage() {
  return (
    <div>
      <section className="mkt-layered overflow-hidden border-b border-white/10">
        <NoiseLayer sweep />
        <div className="mx-auto max-w-5xl px-6 py-24">
          <p className="mkt-kicker mkt-mono">services</p>
          <h1 className="mkt-display mt-4 max-w-3xl text-4xl font-bold leading-tight md:text-5xl">
            <GlitchText text="We ship calm automation." />
          </h1>
          <p className="mkt-muted mt-6 max-w-xl text-base leading-relaxed">
            Three ways to put xnch + nexi to work — from a first deployment to
            an ongoing operations partnership.
          </p>
        </div>
      </section>

      <section className="mkt-layered border-b border-white/10 py-20">
        <NoiseLayer />
        <div className="mx-auto grid max-w-5xl gap-5 px-6 md:grid-cols-3">
          {TIERS.map((t) => (
            <article key={t.name} className="mkt-card flex flex-col p-6">
              <h2 className="mkt-display mkt-chroma text-lg font-bold">
                {t.name}
              </h2>
              <p className="mkt-mono mt-1 text-[11px] text-[#C8FF00]">
                {t.lead}
              </p>
              <ul className="mkt-muted mt-4 space-y-2 text-sm">
                {t.points.map((p) => (
                  <li key={p} className="leading-relaxed">
                    — {p}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>

      <section className="mkt-layered py-24 text-center">
        <NoiseLayer />
        <div className="mx-auto max-w-3xl px-6">
          <h2 className="mkt-display text-2xl font-bold md:text-3xl">
            Start with a conversation.
          </h2>
          <p className="mkt-muted mx-auto mt-3 max-w-lg text-base">
            Bring one workflow you don&apos;t trust yet. We&apos;ll show you how it looks
            behind a policy gate.
          </p>
          <div className="mt-8 flex justify-center gap-4">
            <MktCTA href="/community">Reach the team</MktCTA>
            <MktCTA href="/product" variant="outline">
              See the product
            </MktCTA>
          </div>
        </div>
      </section>
    </div>
  );
}
