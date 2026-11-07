import { dez } from "@/lib/utils";
import {
  CartesianGrid,
  ReferenceLine,
  Scatter,
  ScatterChart,
  XAxis,
  YAxis,
} from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import type { PairPoint } from "../types";

interface ScatterPlotProps {
  points: PairPoint[];
  xLabel: string;
  yLabel: string;
  color?: string;
  height?: number;
  showTrend?: boolean;
}

/** Least-squares line endpoints across the x-range, or null if degenerate. */
function trendSegment(points: PairPoint[]): [PairPoint, PairPoint] | null {
  const n = points.length;
  if (n < 2) return null;
  let sx = 0,
    sy = 0,
    sxx = 0,
    sxy = 0;
  for (const p of points) {
    sx += p.x;
    sy += p.y;
    sxx += p.x * p.x;
    sxy += p.x * p.y;
  }
  const denom = n * sxx - sx * sx;
  if (denom === 0) return null;
  const slope = (n * sxy - sx * sy) / denom;
  const intercept = (sy - slope * sx) / n;
  let xMin = points[0].x,
    xMax = points[0].x;
  for (const p of points) {
    if (p.x < xMin) xMin = p.x;
    if (p.x > xMax) xMax = p.x;
  }
  return [
    { x: xMin, y: slope * xMin + intercept },
    { x: xMax, y: slope * xMax + intercept },
  ];
}

const num = (v: number) =>
  Number.isInteger(v) ? String(v) : dez(v, 1);

/** Themed scatter plot (shadcn ChartContainer + Recharts) with a trend line. */
export function ScatterPlot({
  points,
  xLabel,
  yLabel,
  color = "var(--color-chart-1)",
  height = 300,
  showTrend = true,
}: ScatterPlotProps) {
  const config: ChartConfig = { y: { label: yLabel, color } };
  const seg = showTrend ? trendSegment(points) : null;

  return (
    <ChartContainer config={config} height={height}>
      <ScatterChart margin={{ top: 12, right: 16, bottom: 24, left: 18 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          type="number"
          dataKey="x"
          name={xLabel}
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          domain={["auto", "auto"]}
          tickFormatter={(v) => num(v as number)}
          label={{ value: xLabel, position: "insideBottom", offset: -14, fontSize: 12 }}
        />
        <YAxis
          type="number"
          dataKey="y"
          name={yLabel}
          tickLine={false}
          axisLine={false}
          tickMargin={6}
          width={64}
          domain={["auto", "auto"]}
          tickFormatter={(v) => num(v as number)}
          label={{
            value: yLabel,
            angle: -90,
            position: "insideLeft",
            offset: 0,
            fontSize: 12,
            style: { textAnchor: "middle", fill: "var(--ink-faint)" },
          }}
        />
        <ChartTooltip
          cursor={{ strokeDasharray: "3 3" }}
          content={<ChartTooltipContent valueFormatter={num} />}
        />
        {seg && (
          <ReferenceLine
            ifOverflow="extendDomain"
            segment={seg}
            stroke="var(--ink-soft)"
            strokeWidth={1.5}
            strokeDasharray="5 4"
          />
        )}
        <Scatter dataKey="y" data={points} fill={color} fillOpacity={0.45} />
      </ScatterChart>
    </ChartContainer>
  );
}
