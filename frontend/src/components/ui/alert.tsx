import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const alertVariants = cva(
  "relative flex w-full gap-3 rounded-md border px-4 py-3 text-sm",
  {
    variants: {
      variant: {
        default: "border-border bg-muted/60 text-foreground",
        info: "border-primary/25 bg-primary/5 text-foreground",
        destructive: "border-destructive/30 bg-destructive/5 text-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export function Alert({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof alertVariants>) {
  return (
    <div
      role="alert"
      className={cn(alertVariants({ variant }), className)}
      {...props}
    />
  );
}

export function AlertTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h4 className={cn("mb-0.5 font-semibold leading-tight", className)} {...props} />
  );
}

export function AlertDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <div
      className={cn("text-sm leading-relaxed text-muted-foreground", className)}
      {...props}
    />
  );
}
