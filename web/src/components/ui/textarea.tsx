import * as React from "react";
import { cn } from "@/lib/utils/cn";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full rounded-lg border border-border bg-input px-3 py-2 text-sm text-foreground",
      "placeholder:text-muted-foreground/70 transition-colors",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60",
      "disabled:cursor-not-allowed disabled:opacity-50 resize-none",
      className
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
