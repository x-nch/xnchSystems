import * as React from "react";
import { cn } from "@/lib/utils/cn";

type Tone = "default" | "accent" | "success" | "warning" | "destructive" | "muted";

const toneClasses: Record<Tone, string> = {
  default: "bg-muted text-foreground border-border",
  accent: "bg-accent-subtle text-accent border-accent/30",
  success: "bg-success/10 text-success border-success/25",
  warning: "bg-warning/10 text-warning border-warning/25",
  destructive: "bg-destructive/10 text-destructive border-destructive/25",
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
