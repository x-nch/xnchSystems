import { cn } from "@/lib/utils/cn";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "skeleton rounded-md bg-muted",
        className
      )}
    />
  );
}
