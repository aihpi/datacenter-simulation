import { dez } from "@/lib/utils";
import type { ForecastPoint } from "../types";

interface LineChartProps {
  points: ForecastPoint[];
  yLabel: string;
}

const WIDTH = 760;
const HEIGHT = 300;
const PAD_LEFT = 60;
const PAD_RIGHT = 16;
const PAD_TOP = 16;
const PAD_BOTTOM = 52;

const PLOT_W = WIDTH - PAD_LEFT - PAD_RIGHT;
const PLOT_H = HEIGHT - PAD_TOP - PAD_BOTTOM;

function fmt(v: number): string {
  const abs = Math.abs(v);
  if (abs !== 0 && (abs < 0.01 || abs >= 100000)) return v.toExponential(1);
  return Number.isInteger(v) ? String(v) : dez(v, 1);
}

function niceTicks(min: number, max: number, target = 5): number[] {
  const span = max - min;
  if (!Number.isFinite(span) || span <= 0) return [min];
  const rawStep = span / target;
  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const norm = rawStep / mag;
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let v = start; v <= max + step * 1e-9; v += step) {
    ticks.push(Math.abs(v) < step * 1e-9 ? 0 : v);
  }
  return ticks;
}

/** Overlaid actual-vs-predicted line chart over the hold-out window. */
export function LineChart({ points, yLabel }: LineChartProps) {
  if (!points || points.length === 0) {
    return (
      <div className="chart-empty" role="img" aria-label="Keine Vorhersagedaten">
        keine Daten
      </div>
    );
  }

  const vals = points.flatMap((p) => [p.actual, p.predicted]);
  let yMin = Math.min(...vals);
  let yMax = Math.max(...vals);
  if (yMin === yMax) {
    yMin -= 1;
    yMax += 1;
  } else {
    const pad = (yMax - yMin) * 0.08;
    yMin -= pad;
    yMax += pad;
  }

  const n = points.length;
  const sx = (i: number) => PAD_LEFT + (n === 1 ? PLOT_W / 2 : (i / (n - 1)) * PLOT_W);
  const sy = (v: number) => PAD_TOP + PLOT_H - ((v - yMin) / (yMax - yMin)) * PLOT_H;

  const line = (key: "actual" | "predicted") =>
    points.map((p, i) => `${sx(i)},${sy(p[key])}`).join(" ");

  const yTicks = niceTicks(yMin, yMax).filter((t) => t >= yMin && t <= yMax);

  // Up to 5 x-axis labels drawn from the point timestamps (if present).
  const labelCount = Math.min(5, n);
  const xLabelIdx = Array.from({ length: labelCount }, (_, k) =>
    Math.round((k / Math.max(labelCount - 1, 1)) * (n - 1))
  );

  return (
    <svg
      className="line-chart"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label={`Ist gegen Vorhersage: ${yLabel}`}
      preserveAspectRatio="xMidYMid meet"
    >
      {yTicks.map((t, i) => {
        const y = sy(t);
        return (
          <g key={`y-${i}`}>
            <line x1={PAD_LEFT} y1={y} x2={PAD_LEFT + PLOT_W} y2={y} className="grid-line" />
            <text x={PAD_LEFT - 8} y={y + 3.5} className="tick-label tick-y">
              {fmt(t)}
            </text>
          </g>
        );
      })}

      <line x1={PAD_LEFT} y1={PAD_TOP} x2={PAD_LEFT} y2={PAD_TOP + PLOT_H} className="axis-line" />
      <line
        x1={PAD_LEFT}
        y1={PAD_TOP + PLOT_H}
        x2={PAD_LEFT + PLOT_W}
        y2={PAD_TOP + PLOT_H}
        className="axis-line"
      />

      {/* x tick labels (timestamps) */}
      {xLabelIdx.map((idx, i) => {
        const p = points[idx];
        const raw = p.label ?? String(p.index);
        const short = raw.length > 13 ? raw.slice(5) : raw; // drop the year
        return (
          <text key={`x-${i}`} x={sx(idx)} y={PAD_TOP + PLOT_H + 18} className="tick-label tick-x">
            {short}
          </text>
        );
      })}

      <polyline className="line-actual" points={line("actual")} fill="none" />
      <polyline className="line-predicted" points={line("predicted")} fill="none" />

      <text
        x={16}
        y={PAD_TOP + PLOT_H / 2}
        className="axis-label"
        transform={`rotate(-90 16 ${PAD_TOP + PLOT_H / 2})`}
      >
        {yLabel}
      </text>
    </svg>
  );
}
