import type { PlotPoint } from "../types";

interface ScatterChartProps {
  points: PlotPoint[];
  xLabel: string;
  yLabel: string;
}

const WIDTH = 380;
const HEIGHT = 240;
const PAD_LEFT = 56;
const PAD_RIGHT = 16;
const PAD_TOP = 16;
const PAD_BOTTOM = 52;

const PLOT_W = WIDTH - PAD_LEFT - PAD_RIGHT;
const PLOT_H = HEIGHT - PAD_TOP - PAD_BOTTOM;

function niceRange(min: number, max: number): [number, number] {
  if (min === max) {
    // avoid zero-width domain
    const delta = Math.abs(min) > 0 ? Math.abs(min) * 0.1 : 1;
    return [min - delta, max + delta];
  }
  const pad = (max - min) * 0.06;
  return [min - pad, max + pad];
}

/** Evenly spaced "nice" tick values (1/2/5 * 10^k steps) inside [min, max]. */
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
    // guard against -0 and tiny float dust
    ticks.push(Math.abs(v) < step * 1e-9 ? 0 : v);
  }
  return ticks;
}

function fmt(v: number): string {
  const abs = Math.abs(v);
  if (abs !== 0 && (abs < 0.01 || abs >= 100000)) return v.toExponential(1);
  return Number.isInteger(v) ? String(v) : v.toFixed(2).replace(/\.?0+$/, "");
}

export function ScatterChart({ points, xLabel, yLabel }: ScatterChartProps) {
  if (!points || points.length === 0) {
    return (
      <div className="chart-empty" role="img" aria-label="Keine Streudiagramm-Daten">
        keine Daten
      </div>
    );
  }

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);

  const [xMin, xMax] = niceRange(Math.min(...xs), Math.max(...xs));
  const [yMin, yMax] = niceRange(Math.min(...ys), Math.max(...ys));

  const sx = (x: number) => PAD_LEFT + ((x - xMin) / (xMax - xMin)) * PLOT_W;
  const sy = (y: number) =>
    PAD_TOP + PLOT_H - ((y - yMin) / (yMax - yMin)) * PLOT_H;

  const xTicks = niceTicks(xMin, xMax).filter((t) => t >= xMin && t <= xMax);
  const yTicks = niceTicks(yMin, yMax).filter((t) => t >= yMin && t <= yMax);

  return (
    <svg
      className="mini-chart"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label={`Streudiagramm: ${xLabel} gegen ${yLabel}`}
      preserveAspectRatio="xMidYMid meet"
    >
      {/* gridlines + tick labels (drawn first so points sit on top) */}
      {yTicks.map((t, i) => {
        const y = sy(t);
        return (
          <g key={`y-${i}`}>
            <line
              x1={PAD_LEFT}
              y1={y}
              x2={PAD_LEFT + PLOT_W}
              y2={y}
              className="grid-line"
            />
            <text x={PAD_LEFT - 8} y={y + 3.5} className="tick-label tick-y">
              {fmt(t)}
            </text>
          </g>
        );
      })}
      {xTicks.map((t, i) => {
        const x = sx(t);
        return (
          <g key={`x-${i}`}>
            <line
              x1={x}
              y1={PAD_TOP}
              x2={x}
              y2={PAD_TOP + PLOT_H}
              className="grid-line"
            />
            <text
              x={x}
              y={PAD_TOP + PLOT_H + 16}
              className="tick-label tick-x"
            >
              {fmt(t)}
            </text>
          </g>
        );
      })}

      {/* axes */}
      <line
        x1={PAD_LEFT}
        y1={PAD_TOP}
        x2={PAD_LEFT}
        y2={PAD_TOP + PLOT_H}
        className="axis-line"
      />
      <line
        x1={PAD_LEFT}
        y1={PAD_TOP + PLOT_H}
        x2={PAD_LEFT + PLOT_W}
        y2={PAD_TOP + PLOT_H}
        className="axis-line"
      />

      {/* points */}
      {points.map((p, i) => (
        <circle
          key={i}
          cx={sx(p.x)}
          cy={sy(p.y)}
          r={3.6}
          className="scatter-dot"
        />
      ))}

      {/* axis titles */}
      <text x={PAD_LEFT + PLOT_W / 2} y={HEIGHT - 6} className="axis-label">
        {xLabel}
      </text>
      <text
        x={14}
        y={PAD_TOP + PLOT_H / 2}
        className="axis-label"
        transform={`rotate(-90 14 ${PAD_TOP + PLOT_H / 2})`}
      >
        {yLabel}
      </text>
    </svg>
  );
}
