import type { Metadata } from "next";
import { GlitchText } from "@/components/marketing/glitch-text";
import { MktCTA } from "@/components/marketing/mkt-cta";
import { NoiseLayer } from "@/components/marketing/noise-layer";
import { TypeTerminal } from "@/components/marketing/type-terminal";

export const metadata: Metadata = {
  title: "Product",
  description:
    "xnch decides, nexi executes, you approve what matters — a policy-gated control plane for private AI operations.",
};

const PIPELINE = [
  ["01", "Interpret", "Intent is parsed against session context."],
  ["02", "Load", "Episodic, semantic and graph memory hydrate the request."],
  ["03", "Generate", "Candidate options are produced by the planner."],
  ["04", "Filter", "Policy gates remove anything outside your rules."],
  ["05", "Evaluate", "Options are scored against risk and expected value."],
  ["06", "Decide", "The best safe option is selected — or escalated to you."],
  ["07", "Execute", "nexi compiles an action spec and runs it, audited."],
];

export default function ProductPage() {
  return (
    <div>
      <section className="mkt-layered overflow-hidden border-b border-white/10">
        <NoiseLayer sweep />
        <div className="mx-auto max-w-5xl px-6 py-24 md:py-32">
          <p className="mkt-kicker mkt-mono">xnchsystems / control planes</p>
          <h1 className="mkt-display mt-4 max-w-3xl text-4xl font-bold leading-tight md:text-6xl">
            <GlitchText text="Sovereign infrastructure" />
            <br />
            for agentic AI.
          </h1>
          <p className="mkt-mono mt-6 max-w-xl text-sm text-[#8B96AD]">
            <TypeTerminal text="> xnch decides. nexi executes. You approve what matters._" />
          </p>
          <div className="mt-10 flex flex-wrap gap-4">
            <MktCTA href="/services">Explore services</MktCTA>
            <MktCTA href="/community" variant="outline">
              Join the community
            </MktCTA>
          </div>
        </div>
      </section>

      <section className="mkt-layered border-b border-white/10 py-20">
        <NoiseLayer />
        <div className="mx-auto max-w-5xl px-6">
          <h2 className="mkt-display text-2xl font-bold md:text-3xl">
            <GlitchText text="One pipeline. Seven gates." />
          </h2>
          <p className="mkt-muted mt-3 max-w-2xl text-base">
            Every action passes the same auditable path — autonomy is a dial,
            not a leap of faith.
          </p>
          <ol className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {PIPELINE.map(([n, title, body]) => (
              <li key={n} className="mkt-card p-5">
                <span className="mkt-mono text-[11px] text-[#C8FF00]">{n}</span>
                <h3 className="mkt-display mt-2 font-semibold">{title}</h3>
                <p className="mkt-muted mt-1 text-sm">{body}</p>
              </li>
            ))}
            <li className="mkt-card flex items-center justify-center p-5">
              <MktCTA href="/teaching" variant="outline">
                Learn the pipeline
              </MktCTA>
            </li>
          </ol>
        </div>
      </section>

      <section className="mkt-layered border-b border-white/10 py-20">
        <NoiseLayer />
        <div className="mx-auto grid max-w-5xl gap-10 px-6 md:grid-cols-2">
          <div>
            <h2 className="mkt-display text-2xl font-bold md:text-3xl">
              <GlitchText text="Human-in-the-loop by design" />
            </h2>
            <p className="mkt-muted mt-4 text-base leading-relaxed">
              When risk crosses your policy threshold, the decision pauses and
              lands in an approval queue with full context: what was asked,
              which options existed, why this one won, what happens on
              approval. One keystroke to approve, reject, or edit the plan.
            </p>
          </div>
          <div>
            <h2 className="mkt-display text-2xl font-bold md:text-3xl">
              <GlitchText text="Memory that earns trust" />
            </h2>
            <p className="mkt-muted mt-4 text-base leading-relaxed">
              Episodic traces, semantic distillation and a relationship graph
              work together, so context improves with every approved run — and
              every stored memory can be inspected, cited and revoked.
            </p>
          </div>
        </div>
      </section>

      <section className="mkt-layered py-24">
        <NoiseLayer />
        <div className="mx-auto max-w-5xl px-6 text-center">
          <h2 className="mkt-display text-2xl font-bold md:text-3xl">
            Runs where you run it.
          </h2>
          <p className="mkt-muted mx-auto mt-3 max-w-xl text-base">
            k3s manifests, Docker images and systemd units ship in the box.
            Your data never leaves your infrastructure.
          </p>
          <div className="mt-8 flex justify-center gap-4">
            <MktCTA href="/services">Talk deployment</MktCTA>
          </div>
        </div>
      </section>
    </div>
  );
}
