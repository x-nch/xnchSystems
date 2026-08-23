import Link from "next/link";
import type { ReactNode } from "react";

type Variant = "solid" | "outline";

/**
 * Marketing CTA. Deliberately forked from operator ui/button.tsx so brand
 * effects can never leak into functional UI (and vice versa). CTAs carry
 * NO glitch/chroma/texture treatment by design — fully legible always.
 */
export function MktCTA({
  href,
  variant = "solid",
  children,
}: {
  href: string;
  variant?: Variant;
  children: ReactNode;
}) {
  const external = href.startsWith("http") || href.startsWith("mailto:");
  const cls = `mkt-cta mkt-cta--${variant} mkt-mono`;
  return external ? (
    <a href={href} className={cls}>
      {children}
    </a>
  ) : (
    <Link href={href} className={cls}>
      {children}
    </Link>
  );
}
