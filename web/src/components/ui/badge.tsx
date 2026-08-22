import * as React from "react";
import { cn } from "@/lib/utils/cn";

type Tone = "default" | "accent" | "success" | "warning" | "destructive" | "muted";

const toneClasses: Record<Tone, string> = {
  default: "bg-muted text-foreground border-border",
  accent: "bg-accent-subtle text-accent border-accent/30",
  success: "bg-emerald-500/10 text-emerald-400 border-emerald-500/25",
  warning: "bg-amber-500/10 text-amber-400 border-amber-500/25",
  destructive: "bg-red-500/10 text-red-400 border-red-500/25",
  muted: "bg-transparent text-muted-foreground border-border",
};

export function Badge({
  className,
  tone = "default",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-none",
        toneClasses[tone],
        className
      )}
      {...props}
    />
  );
}
