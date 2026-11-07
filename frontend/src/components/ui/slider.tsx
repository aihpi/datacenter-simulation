import * as React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";
import { cn } from "@/lib/utils";

export function Slider({
  className,
  ...props
}: React.ComponentProps<typeof SliderPrimitive.Root>) {
  return (
    <SliderPrimitive.Root
      className={cn(
        "relative flex w-full touch-none select-none items-center py-2 " +
          "data-[disabled]:opacity-50",
        className
      )}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-1.5 w-full grow overflow-hidden rounded-full bg-muted">
        <SliderPrimitive.Range className="absolute h-full bg-primary" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb
        className={cn(
          "block h-4 w-4 rounded-full border-2 border-primary bg-background shadow-sm " +
            "cursor-grab outline-none transition-shadow active:cursor-grabbing " +
            "focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-offset-1 " +
            "data-[disabled]:cursor-not-allowed"
        )}
      />
    </SliderPrimitive.Root>
  );
}
