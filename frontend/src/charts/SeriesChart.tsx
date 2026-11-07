import { dez } from "@/lib/utils";
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";

export interface SeriesSpec {
  key: string; // data field to plot
  label: string; // human label
  color: string; // resolved CSS color
}

interface SeriesChartProps {
  data: Record<string, unknown>[];
  xKey: string;
  series: SeriesSpec[];
  height?: number;
  /** How many x-axis ticks to show (points are downsampled to labels only). */
  xTickCount?: number;
  yFormatter?: (v: number) => string;
  xFormatter?: (v: string | number) => string;
}

function defaultNum(v: number): string {
  if (Number.isInteger(v)) return String(v);
  return dez(v, 1);
}

/** A themed multi-series line chart (shadcn ChartContainer + Recharts). */
export function SeriesChart({
  data,
  xKey,
  series,
  height = 240,
  xTickCount = 6,
  yFormatter = defaultNum,
  xFormatter,
}: SeriesChartProps) {
  const config: ChartConfig = Object.fromEntries(
    series.map((s) => [s.key, { label: s.label, color: s.color }])
  );

  // Show only ~xTickCount evenly spaced x labels to avoid a crowded axis.
  const step = Math.max(1, Math.ceil(data.length / xTickCount));
  const ticks = data
    .map((row) => row[xKey] as string | number)
    .filter((_, i) => i % step === 0);

  return (
    <ChartContainer config={config} height={height}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
        <CartesianGrid vertical={false} strokeDasharray="3 3" />
        <XAxis
          dataKey={xKey}
          ticks={ticks}
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          minTickGap={16}
          tickFormatter={
            xFormatter ? (v) => xFormatter(v as string | number) : undefined
          }
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          tickMargin={6}
          width={44}
          tickFormatter={(v) => yFormatter(v as number)}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              valueFormatter={yFormatter}
              labelFormatter={
                xFormatter
                  ? (l) => xFormatter(l as string | number)
                  : undefined
              }
            />
          }
        />
        {series.map((s) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            stroke={`var(--color-${s.key})`}
            strokeWidth={1.75}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ChartContainer>
  );
}
