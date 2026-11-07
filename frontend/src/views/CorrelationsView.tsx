import { dez } from "@/lib/utils";
import { useCallback, useEffect, useState } from "react";
import type { CorrelationMatrix, CorrMethod, PairData } from "../types";
import { fetchCorrelations, fetchPair } from "../lib/api";
import { columnLabel } from "../lib/labels";
import { CorrelationHeatmap } from "../charts/CorrelationHeatmap";
import { ScatterPlot } from "../charts/ScatterPlot";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const DATASET = "rechenzentrum_full.csv";
const PALETTE = ["var(--color-chart-1)", "var(--color-chart-2)"];
// Radix Select reserves the empty string, so "no control variable" needs a
// sentinel value of its own.
const NO_Z = "__keine__";

function fmt(v: number | null): string {
  return v === null ? "–" : dez(v, 2);
}

/** Plain-language read on whether controlling for Z explains the X-Y link. */
function collapseVerdict(r: number | null, partial: number | null): string {
  if (r === null || partial === null) return "";
  const a = Math.abs(r);
  const b = Math.abs(partial);
  if (a < 0.2) return "Zwischen X und Y besteht kaum ein Zusammenhang.";
  if (b < 0.2 && a >= 0.4)
    return "Der Zusammenhang verschwindet, wenn die Störgröße konstant gehalten wird, er wird durch sie erklärt (Confounder / Scheinkorrelation).";
  if (b < a * 0.5)
    return "Der Zusammenhang wird deutlich schwächer, er ist teilweise durch die Störgröße erklärt.";
  return "Der Zusammenhang bleibt bestehen, er wird durch diese Störgröße nicht erklärt.";
}

export function CorrelationsView() {
  const [matrix, setMatrix] = useState<CorrelationMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [method, setMethod] = useState<CorrMethod>("pearson");

  const [sel, setSel] = useState<{ x: string; y: string } | null>(null);
  const [controlZ, setControlZ] = useState<string>("");
  const [pair, setPair] = useState<PairData | null>(null);
  const [pairLoading, setPairLoading] = useState(false);
  const [finding, setFinding] = useState(false);

  const loadMatrix = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setMatrix(await fetchCorrelations(DATASET));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMatrix();
  }, [loadMatrix]);

  const loadPair = useCallback(async (x: string, y: string, z: string) => {
    setPairLoading(true);
    try {
      setPair(await fetchPair(x, y, z || undefined, DATASET));
    } catch {
      setPair(null);
    } finally {
      setPairLoading(false);
    }
  }, []);

  const selectPair = useCallback(
    (x: string, y: string) => {
      setSel({ x, y });
      setControlZ("");
      void loadPair(x, y, "");
    },
    [loadPair]
  );

  const changeZ = useCallback(
    (z: string) => {
      setControlZ(z);
      if (sel) void loadPair(sel.x, sel.y, z);
    },
    [sel, loadPair]
  );

  // Auto-finder: test every other column as Z, keep the one that shrinks |partial| most.
  const findConfounder = useCallback(async () => {
    if (!sel || !matrix) return;
    setFinding(true);
    try {
      const candidates = matrix.columns.filter(
        (c) => c !== sel.x && c !== sel.y
      );
      const results = await Promise.all(
        candidates.map((z) => fetchPair(sel.x, sel.y, z, DATASET))
      );
      let best: PairData | null = null;
      for (const res of results) {
        if (res.partial_r === null) continue;
        if (best === null || Math.abs(res.partial_r) < Math.abs(best.partial_r!))
          best = res;
      }
      if (best && best.z) {
        setControlZ(best.z);
        setPair(best);
      }
    } finally {
      setFinding(false);
    }
  }, [sel, matrix]);

  if (loading)
    return (
      <div className="state-msg" data-testid="corr-loading">
        Korrelationen werden berechnet
      </div>
    );
  if (error)
    return (
      <div className="state-msg state-error" data-testid="corr-error">
        Korrelationen konnten nicht geladen werden. {error}
        <button className="retry-btn" onClick={() => void loadMatrix()}>
          Erneut versuchen
        </button>
      </div>
    );
  if (!matrix) return null;

  const grid = method === "pearson" ? matrix.pearson : matrix.spearman;
  const zOptions = matrix.columns.filter(
    (c) => !sel || (c !== sel.x && c !== sel.y)
  );

  return (
    <div className="corr-view" data-testid="corr-view">
      <section className="picker-intro">
        <h2 className="section-title">Zusammenhänge</h2>
        <p className="section-sub">
          Alle Variablenpaare auf einen Blick. Zelle anklicken, um ein Paar zu
          untersuchen, und eine Störgröße konstant zu halten, um echte von
          scheinbaren Zusammenhängen zu trennen. n = {matrix.n}.
        </p>
        <div className="raw-toolbar">
          <Label>Maß</Label>
          <Tabs
            value={method}
            onValueChange={(value) => setMethod(value as CorrMethod)}
          >
            <TabsList aria-label="Korrelationsmaß">
              <TabsTrigger value="pearson" data-testid="method-pearson">
                Pearson (linear)
              </TabsTrigger>
              <TabsTrigger value="spearman" data-testid="method-spearman">
                Spearman (monoton)
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </section>

      <div className="corr-legend" aria-hidden="true">
        <span className="corr-legend-neg" /> −1
        <span className="corr-legend-grad" />
        +1 <span className="corr-legend-pos" />
        <span className="corr-legend-note">
          Blau: gleichläufig, Rot: gegenläufig, Helligkeit: Stärke
        </span>
      </div>

      <CorrelationHeatmap
        columns={matrix.columns}
        matrix={grid}
        selectedX={sel?.x}
        selectedY={sel?.y}
        onSelect={selectPair}
      />

      {!sel && (
        <p className="corr-hint">Eine Zelle anklicken, um das Paar zu öffnen.</p>
      )}

      {sel && (
        <section className="corr-pair" data-testid="corr-pair">
          <div className="corr-pair-head">
            <h3 className="section-title">
              {columnLabel(sel.x)} <span className="corr-x">×</span>{" "}
              {columnLabel(sel.y)}
            </h3>
            {pair && (
              <div className="corr-stats">
                <span className="corr-stat">
                  Pearson r <strong>{fmt(pair.r)}</strong>
                </span>
                <span className="corr-stat">
                  Spearman ρ <strong>{fmt(pair.rho)}</strong>
                </span>
              </div>
            )}
          </div>

          <div className="corr-panels">
            <div className="corr-panel">
              <div className="corr-panel-title">Streudiagramm</div>
              {pair && (
                <ScatterPlot
                  points={pair.points}
                  xLabel={columnLabel(sel.x)}
                  yLabel={columnLabel(sel.y)}
                  color={PALETTE[0]}
                />
              )}
            </div>

            <div className="corr-panel">
              <div className="corr-control">
                <Label htmlFor="corr-z">Konstant halten (Störgröße Z)</Label>
                <Select
                  value={controlZ || NO_Z}
                  onValueChange={(value) => changeZ(value === NO_Z ? "" : value)}
                >
                  <SelectTrigger
                    id="corr-z"
                    className="w-[20rem]"
                    data-testid="corr-z-select"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_Z}>keine</SelectItem>
                    {zOptions.map((c) => (
                      <SelectItem key={c} value={c}>
                        {columnLabel(c)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void findConfounder()}
                  disabled={finding}
                  data-testid="corr-find"
                >
                  {finding ? "sucht" : "Störgröße automatisch finden"}
                </Button>
              </div>

              {controlZ && pair && pair.partial_r !== null ? (
                <>
                  <div className="corr-panel-title">
                    Residuen: {columnLabel(sel.x)} und {columnLabel(sel.y)} nach
                    Herausrechnen von {columnLabel(controlZ)}
                  </div>
                  <ScatterPlot
                    points={pair.residual_points}
                    xLabel={`${columnLabel(sel.x)} (Rest)`}
                    yLabel={`${columnLabel(sel.y)} (Rest)`}
                    color={PALETTE[1]}
                  />
                  <div className="corr-collapse">
                    <span>
                      r {fmt(pair.r)} <span className="corr-arrow">→</span> partielles
                      r <strong>{fmt(pair.partial_r)}</strong> (Z ={" "}
                      {columnLabel(controlZ)})
                    </span>
                    <p className="corr-verdict">
                      {collapseVerdict(pair.r, pair.partial_r)}
                    </p>
                  </div>
                </>
              ) : (
                <p className="corr-hint">
                  Eine Störgröße wählen (oder automatisch finden), um zu sehen, ob
                  der Zusammenhang bestehen bleibt.
                </p>
              )}
            </div>
          </div>
          {pairLoading && <div className="corr-loading-note">lädt</div>}
        </section>
      )}
    </div>
  );
}
