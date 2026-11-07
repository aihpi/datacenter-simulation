import { dez } from "@/lib/utils";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, XAxis, YAxis } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";

export interface BreakdownItem {
  name: string;
  value: number; // signed contribution in target units (kW)
}

function signed(v: number): string {
  return `${v >= 0 ? "+" : "−"}${dez(Math.abs(v), 1)}`;
}

const config: ChartConfig = { value: { label: "Beitrag (kW)" } };

/** Horizontal signed-contribution bars: Basis + each feature -> prediction.
 *  `rows` reserves height for that many bars (>= items.length), so re-fitting
 *  with fewer features keeps the chart box — and the page — the same size. */
export function PredictionBreakdown({
  items,
  rows,
}: {
  items: BreakdownItem[];
  rows?: number;
}) {
  const height = Math.max(rows ?? items.length, items.length) * 38 + 44;
  return (
    <ChartContainer config={config} height={height}>
      <BarChart
        layout="vertical"
        data={items}
        margin={{ top: 4, right: 40, bottom: 4, left: 8 }}
      >
        <CartesianGrid horizontal={false} strokeDasharray="3 3" />
        <XAxis
          type="number"
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => signed(v as number)}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={168}
          tickLine={false}
          axisLine={false}
        />
        <ReferenceLine x={0} stroke="var(--line-strong)" />
        <ChartTooltip
          cursor={{ fill: "rgba(125,136,150,0.12)" }}
          content={<ChartTooltipContent valueFormatter={(v) => `${signed(v)} kW`} />}
        />
        <Bar dataKey="value" radius={3} barSize={20} isAnimationActive={false}>
          {items.map((it, i) => (
            <Cell key={i} fill={it.value >= 0 ? "var(--pos)" : "var(--neg)"} />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  );
}
