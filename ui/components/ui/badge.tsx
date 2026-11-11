import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium transition-colors",
  {
    variants: {
      variant: {
        default:
          "border-sky-500/30 bg-sky-500/12 text-sky-600 dark:text-sky-400",
        secondary:
          "border-[var(--border-subtle)] bg-[var(--bg-elevated)] text-[var(--text-secondary)]",
        success:
          "border-emerald-500/30 bg-emerald-500/12 text-emerald-600 dark:text-emerald-400",
        warning:
          "border-amber-500/30 bg-amber-500/12 text-amber-600 dark:text-amber-400",
        destructive:
          "border-rose-500/30 bg-rose-500/12 text-rose-600 dark:text-rose-400",
        violet:
          "border-violet-500/30 bg-violet-500/12 text-violet-600 dark:text-violet-400",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
