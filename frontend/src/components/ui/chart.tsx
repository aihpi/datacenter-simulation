import * as React from "react";
import { ResponsiveContainer, Tooltip, Legend } from "recharts";
import { cn } from "@/lib/utils";

/** One series' presentation: a human label and a resolved color. */
export interface ChartSeriesConfig {
  label?: React.ReactNode;
  color?: string;
}
export type ChartConfig = Record<string, ChartSeriesConfig>;

interface ChartContextValue {
  config: ChartConfig;
}
const ChartContext = React.createContext<ChartContextValue | null>(null);

function useChart(): ChartContextValue {
  const ctx = React.useContext(ChartContext);
  if (!ctx) throw new Error("useChart must be used within a <ChartContainer>");
  return ctx;
}

/**
 * shadcn-style chart shell: a themed, responsive wrapper around a Recharts
 * chart. Each config key's color is exposed as a `--color-<key>` CSS variable
 * on the container, so children can reference `var(--color-<key>)`.
 */
export function ChartContainer({
  config,
  className,
  children,
  height = 320,
}: {
  config: ChartConfig;
  className?: string;
  children: React.ReactElement;
  height?: number;
}) {
  const styleVars = React.useMemo(() => {
    const vars: Record<string, string> = {};
    for (const [key, s] of Object.entries(config)) {
      if (s.color) vars[`--color-${key}`] = s.color;
    }
    return vars as React.CSSProperties;
  }, [config]);

  return (
    <ChartContext.Provider value={{ config }}>
      <div
        data-chart
        className={cn(
          "w-full text-xs [&_.recharts-cartesian-grid_line]:stroke-border/60 " +
            "[&_.recharts-cartesian-axis-tick_text]:fill-muted-foreground " +
            "[&_.recharts-cartesian-axis-line]:stroke-border " +
            "[&_.recharts-curve.recharts-tooltip-cursor]:stroke-border " +
            "[&_.recharts-rectangle.recharts-tooltip-cursor]:fill-muted/60",
          className
        )}
        style={{ ...styleVars, height }}
      >
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </ChartContext.Provider>
  );
}

export const ChartTooltip = Tooltip;
export const ChartLegend = Legend;

interface TooltipPayloadItem {
  name?: string;
  dataKey?: string | number;
  value?: number | string;
  color?: string;
  payload?: Record<string, unknown>;
}

export function ChartTooltipContent({
  active,
  payload,
  label,
  valueFormatter,
  labelFormatter,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string | number;
  valueFormatter?: (v: number) => string;
  labelFormatter?: (l: string | number) => string;
}) {
  const { config } = useChart();
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs shadow-md">
      {label !== undefined && (
        <div className="mb-1 font-medium text-popover-foreground">
          {labelFormatter ? labelFormatter(label) : label}
        </div>
      )}
      <div className="flex flex-col gap-0.5">
        {payload.map((item, i) => {
          const key = String(item.dataKey ?? item.name ?? i);
          const seriesLabel = config[key]?.label ?? item.name ?? key;
          const val =
            typeof item.value === "number" && valueFormatter
              ? valueFormatter(item.value)
              : item.value;
          return (
            <div key={key + i} className="flex items-center gap-2">
              <span
                className="inline-block h-2 w-2 shrink-0 rounded-[2px]"
                style={{ background: item.color }}
              />
              <span className="text-muted-foreground">{seriesLabel}</span>
              <span className="ml-auto font-medium text-popover-foreground tabular-nums">
                {val}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
