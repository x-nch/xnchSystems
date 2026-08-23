import Link from "next/link";

const LINKS = [
  { href: "/product", label: "Product" },
  { href: "/services", label: "Services" },
  { href: "/teaching", label: "Teaching" },
  { href: "/community", label: "Community" },
];

export function MktNav() {
  return (
    <header className="border-b border-white/10">
      <nav
        aria-label="Marketing"
        className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6"
      >
        <Link
          href="/product"
          className="mkt-display text-sm font-bold tracking-wide"
        >
          xnch<span className="text-[#C8FF00]">Systems</span>
        </Link>
        <ul className="flex items-center gap-6">
          {LINKS.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                className="mkt-mono text-[11px] text-[#8B96AD] mkt-navlink"
              >
                {l.label}
              </Link>
            </li>
          ))}
          <li>
            <Link
              href="/"
              className="mkt-mono border border-[#C8FF00]/40 px-3 py-1.5 text-[11px] text-[#C8FF00]"
            >
              Console →
            </Link>
          </li>
        </ul>
      </nav>
    </header>
  );
}
