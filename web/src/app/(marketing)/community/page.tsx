import type { Metadata } from "next";
import { GlitchText } from "@/components/marketing/glitch-text";
import { MktCTA } from "@/components/marketing/mkt-cta";
import { NoiseLayer } from "@/components/marketing/noise-layer";

export const metadata: Metadata = {
  title: "Community",
  description:
    "Open source control planes, public RFCs and weekly office hours for people building governed AI systems.",
};

const REPOS = [
  {
    name: "x-nch/xnch",
    body: "Control plane: REST routes, auth, memory, policy, learning.",
  },
  {
    name: "x-nch/nexi",
    body: "Execution engine: FastAPI decision/policy pipeline.",
  },
];

export default function CommunityPage() {
  return (
    <div>
      <section className="mkt-layered overflow-hidden border-b border-white/10">
        <NoiseLayer sweep />
        <div className="mx-auto max-w-5xl px-6 py-24">
          <p className="mkt-kicker mkt-mono">community / open source</p>
          <h1 className="mkt-display mt-4 max-w-3xl text-4xl font-bold leading-tight md:text-5xl">
            <GlitchText text="Built in the open." />
          </h1>
          <p className="mkt-muted mt-6 max-w-xl text-base leading-relaxed">
            Both core systems are open source. Roadmaps are RFCs, not
            press releases — argue with us before we build it.          </p>
        </div>
      </section>

      <section className="mkt-layered border-b border-white/10 py-20">
        <NoiseLayer />
        <div className="mx-auto grid max-w-5xl gap-10 px-6 md:grid-cols-2">
          <div>
            <h2 className="mkt-display text-2xl font-bold md:text-3xl">
              <GlitchText text="The repositories" />
            </h2>
            <ul className="mt-6 space-y-4">
              {REPOS.map((r) => (
                <li key={r.name} className="mkt-card p-5">
                  <a
                    href={`https://github.com/${r.name}`}
                    className="mkt-mono mkt-chroma text-sm font-semibold text-[#C8FF00]"
                  >
                    github.com/{r.name}
                  </a>
                  <p className="mkt-muted mt-2 text-sm">{r.body}</p>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h2 className="mkt-display text-2xl font-bold md:text-3xl">
              <GlitchText text="How to plug in" />
            </h2>
            <ol className="mkt-muted mt-6 space-y-4 text-sm leading-relaxed">
              <li>
                <span className="mkt-mono text-[11px] text-[#C8FF00]">
                  01&nbsp;&nbsp;
                </span>
                Clone, run the sandbox, break something small.
              </li>
              <li>
                <span className="mkt-mono text-[11px] text-[#C8FF00]">
                  02&nbsp;&nbsp;
                </span>
                Open an RFC with what surprised you &mdash; that&apos;s the currency.
              </li>
              <li>
                <span className="mkt-mono text-[11px] text-[#C8FF00]">
                  03&nbsp;&nbsp;
                </span>
                Weekly office hours: bring a workflow, leave with a policy.
              </li>
            </ol>
            <pre className="mkt-card mkt-mono mt-8 overflow-x-auto p-4 text-[12px] leading-relaxed text-[#8B96AD]">
              <code>{`$ git submodule update --init --recursive
$ pytest nexi/tests xnch/tests
$ # approval queue is already running at :3000`}</code>
            </pre>
          </div>
        </div>
      </section>

      <section className="mkt-layered py-24 text-center">
        <NoiseLayer />
        <div className="mx-auto max-w-2xl px-6">
          <h2 className="mkt-display text-2xl font-bold md:text-3xl">
            Governed AI needs skeptics.
          </h2>
          <p className="mkt-muted mx-auto mt-3 max-w-md text-base">
            The best feature requests start as objections. Bring yours.
          </p>
          <div className="mt-8 flex justify-center gap-4">
            <MktCTA href="/product">Start with the product</MktCTA>
            <MktCTA href="/teaching" variant="outline">
              Or go deep in teaching
            </MktCTA>
          </div>
        </div>
      </section>
    </div>
  );
}
