import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/utils/cn";

type Variant = "default" | "secondary" | "ghost" | "outline" | "destructive";
type Size = "sm" | "md" | "icon" | "lg";

const variantClasses: Record<Variant, string> = {
  default:
    "bg-accent text-accent-foreground hover:bg-accent/90 shadow-sm shadow-accent/20",
  secondary: "bg-muted text-foreground hover:bg-muted/70",
  ghost: "text-muted-foreground hover:bg-muted hover:text-foreground",
  outline:
    "border border-border bg-transparent text-foreground hover:bg-muted",
  destructive:
    "bg-destructive text-destructive-foreground hover:bg-destructive/90",
};

const sizeClasses: Record<Size, string> = {
  sm: "h-7 px-2.5 text-xs gap-1.5 rounded-md",
  md: "h-8.5 px-3.5 text-sm gap-2 rounded-lg",
  lg: "h-10 px-4 text-sm gap-2 rounded-lg",
  icon: "h-8 w-8 rounded-lg",
};

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "md", asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center font-medium transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60",
          "disabled:pointer-events-none disabled:opacity-50 select-none whitespace-nowrap",
          variantClasses[variant],
          sizeClasses[size],
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
