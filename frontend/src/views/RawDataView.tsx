import { dez } from "@/lib/utils";
import { useState } from "react";
import type { RawDataResponse } from "../types";
import { RAW_DATASET_OPTIONS } from "../types";
import { SeriesChart } from "../charts/SeriesChart";
import { columnLabel } from "../lib/labels";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface RawDataViewProps {
  data: RawDataResponse | null;
  dataset: string;
  loading: boolean;
  error: string | null;
  onSelectDataset: (dataset: string) => void;
  onRetry: () => void;
}

const PALETTE = Array.from({ length: 8 }, (_, i) => `var(--color-chart-${i + 1})`);

const TABLE_ROWS = 100; // rows rendered in the table view

function fmt(v: number | null): string {
  if (v === null) return "–";
  if (Number.isInteger(v)) return String(v);
  return dez(v, 2);
}

function cellText(v: string | number | null): string {
  if (v === null) return "";
  return typeof v === "number" ? fmt(v) : v;
}

/** "2026-01-05 14:00" -> "05.01" for axis ticks; leaves other strings intact. */
function shortTime(v: string | number): string {
  const s = String(v);
  const m = s.match(/^\d{4}-(\d{2})-(\d{2})/);
  return m ? `${m[2]}.${m[1]}` : s;
}

export function RawDataView({
  data,
  dataset,
  loading,
  error,
  onSelectDataset,
  onRetry,
}: RawDataViewProps) {
  const [mode, setMode] = useState<"table" | "charts">("charts");

  const cols = data?.columns.map((c) => c.name) ?? [];
  const numericCols = data?.columns.filter((c) => c.dtype === "numeric") ?? [];
  const textCols = data?.columns.filter((c) => c.dtype === "text") ?? [];
  // x-axis: first text column (usually the timestamp), else the row index.
  const xKey = textCols[0]?.name ?? "__i";
  const chartRows =
    data?.rows.map((r, i) => ({ ...r, __i: i })) ?? [];

  return (
    <div className="raw-view" data-testid="raw-view">
      <section className="picker-intro">
        <h2 className="section-title">Rohdaten</h2>
        <p className="section-sub">
          Die Eingangsdaten unverändert ansehen: Spaltenprofil, dann als
          Tabelle oder als Zeitreihen-Diagramme, bevor irgendein Modell läuft.
        </p>
        <div className="raw-toolbar">
          <Label htmlFor="raw-dataset">Datensatz</Label>
          <Select value={dataset} onValueChange={onSelectDataset}>
            <SelectTrigger
              id="raw-dataset"
              className="w-[24rem]"
              data-testid="raw-dataset-select"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {RAW_DATASET_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Tabs
            value={mode}
            onValueChange={(value) => setMode(value as "table" | "charts")}
          >
            <TabsList aria-label="Ansicht">
              <TabsTrigger value="table" data-testid="raw-mode-table">
                Tabelle
              </TabsTrigger>
              <TabsTrigger value="charts" data-testid="raw-mode-charts">
                Diagramme
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </section>

      {loading && (
        <div className="state-msg" data-testid="raw-loading">
          Rohdaten werden geladen
        </div>
      )}

      {error && !loading && (
        <div className="state-msg state-error" data-testid="raw-error">
          Rohdaten konnten nicht geladen werden. {error}
          <button className="retry-btn" onClick={onRetry}>
            Erneut versuchen
          </button>
        </div>
      )}

      {data && !loading && !error && (
        <>
          <section className="raw-summary" data-testid="raw-summary">
            <span>
              <strong>{data.n_rows.toLocaleString("de-DE")}</strong> Zeilen
            </span>
            <span>
              <strong>{data.n_cols}</strong> Spalten
            </span>
            <span>
              geladen: <strong>{data.returned_rows}</strong> Zeilen
            </span>
          </section>

          {mode === "table" && (
            <section className="raw-table-wrap" data-testid="raw-table-wrap">
              <table className="raw-table">
                <thead>
                  <tr>
                    <th className="raw-th-idx">#</th>
                    {cols.map((c) => (
                      <th key={c}>{columnLabel(c)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.rows.slice(0, TABLE_ROWS).map((row, i) => (
                    <tr key={i}>
                      <td className="raw-td-idx">{i + 1}</td>
                      {cols.map((c) => (
                        <td key={c}>{cellText(row[c])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.returned_rows > TABLE_ROWS && (
                <div className="raw-table-note">
                  erste {TABLE_ROWS} von {data.returned_rows} geladenen Zeilen
                </div>
              )}
            </section>
          )}

          {mode === "charts" && (
            <section className="raw-charts" data-testid="raw-charts">
              {numericCols.map((c, i) => (
                <div
                  className="raw-chart-card"
                  key={c.name}
                  data-testid={`raw-chart-${c.name}`}
                >
                  <div className="raw-chart-title">{columnLabel(c.name)}</div>
                  <SeriesChart
                    data={chartRows}
                    xKey={xKey}
                    height={220}
                    xTickCount={12}
                    series={[
                      {
                        key: c.name,
                        label: columnLabel(c.name),
                        color: PALETTE[i % PALETTE.length],
                      },
                    ]}
                    xFormatter={xKey === "__i" ? undefined : shortTime}
                  />
                </div>
              ))}
            </section>
          )}
        </>
      )}
    </div>
  );
}
