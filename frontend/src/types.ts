export type VerdictLabel =
  | "causal"
  | "reverse_causal"
  | "confounder"
  | "selection"
  | "chance";

export interface CorrelationStat {
  method: string;
  coefficient: number;
  effect_size: number;
  p_value: number;
  p_adjusted: number;
  n: number;
  significant: boolean;
}

/** One alternative explanation the model considered and rejected. */
export interface RuledOut {
  label: VerdictLabel;
  why: string;
}

export interface Verdict {
  x: string;
  y: string;
  verdict: VerdictLabel;
  confidence: number;
  confounder: string | null;
  confounder_in_data: boolean;
  reasoning: string;
  needed_data: string;
  /** Why each non-chosen category was excluded. Optional for older payloads. */
  ruled_out?: RuledOut[];
}

export interface VerificationResult {
  confounder: string;
  method: string;
  r_before: number;
  r_after: number;
  p_after: number;
  n: number;
  threshold_abs: number;
  collapsed: boolean;
  note: string;
}

export interface PlotPoint {
  x: number;
  y: number;
}

export interface BarGroup {
  category: string;
  value: number;
  n: number;
}

export interface PlotData {
  kind: "scatter" | "grouped_bar";
  x_label: string;
  y_label: string;
  points: PlotPoint[];
  bars: BarGroup[];
  value_label: string | null;
}

/** Everyday-language readout of one pair (mirrors api.schemas.PlainStats). */
export interface PlainStats {
  summary: string;
  strength_label: string;
  strength_pct: number;
  direction: "positiv" | "negativ" | "keine";
  explained_pct: number | null;
  rule_of_thumb: string | null;
  chance_text: string;
}

export interface AnalysisPair {
  x: string;
  y: string;
  stat: CorrelationStat;
  verdict: Verdict;
  verification: VerificationResult | null;
  plot: PlotData;
  /** Everyday-language readout. Optional for older payloads. */
  plain?: PlainStats | null;
}

export interface DroppedColumn {
  name: string;
  reason: string;
}

export interface AnalyzeResponse {
  dataset: string;
  description: string;
  n_tested_pairs: number;
  pairs: AnalysisPair[];
  dropped_columns?: DroppedColumn[];
}

/** A curated topic from GET /themes. */
export interface Theme {
  slug: string;
  title: string;
  emoji: string;
  summary: string;
  kind: "example" | "dataset";
  files: string[];
  key_hint: string | null;
}

/** One streamed progress event from /analyze/stream or /upload/stream. */
export interface ProgressEvent {
  type: "step";
  stage: string;
  label: string;
  progress: number;
  detail?: string;
  pair?: { x: string; y: string };
}

/** A saved analysis run (persisted in localStorage for the history view). */
export interface RunRecord {
  id: string;
  ts: number;
  title: string;
  source: string;
  response: AnalyzeResponse;
}

export const VERDICT_LABELS: VerdictLabel[] = [
  "causal",
  "reverse_causal",
  "confounder",
  "selection",
  "chance",
];

/** One regression feature's raw slope and standardized influence. */
export interface FeatureWeight {
  name: string;
  coefficient: number;
  std_importance: number;
}

/** One hold-out row: actual vs predicted target value. */
export interface ForecastPoint {
  index: number;
  actual: number;
  predicted: number;
  label: string | null;
  /** Feature values at this row (by name) for the contribution breakdown. */
  values?: Record<string, number> | null;
}

/** Per-feature slope + value range, for the prediction explainers. */
export interface FeatureStat {
  name: string;
  coefficient: number;
  mean: number;
  min: number;
  max: number;
}

/** A numeric column's correlation with the target, whether or not it's
 *  currently included in the fitted model — powers the feature checklist.
 *  `same_measure` marks another meter of the target quantity (total vs. IT vs.
 *  cooling power): togglable by hand, never auto-selected. */
export interface FeatureCandidate {
  name: string;
  correlation: number;
  effect_size: number;
  included: boolean;
  same_measure: boolean;
}

/** Result of POST /predict: a linear-regression forecast on a hold-out window. */
export interface PredictResponse {
  dataset: string;
  target: string;
  features: string[];
  method: string;
  n_train: number;
  n_test: number;
  r2: number;
  mae: number;
  rmse: number;
  baseline_mae: number;
  intercept: number;
  weights: FeatureWeight[];
  series: ForecastPoint[];
  feature_stats: FeatureStat[];
  candidates: FeatureCandidate[];
  min_correlation: number;
  available_targets: string[];
}

/** POST /synthesize request: a few datacenter specs instead of a CSV. */
export type GpuType = "l40s" | "a100" | "h100" | "h200" | "b200";
export type CoolingType = "luft" | "warmwasser" | "direktchip" | "immersion";
export type ModelClass = "klein" | "70b" | "120b";
export type ModelArch = "dense" | "moe";
export type InferencePhase = "decode" | "prefill";

export interface SynthesizeSpec {
  n_gpus: number;
  gpu_type: GpuType;
  workload: "training" | "inference";
  model_class: ModelClass;
  arch: ModelArch;
  inference_phase: InferencePhase;
  cooling: CoolingType;
  pue: number;
  climate: "kalt" | "gemaessigt" | "warm";
  occupancy_pct: number;
  chip_load_pct: number;
  idle_w: number;
  tdp_w: number;
  moe_anteil_pct: number;
  batch_size: number;
  days: number;
}

/** Result of POST /synthesize: a plausible generated load series. */
export interface SynthesizeResponse {
  label: string;
  rows: Record<string, unknown>[];
  columns: string[];
}

export interface SynthesizePreset extends SynthesizeSpec {
  slug: string;
  /** Short button caption, e.g. "50k H100 · Training". */
  name: string;
  /** Full spec readout, shown as the button's second line. */
  label: string;
}

/** Result of POST /upload/rows: combined rows from uploaded CSV(s), for the
 *  forecast tab (as opposed to /upload, which returns correlation verdicts). */
export interface UploadRowsResponse {
  label: string;
  rows: Record<string, unknown>[];
  columns: string[];
}

/** One column's type + lightweight profile (mirrors api.schemas.RawColumn). */
export interface RawColumn {
  name: string;
  dtype: "numeric" | "text";
  n_missing: number;
  min: number | null;
  max: number | null;
  mean: number | null;
  std: number | null;
  n_unique: number | null;
  example: string | null;
}

/** Raw dataset preview from GET /raw (mirrors api.schemas.RawDataResponse). */
export interface RawDataResponse {
  dataset: string;
  n_rows: number;
  n_cols: number;
  columns: RawColumn[];
  rows: Record<string, string | number | null>[];
  returned_rows: number;
}

/** Pairwise correlation matrix from GET /correlations. */
export interface CorrelationMatrix {
  dataset: string;
  columns: string[];
  n: number;
  pearson: (number | null)[][];
  spearman: (number | null)[][];
}

export interface PairPoint {
  x: number;
  y: number;
}

/** One X-Y pair (+ optional control Z) from GET /pair. */
export interface PairData {
  dataset: string;
  x: string;
  y: string;
  n: number;
  r: number | null;
  rho: number | null;
  points: PairPoint[];
  z: string | null;
  partial_r: number | null;
  residual_points: PairPoint[];
}

export type CorrMethod = "pearson" | "spearman";

export interface DatasetOption {
  value: string;
  label: string;
}

export const DATASET_OPTIONS: DatasetOption[] = [
  { value: "synthetic.csv", label: "Synthetic (full)" },
  { value: "fixtures/ice_cream_drownings.csv", label: "Ice cream vs drownings" },
  { value: "fixtures/chocolate_nobel.csv", label: "Chocolate vs Nobel" },
  { value: "fixtures/storks_births.csv", label: "Storks vs births" },
];

/** Datasets offered in the raw-data inspector (datacenter forecast focus). */
export const RAW_DATASET_OPTIONS: DatasetOption[] = [
  { value: "rechenzentrum_full.csv", label: "Rechenzentrum, komplett (Eingaben und Kühlung)" },
  { value: "rechenzentrum_load.csv", label: "Rechenzentrum, nur Vorhersage-Eingaben (6 Spalten)" },
];

export const RAW_DEFAULT_DATASET = "rechenzentrum_full.csv";
