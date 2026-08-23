import * as React from "react";
import { cn } from "@/lib/utils/cn";

type HudCardProps = React.HTMLAttributes<HTMLDivElement> & {
  glow?: "attention" | "none";
};

export function HudCard({ className, glow = "none", children, ...props }: HudCardProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border border-border bg-card motion-hover-lift",
        glow === "attention" && "border-[var(--state-attention)]",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function HudCardHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-col gap-0.5 border-b border-border px-4 py-3", className)}
      {...props}
    />
  );
}

export function HudCardTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn(
        "font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-foreground",
        className
      )}
      {...props}
    />
  );
}

export function HudCardDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn("text-[11px] text-muted-foreground", className)} {...props} />
  );
}

export function HudCardContent({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-4 py-3", className)} {...props} />;
}
