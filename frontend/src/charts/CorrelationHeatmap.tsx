import { dez } from "@/lib/utils";
import { columnShort, columnLabel } from "../lib/labels";

interface HeatmapProps {
  columns: string[];
  matrix: (number | null)[][];
  selectedX?: string;
  selectedY?: string;
  onSelect: (x: string, y: string) => void;
}

function cellColor(r: number | null): string {
  if (r === null) return "#151b22";
  const t = Math.min(1, Math.abs(r));
  const [cr, cg, cb] = r >= 0 ? [88, 166, 255] : [248, 81, 73];
  const [br, bg, bb] = [21, 27, 34];
  const mix = (c: number, base: number) => Math.round(base + (c - base) * t);
  return `rgb(${mix(cr, br)}, ${mix(cg, bg)}, ${mix(cb, bb)})`;
}

function textColor(r: number | null): string {
  return r !== null && Math.abs(r) > 0.55 ? "#0b0e12" : "#d7dde5";
}

function fmtR(r: number | null): string {
  if (r === null) return "–";
  return dez(r, 2);
}

export function CorrelationHeatmap({
  columns,
  matrix,
  selectedX,
  selectedY,
  onSelect,
}: HeatmapProps) {
  return (
    <div className="heatmap-wrap">
      <table className="heatmap" data-testid="heatmap">
        <thead>
          <tr>
            <th className="heatmap-corner" />
            {columns.map((c) => (
              <th
                key={c}
                className="heatmap-col-head"
                title={columnLabel(c)}
              >
                <span>{columnShort(c)}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {columns.map((rowName, i) => (
            <tr key={rowName}>
              <th className="heatmap-row-head" title={columnLabel(rowName)}>
                {columnShort(rowName)}
              </th>
              {columns.map((colName, j) => {
                const r = matrix[i]?.[j] ?? null;
                const isDiag = i === j;
                const isSel =
                  (rowName === selectedX && colName === selectedY) ||
                  (rowName === selectedY && colName === selectedX);
                return (
                  <td
                    key={colName}
                    className={`heatmap-cell${isDiag ? " is-diag" : ""}${
                      isSel ? " is-sel" : ""
                    }`}
                    style={
                      isDiag
                        ? undefined
                        : { background: cellColor(r), color: textColor(r) }
                    }
                    title={`${columnLabel(rowName)} × ${columnLabel(
                      colName
                    )}: r = ${fmtR(r)}`}
                    onClick={() => !isDiag && onSelect(rowName, colName)}
                    data-testid={`cell-${rowName}-${colName}`}
                  >
                    {isDiag ? "" : fmtR(r)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
