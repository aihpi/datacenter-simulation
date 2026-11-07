import type { AnalyzeResponse, RunRecord } from "../types";

const KEY = "correlation-explainer:history:v1";
const MAX_RUNS = 30;

export function loadHistory(): RunRecord[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as RunRecord[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function save(runs: RunRecord[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(runs));
  } catch {
    /* quota / private mode: history just won't persist */
  }
}

function makeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.floor(Math.random() * 1e9)}`;
}

/** Prepend a new run, cap the list, persist, and return the updated list. */
export function addRun(
  title: string,
  source: string,
  response: AnalyzeResponse
): RunRecord[] {
  const rec: RunRecord = {
    id: makeId(),
    ts: Date.now(),
    title,
    source,
    response,
  };
  const runs = [rec, ...loadHistory()].slice(0, MAX_RUNS);
  save(runs);
  return runs;
}

export function deleteRun(id: string): RunRecord[] {
  const runs = loadHistory().filter((r) => r.id !== id);
  save(runs);
  return runs;
}

export function clearHistory(): RunRecord[] {
  save([]);
  return [];
}
