import type {
  AnalyzeResponse,
  CorrelationMatrix,
  PairData,
  PredictResponse,
  ProgressEvent,
  RawDataResponse,
  SynthesizePreset,
  SynthesizeResponse,
  SynthesizeSpec,
  Theme,
  UploadRowsResponse,
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

/** Pull a human-readable error out of a FastAPI JSON error body when possible. */
async function readError(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    /* not JSON */
  }
  return `Backend antwortete mit ${res.status}`;
}

export async function fetchThemes(): Promise<Theme[]> {
  const res = await fetch(`${API_BASE}/themes`);
  if (!res.ok) throw new Error(await readError(res));
  const body = (await res.json()) as { themes: Theme[] };
  return body.themes;
}

/** Read a newline-delimited JSON stream, forwarding step events and returning
 *  the final result payload. Throws on transport or mid-stream errors. */
async function consumeStream(
  res: Response,
  onEvent: (e: ProgressEvent) => void
): Promise<AnalyzeResponse> {
  if (!res.ok) throw new Error(await readError(res));
  if (!res.body) throw new Error("Antwort ohne Stream-Body.");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: AnalyzeResponse | null = null;

  const handleLine = (raw: string) => {
    const line = raw.trim();
    if (!line) return;
    const ev = JSON.parse(line) as
      | ProgressEvent
      | { type: "result"; data: AnalyzeResponse }
      | { type: "error"; detail: string };
    if (ev.type === "result") result = ev.data;
    else if (ev.type === "error") throw new Error(ev.detail);
    else onEvent(ev);
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let nl: number;
    while ((nl = buffer.indexOf("\n")) >= 0) {
      handleLine(buffer.slice(0, nl));
      buffer = buffer.slice(nl + 1);
    }
  }
  if (buffer.trim()) handleLine(buffer);

  if (!result) throw new Error("Stream endete ohne Ergebnis.");
  return result;
}

/** Fit a linear-regression forecast for a numeric target (default: the seeded
 *  datacenter load series) and return the hold-out evaluation. */
export async function runPredict(
  body: {
    dataset?: string;
    rows?: Record<string, unknown>[];
    target?: string;
    test_fraction?: number;
    min_correlation?: number;
    feature_cols?: string[];
  } = {}
): Promise<PredictResponse> {
  const res = await fetch(`${API_BASE}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as PredictResponse;
}

/** Generate a plausible datacenter load series from a few specs (or a named
 *  preset), for the "no real data available" path of the forecast tab. */
export async function runSynthesize(
  spec: SynthesizeSpec | { preset: string }
): Promise<SynthesizeResponse> {
  const res = await fetch(`${API_BASE}/synthesize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as SynthesizeResponse;
}

/** Serialize rows to CSV text (columns from the first row, in order). */
export function rowsToCsv(rows: Record<string, unknown>[]): string {
  if (rows.length === 0) return "";
  const cols = Object.keys(rows[0]);
  const cell = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return (
    [
      cols.join(","),
      ...rows.map((r) => cols.map((c) => cell(r[c])).join(",")),
    ].join("\n") + "\n"
  );
}

export async function fetchSynthesizePresets(): Promise<SynthesizePreset[]> {
  const res = await fetch(`${API_BASE}/synthesize/presets`);
  if (!res.ok) throw new Error(await readError(res));
  const body = (await res.json()) as { presets: SynthesizePreset[] };
  return body.presets;
}

/** Combine one or more uploaded CSVs into rows for the forecast tab (real
 *  data, no verdicts) -- the /predict counterpart of /upload/stream. */
export async function uploadRows(files: File[]): Promise<UploadRowsResponse> {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  const res = await fetch(`${API_BASE}/upload/rows`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as UploadRowsResponse;
}

/** Fetch a dataset's raw rows + column profile for the raw-data inspector. */
export async function fetchRawData(
  dataset = "rechenzentrum_load.csv",
  limit = 1000
): Promise<RawDataResponse> {
  const params = new URLSearchParams({ dataset, limit: String(limit) });
  const res = await fetch(`${API_BASE}/raw?${params}`);
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as RawDataResponse;
}

/** Fetch the full pairwise correlation matrix for the relationship explorer. */
export async function fetchCorrelations(
  dataset = "rechenzentrum_full.csv"
): Promise<CorrelationMatrix> {
  const params = new URLSearchParams({ dataset });
  const res = await fetch(`${API_BASE}/correlations?${params}`);
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as CorrelationMatrix;
}

/** Fetch one X-Y pair (scatter + correlation), optionally controlling for Z. */
export async function fetchPair(
  x: string,
  y: string,
  z?: string,
  dataset = "rechenzentrum_full.csv"
): Promise<PairData> {
  const params = new URLSearchParams({ dataset, x, y });
  if (z) params.set("z", z);
  const res = await fetch(`${API_BASE}/pair?${params}`);
  if (!res.ok) throw new Error(await readError(res));
  return (await res.json()) as PairData;
}

export async function streamTheme(
  slug: string,
  onEvent: (e: ProgressEvent) => void
): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/analyze/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ theme: slug }),
  });
  return consumeStream(res, onEvent);
}

export async function streamUpload(
  files: File[],
  onEvent: (e: ProgressEvent) => void
): Promise<AnalyzeResponse> {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  const res = await fetch(`${API_BASE}/upload/stream`, {
    method: "POST",
    body: form,
  });
  return consumeStream(res, onEvent);
}
