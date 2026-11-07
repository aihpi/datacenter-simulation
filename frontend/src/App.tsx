import { useCallback, useEffect, useRef, useState } from "react";
import type {
  PredictResponse,
  RawDataResponse,
  SynthesizePreset,
  SynthesizeSpec,
} from "./types";
import { RAW_DEFAULT_DATASET } from "./types";
import {
  fetchRawData,
  fetchSynthesizePresets,
  rowsToCsv,
  runPredict,
  runSynthesize,
  uploadRows as uploadRowsApi,
} from "./lib/api";
import { ForecastView } from "./views/ForecastView";
import { RawDataView } from "./views/RawDataView";
import { CorrelationsView } from "./views/CorrelationsView";
import { FOERDERHINWEIS, IMPRESSUM_URL, LegalView, PROJEKTSEITE_URL } from "./views/LegalView";
import "./App.css";

type View = "forecast" | "raw" | "correlations" | "datenschutz";

type ForecastSource = "seed" | "specs" | "upload";

export default function App() {
  const [view, setView] = useState<View>("raw");

  // forecast (Scope B)
  const [forecast, setForecast] = useState<PredictResponse | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [forecastError, setForecastError] = useState<string | null>(null);
  const [minCorrelation, setMinCorrelation] = useState(0);
  const [manualFeatures, setManualFeatures] = useState<string[] | null>(null);
  // null = let the backend pick (the uploaded CSV may not have the default
  // target column); set once the user picks explicitly.
  const [target, setTarget] = useState<string | null>(null);
  const lastForecastParams = useRef<{
    minCorrelation: number;
    featureCols: string[] | null;
    rows: Record<string, unknown>[] | null;
    target: string | null;
  }>({ minCorrelation: 0, featureCols: null, rows: null, target: null });
  // Slider drags fire overlapping requests; only the newest one may write
  // state, otherwise a slow earlier fit lands on top of the current settings.
  const forecastSeq = useRef(0);
  const synthSeq = useRef(0);

  // forecast data source: the seeded CSV, a specs-synthesized series, or an
  // uploaded CSV
  const [forecastSource, setForecastSource] = useState<ForecastSource>(
    "seed"
  );
  const [uploadedRows, setUploadedRows] = useState<
    Record<string, unknown>[] | null
  >(null);
  const [uploadLabel, setUploadLabel] = useState<string | null>(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [synthSpec, setSynthSpec] = useState<SynthesizeSpec>({
    n_gpus: 50_000,
    gpu_type: "h100",
    workload: "training",
    model_class: "70b",
    arch: "dense",
    inference_phase: "decode",
    cooling: "warmwasser",
    pue: 1.3,
    climate: "gemaessigt",
    occupancy_pct: 100,
    chip_load_pct: 75,
    idle_w: 100,
    tdp_w: 700,
    moe_anteil_pct: 12.5,
    batch_size: 16,
    days: 14,
  });
  const [synthRows, setSynthRows] = useState<Record<string, unknown>[] | null>(
    null
  );
  const [synthLabel, setSynthLabel] = useState<string | null>(null);
  const [synthLoading, setSynthLoading] = useState(false);
  const [synthError, setSynthError] = useState<string | null>(null);
  const [presets, setPresets] = useState<SynthesizePreset[]>([]);
  const synthTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    void fetchSynthesizePresets().then(setPresets).catch(() => setPresets([]));
  }, []);

  // raw data inspector (Phase 1)
  const [rawData, setRawData] = useState<RawDataResponse | null>(null);
  const [rawDataset, setRawDataset] = useState(RAW_DEFAULT_DATASET);
  const [rawLoading, setRawLoading] = useState(false);
  const [rawError, setRawError] = useState<string | null>(null);

  const loadRaw = useCallback(async (dataset: string) => {
    setRawLoading(true);
    setRawError(null);
    try {
      setRawData(await fetchRawData(dataset));
    } catch (err) {
      setRawData(null);
      setRawError(err instanceof Error ? err.message : String(err));
    } finally {
      setRawLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRaw(rawDataset);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openRaw = useCallback(() => {
    setView("raw");
    void loadRaw(rawDataset);
  }, [loadRaw, rawDataset]);

  const selectRawDataset = useCallback(
    (dataset: string) => {
      setRawDataset(dataset);
      void loadRaw(dataset);
    },
    [loadRaw]
  );

  const loadForecast = useCallback(
    async (params: {
      minCorrelation: number;
      featureCols: string[] | null;
      rows: Record<string, unknown>[] | null;
      target: string | null;
    }) => {
      lastForecastParams.current = params;
      const seq = ++forecastSeq.current;
      setForecastLoading(true);
      setForecastError(null);
      try {
        const res = await runPredict({
          min_correlation: params.minCorrelation,
          feature_cols: params.featureCols ?? undefined,
          rows: params.rows ?? undefined,
          target: params.target ?? undefined,
        });
        if (seq !== forecastSeq.current) return;
        setForecast(res);
      } catch (err) {
        if (seq !== forecastSeq.current) return;
        setForecastError(err instanceof Error ? err.message : String(err));
      } finally {
        if (seq === forecastSeq.current) setForecastLoading(false);
      }
    },
    []
  );

  const rowsForSource = useCallback(
    (source: ForecastSource) => {
      if (source === "specs") return synthRows;
      if (source === "upload") return uploadedRows;
      return null;
    },
    [synthRows, uploadedRows]
  );

  const openForecast = useCallback(() => {
    setView("forecast");
    setMinCorrelation(0);
    setManualFeatures(null);
    const rows = rowsForSource(forecastSource);
    // Only the seed source can fit without rows of its own; an upload/specs
    // source without rows would silently fall back to the seed dataset.
    if (forecastSource !== "seed" && !rows) return;
    void loadForecast({
      minCorrelation: 0,
      featureCols: null,
      rows,
      target,
    });
  }, [loadForecast, forecastSource, rowsForSource, target]);

  // Threshold slider: auto-select features by correlation strength, clearing
  // any manual checkbox overrides.
  const changeMinCorrelation = useCallback(
    (value: number) => {
      setMinCorrelation(value);
      setManualFeatures(null);
      void loadForecast({
        minCorrelation: value,
        featureCols: null,
        rows: rowsForSource(forecastSource),
        target,
      });
    },
    [loadForecast, forecastSource, rowsForSource, target]
  );

  // Checkbox toggle: switches to a manual feature list, seeded from whatever
  // is currently included (auto-selected or previously toggled).
  const toggleForecastFeature = useCallback(
    (name: string) => {
      const base = manualFeatures ?? forecast?.features ?? [];
      const next = base.includes(name)
        ? base.filter((n) => n !== name)
        : [...base, name];
      // A regression needs at least one feature; unchecking the last one would
      // only yield a 400 from the backend.
      if (next.length === 0) return;
      setManualFeatures(next);
      void loadForecast({
        minCorrelation,
        featureCols: next,
        rows: rowsForSource(forecastSource),
        target,
      });
    },
    [
      loadForecast,
      manualFeatures,
      forecast,
      minCorrelation,
      forecastSource,
      rowsForSource,
      target,
    ]
  );

  // Target picker: refit on a different column, keeping the current data
  // source and letting the threshold re-select features for the new target.
  const changeTarget = useCallback(
    (name: string) => {
      setTarget(name);
      setManualFeatures(null);
      void loadForecast({
        minCorrelation,
        featureCols: null,
        rows: rowsForSource(forecastSource),
        target: name,
      });
    },
    [loadForecast, minCorrelation, forecastSource, rowsForSource]
  );

  // Fetch a synthesized series for the given spec (or preset) and re-fit the
  // live forecast on it — same debounced real-time loop as the threshold
  // slider, just fed by generated rows instead of an uploaded/seeded CSV.
  const runSynth = useCallback(
    async (spec: SynthesizeSpec | { preset: string }) => {
      const seq = ++synthSeq.current;
      setSynthLoading(true);
      setSynthError(null);
      try {
        const res = await runSynthesize(spec);
        if (seq !== synthSeq.current) return;
        setSynthRows(res.rows);
        setSynthLabel(res.label);
        setManualFeatures(null);
        // Keep an explicitly picked target if the generated series still has
        // that column, else let the backend pick (the facility-wide meter).
        const nextTarget =
          target && res.columns.includes(target) ? target : null;
        setTarget(nextTarget);
        await loadForecast({
          minCorrelation,
          featureCols: null,
          rows: res.rows,
          target: nextTarget,
        });
      } catch (err) {
        if (seq !== synthSeq.current) return;
        setSynthError(err instanceof Error ? err.message : String(err));
      } finally {
        if (seq === synthSeq.current) setSynthLoading(false);
      }
    },
    [loadForecast, minCorrelation, target]
  );

  const SYNTH_DEBOUNCE_MS = 400;
  const changeSynthSpec = useCallback(
    (next: SynthesizeSpec) => {
      setSynthSpec(next);
      if (synthTimer.current) clearTimeout(synthTimer.current);
      synthTimer.current = setTimeout(() => void runSynth(next), SYNTH_DEBOUNCE_MS);
    },
    [runSynth]
  );

  const pickPreset = useCallback(
    (slug: string) => {
      if (synthTimer.current) clearTimeout(synthTimer.current);
      const preset = presets.find((p) => p.slug === slug);
      if (preset) {
        setSynthSpec({
          n_gpus: preset.n_gpus,
          gpu_type: preset.gpu_type,
          workload: preset.workload,
          model_class: preset.model_class,
          arch: preset.arch,
          inference_phase: preset.inference_phase,
          cooling: preset.cooling,
          pue: preset.pue,
          climate: preset.climate,
          occupancy_pct: preset.occupancy_pct,
          chip_load_pct: preset.chip_load_pct,
          idle_w: preset.idle_w,
          tdp_w: preset.tdp_w,
          moe_anteil_pct: preset.moe_anteil_pct,
          batch_size: preset.batch_size,
          days: preset.days,
        });
      }
      void runSynth({ preset: slug });
    },
    [runSynth, presets]
  );

  // Combine one or more uploaded CSVs into rows and re-fit the live forecast
  // on them -- real data, no verdicts, feeding straight into /predict.
  const runUpload = useCallback(
    async (files: File[]) => {
      setUploadLoading(true);
      setUploadError(null);
      try {
        const res = await uploadRowsApi(files);
        setUploadedRows(res.rows);
        setUploadLabel(res.label);
        setManualFeatures(null);
        setTarget(null);
        await loadForecast({
          minCorrelation,
          featureCols: null,
          rows: res.rows,
          target: null,
        });
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : String(err));
      } finally {
        setUploadLoading(false);
      }
    },
    [loadForecast, minCorrelation]
  );

  // Save the currently synthesized series as a CSV, so a generated datacenter
  // can be handed around (or re-imported through the upload path) as a file.
  const downloadSynthCsv = useCallback(() => {
    if (!synthRows || synthRows.length === 0) return;
    const blob = new Blob([rowsToCsv(synthRows)], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `rechenzentrum-${synthSpec.n_gpus}gpu-${synthSpec.workload}-pue${synthSpec.pue}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [synthRows, synthSpec]);

  const changeForecastSource = useCallback(
    (source: ForecastSource) => {
      setForecastSource(source);
      setManualFeatures(null);
      setTarget(null);
      const rows = rowsForSource(source);
      if (source === "specs" && !rows) {
        void runSynth(synthSpec);
        return;
      }
      if (source === "upload" && !rows) {
        // No file picked yet: drop the previous source's fit instead of
        // leaving its numbers on screen under an "uploaded data" heading.
        forecastSeq.current++;
        setForecast(null);
        setForecastError(null);
        setForecastLoading(false);
        return;
      }
      void loadForecast({
        minCorrelation,
        featureCols: null,
        rows,
        target: null,
      });
    },
    [loadForecast, minCorrelation, rowsForSource, runSynth, synthSpec]
  );

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-brand">
          <a className="app-brand-plate" href={PROJEKTSEITE_URL}>
            <img
              className="app-brand-logo"
              src="/brand/kisz-logo.png"
              alt="KI-Servicezentrum by Hasso-Plattner-Institut"
            />
          </a>
          <span className="app-brand-text">
            <b>aihpi/datacenter-simulation</b>
            <span>// Stromrechner für KI-Rechenzentren</span>
          </span>
        </div>
        <nav className="app-nav" aria-label="Hauptnavigation">
          <button
            className={`nav-btn ${view === "raw" ? "is-active" : ""}`}
            onClick={openRaw}
            data-testid="nav-raw"
          >
            Rohdaten
          </button>
          <button
            className={`nav-btn ${view === "correlations" ? "is-active" : ""}`}
            onClick={() => setView("correlations")}
            data-testid="nav-correlations"
          >
            Zusammenhänge
          </button>
          <button
            className={`nav-btn ${view === "forecast" ? "is-active" : ""}`}
            onClick={openForecast}
            data-testid="nav-forecast"
          >
            Vorhersage
          </button>
        </nav>
      </header>
      <div className="app-stripe" />

      <section className="app-hero">
        <h1 className="app-title">
          <span className="app-title-prompt" aria-hidden="true">$ </span>
          Was verbraucht ein KI-Rechenzentrum?
        </h1>
        <p className="app-hero-lead">
          Aus GPU-Anzahl, Workload und Kühlung berechnet das Tool Jahresstromverbrauch,
          Stromkosten und CO₂-Äquivalent und übersetzt sie in greifbare Vergleiche.
          Umgekehrt geht es auch: Verbrauch vorgeben, GPU-Anzahl ableiten.
        </p>
      </section>

      <details className="app-intro" data-testid="app-intro">
        <summary>Kurzanleitung</summary>
        <ol>
          <li>
            <b>Rohdaten</b>: Messreihen eines Rechenzentrums (Stromverbrauch,
            Auslastung, Temperatur) als Tabelle mit Profil je Spalte ansehen.
          </li>
          <li>
            <b>Zusammenhänge</b>: Korrelationsmatrix aller Spalten; ein Klick auf
            eine Zelle zeigt den Scatterplot und erlaubt, eine dritte Größe
            herauszurechnen.
          </li>
          <li>
            <b>Vorhersage</b>: Datenquelle wählen (Seed, eigene CSV oder ein aus
            Specs wie GPU-Anzahl und Workload generiertes Rechenzentrum), dann
            liefert das Modell Jahresstromverbrauch, Stromkosten und CO₂-Äquivalent
            mit greifbaren Vergleichen. Die inverse Auslegung rechnet umgekehrt vom
            Jahresverbrauch auf die GPU-Anzahl.
          </li>
        </ol>
      </details>

      {view === "raw" && (
        <RawDataView
          data={rawData}
          dataset={rawDataset}
          loading={rawLoading}
          error={rawError}
          onSelectDataset={selectRawDataset}
          onRetry={() => void loadRaw(rawDataset)}
        />
      )}

      {view === "correlations" && <CorrelationsView />}

      {view === "datenschutz" && (
        <LegalView onBack={() => setView("forecast")} />
      )}

      {view === "forecast" && (
        <ForecastView
          data={forecast}
          loading={forecastLoading}
          error={forecastError}
          onRetry={() => void loadForecast(lastForecastParams.current)}
          minCorrelation={minCorrelation}
          onMinCorrelationChange={changeMinCorrelation}
          onToggleFeature={toggleForecastFeature}
          onTargetChange={changeTarget}
          onDownloadSynth={downloadSynthCsv}
          source={forecastSource}
          onSourceChange={changeForecastSource}
          spec={synthSpec}
          onSpecChange={changeSynthSpec}
          presets={presets}
          onPickPreset={pickPreset}
          synthLabel={synthLabel}
          synthLoading={synthLoading}
          synthError={synthError}
          onUpload={runUpload}
          uploadLabel={uploadLabel}
          uploadLoading={uploadLoading}
          uploadError={uploadError}
        />
      )}
      <footer className="app-footer">
        <p className="app-footer-funding">
          <span className="app-footer-plate">
            <img src="/brand/bmftr-gefoerdert.png" alt="Gefördert durch das BMFTR" />
          </span>
          <span>{FOERDERHINWEIS}</span>
        </p>
        <nav className="app-footer-links" aria-label="Rechtliches">
          <a href={PROJEKTSEITE_URL} data-testid="footer-projektseite">
            hpi.de/kisz
          </a>
          <a href={IMPRESSUM_URL} target="_blank" rel="noopener noreferrer" data-testid="footer-impressum">
            Impressum
          </a>
          <button className="link-btn" onClick={() => setView("datenschutz")} data-testid="footer-datenschutz">
            Datenschutz
          </button>
        </nav>
      </footer>
    </div>
  );
}
