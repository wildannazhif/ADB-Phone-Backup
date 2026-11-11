import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const alertVariants = cva(
  "relative flex items-start gap-3 rounded-xl border p-3.5 text-xs",
  {
    variants: {
      variant: {
        default:
          "border-[var(--border-subtle)] bg-[var(--bg-card)] text-[var(--text-primary)]",
        info: "border-sky-500/30 bg-sky-500/8 text-sky-700 dark:text-sky-300",
        warning:
          "border-amber-500/35 bg-amber-500/10 text-amber-800 dark:text-amber-300",
        destructive:
          "border-rose-500/35 bg-rose-500/10 text-rose-800 dark:text-rose-300",
        success:
          "border-emerald-500/35 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface AlertProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {}

export function Alert({ className, variant, ...props }: AlertProps) {
  return <div role="alert" className={cn(alertVariants({ variant }), className)} {...props} />;
}
