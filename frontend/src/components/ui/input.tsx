import * as React from "react";
import { cn } from "@/lib/utils";

export function Input({
  className,
  type,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type={type}
      className={cn(
        "flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 " +
          "text-sm text-foreground shadow-xs outline-none transition-colors " +
          "placeholder:text-muted-foreground " +
          "focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-offset-1 " +
          "disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}
