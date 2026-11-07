import * as React from "react";
import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export function Select(props: React.ComponentProps<typeof SelectPrimitive.Root>) {
  return <SelectPrimitive.Root {...props} />;
}

export function SelectGroup(
  props: React.ComponentProps<typeof SelectPrimitive.Group>
) {
  return <SelectPrimitive.Group {...props} />;
}

export function SelectValue(
  props: React.ComponentProps<typeof SelectPrimitive.Value>
) {
  return <SelectPrimitive.Value {...props} />;
}

export function SelectTrigger({
  className,
  children,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Trigger>) {
  return (
    <SelectPrimitive.Trigger
      className={cn(
        "flex h-9 w-full items-center justify-between gap-2 rounded-md border border-input " +
          "bg-background px-3 py-2 text-sm text-foreground shadow-xs cursor-pointer " +
          "outline-none transition-colors hover:bg-accent/60 " +
          "focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-offset-1 " +
          "disabled:cursor-not-allowed disabled:opacity-50 " +
          "data-[placeholder]:text-muted-foreground [&>span]:truncate",
        className
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon asChild>
        <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}

export function SelectContent({
  className,
  children,
  position = "popper",
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        position={position}
        sideOffset={4}
        className={cn(
          "relative z-50 max-h-[--radix-select-content-available-height] min-w-[8rem] " +
            "overflow-y-auto overflow-x-hidden rounded-md border border-border " +
            "bg-popover p-1 text-popover-foreground shadow-lg " +
            "data-[side=bottom]:origin-top data-[side=top]:origin-bottom",
          position === "popper" && "w-[var(--radix-select-trigger-width)]",
          className
        )}
        {...props}
      >
        <SelectPrimitive.Viewport>{children}</SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  );
}

export function SelectLabel({
  className,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Label>) {
  return (
    <SelectPrimitive.Label
      className={cn(
        "px-2 py-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase",
        className
      )}
      {...props}
    />
  );
}

export function SelectItem({
  className,
  children,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Item>) {
  return (
    <SelectPrimitive.Item
      className={cn(
        "relative flex w-full cursor-pointer select-none items-center gap-2 rounded-sm " +
          "py-1.5 pr-8 pl-2 text-sm outline-none " +
          "data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground " +
          "data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        className
      )}
      {...props}
    >
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
      <span className="absolute right-2 flex h-3.5 w-3.5 items-center justify-center">
        <SelectPrimitive.ItemIndicator>
          <Check className="h-4 w-4 text-primary" />
        </SelectPrimitive.ItemIndicator>
      </span>
    </SelectPrimitive.Item>
  );
}

export function SelectSeparator({
  className,
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Separator>) {
  return (
    <SelectPrimitive.Separator
      className={cn("-mx-1 my-1 h-px bg-border", className)}
      {...props}
    />
  );
}
