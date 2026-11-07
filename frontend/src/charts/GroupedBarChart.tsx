import type { BarGroup } from "../types";

interface GroupedBarChartProps {
  bars: BarGroup[];
  xLabel: string;
  yLabel: string;
  valueLabel: string | null;
}

const WIDTH = 380;
const HEIGHT = 240;
const PAD_LEFT = 56;
const PAD_RIGHT = 16;
const PAD_TOP = 22;
const PAD_BOTTOM = 56;

const PLOT_W = WIDTH - PAD_LEFT - PAD_RIGHT;
const PLOT_H = HEIGHT - PAD_TOP - PAD_BOTTOM;

function fmt(v: number): string {
  const abs = Math.abs(v);
  if (abs !== 0 && (abs < 0.01 || abs >= 100000)) return v.toExponential(1);
  return Number.isInteger(v) ? String(v) : v.toFixed(2).replace(/\.?0+$/, "");
}

/** "Nice" tick values from 0 up to (and including) a rounded max. */
function niceTicksFromZero(max: number, target = 4): number[] {
  if (!Number.isFinite(max) || max <= 0) return [0, 1];
  const rawStep = max / target;
  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const norm = rawStep / mag;
  const step = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * mag;
  const top = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = 0; v <= top + step * 1e-9; v += step) ticks.push(v);
  return ticks;
}

/** Shorten long category labels so they don't overlap. */
function truncate(s: string, n = 10): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

export function GroupedBarChart({
  bars,
  xLabel,
  yLabel,
  valueLabel,
}: GroupedBarChartProps) {
  if (!bars || bars.length === 0) {
    return (
      <div className="chart-empty" role="img" aria-label="Keine Balkendaten">
        keine Daten
      </div>
    );
  }

  const values = bars.map((b) => b.value);
  const maxVal = Math.max(...values, 0);
  const ticks = niceTicksFromZero(maxVal);
  const domainMax = ticks[ticks.length - 1] || 1;

  const slot = PLOT_W / bars.length;
  const barW = Math.min(slot * 0.6, 64);

  const sy = (v: number) => PAD_TOP + PLOT_H - (v / domainMax) * PLOT_H;

  return (
    <svg
      className="mini-chart"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label={`Balkendiagramm: ${yLabel} nach ${xLabel}`}
      preserveAspectRatio="xMidYMid meet"
    >
      {/* y gridlines + ticks */}
      {ticks.map((t, i) => {
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

      {bars.map((b, i) => {
        const h = (b.value / domainMax) * PLOT_H;
        const cx = PAD_LEFT + slot * i + slot / 2;
        const x = cx - barW / 2;
        const y = PAD_TOP + PLOT_H - h;
        return (
          <g key={b.category}>
            <rect
              x={x}
              y={y}
              width={barW}
              height={Math.max(h, 0)}
              className="bar-rect"
              rx={3}
            />
            {/* value on top */}
            <text x={cx} y={y - 5} className="bar-value">
              {fmt(b.value)}
            </text>
            {/* category label */}
            <text x={cx} y={PAD_TOP + PLOT_H + 16} className="bar-category">
              <title>{b.category}</title>
              {truncate(b.category)}
            </text>
            {/* n label */}
            <text x={cx} y={PAD_TOP + PLOT_H + 29} className="bar-n">
              n={b.n}
            </text>
          </g>
        );
      })}

      {/* y-axis title: what the bars measure */}
      <text
        x={14}
        y={PAD_TOP + PLOT_H / 2}
        className="axis-label"
        transform={`rotate(-90 14 ${PAD_TOP + PLOT_H / 2})`}
      >
        {valueLabel ?? yLabel}
      </text>

      {/* x-axis title: the grouping variable */}
      <text x={PAD_LEFT + PLOT_W / 2} y={HEIGHT - 5} className="axis-label">
        {xLabel}
      </text>
    </svg>
  );
}
