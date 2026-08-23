import type { Metadata } from "next";
import Link from "next/link";
import "@/styles/marketing.css";
import { MktNav } from "@/components/marketing/mkt-nav";

export const metadata: Metadata = {
  title: {
    default: "xnchSystems — sovereign infrastructure for agentic AI",
    template: "%s — xnchSystems",
  },
  description:
    "Control planes and execution engines for private AI operations: policy-gated autonomy, human-in-the-loop approvals, memory that learns.",
};

export default function MarketingLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="mkt-root flex min-h-dvh flex-col">
      <a
        href="#mkt-main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-[#C8FF00] focus:px-3 focus:py-2 focus:text-[#0C0F14]"
      >
        Skip to content
      </a>
      <MktNav />
      <main id="mkt-main" className="flex-1">
        {children}
      </main>
      <footer className="border-t border-white/10 py-8">
        <div className="mx-auto flex max-w-5xl flex-col gap-2 px-6">
          <p className="mkt-mono text-[11px] text-[#8B96AD]">
            xnchSystems — public site. The operator console lives at{" "}
            <Link href="/" className="mkt-navlink">
              /
            </Link>
            .
          </p>
          <p className="mkt-mono text-[11px] text-[#8B96AD]/70">
            Motion-sensitive? Every animated effect on this site has a static
            equivalent under your OS reduced-motion setting.
          </p>
        </div>
      </footer>
    </div>
  );
}
