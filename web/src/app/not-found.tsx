import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-5 bg-background px-6 text-center text-foreground">
      <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.3em] text-muted-foreground">
        error 404
      </p>
      <h1 className="font-display text-5xl font-bold tracking-tight md:text-6xl">
        Surface not found
      </h1>
      <p className="max-w-md text-sm leading-relaxed text-muted-foreground">
        The control surface you requested doesn&apos;t exist or was moved.
        Check the sidebar or head back to the dashboard.
      </p>
      <Button asChild>
        <Link href="/">Back to dashboard</Link>
      </Button>
    </main>
  );
}