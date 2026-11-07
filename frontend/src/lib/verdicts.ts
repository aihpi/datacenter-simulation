import type { AnalysisPair, VerdictLabel } from "../types";

export const VERDICT_TEXT: Record<VerdictLabel, string> = {
  causal: "Kausal",
  reverse_causal: "Umgekehrt kausal",
  confounder: "Confounder",
  selection: "Selektionseffekt",
  chance: "Zufall",
};

export const VERDICT_ORDER: VerdictLabel[] = [
  "causal",
  "reverse_causal",
  "confounder",
  "selection",
  "chance",
];

// How "interesting" each verdict is for a headline. A confounder that the data
// confirms (the "correlation ≠ causation" punchline) ranks highest; plain chance
// ranks lowest. Effect size breaks ties.
const INTEREST_BASE: Record<VerdictLabel, number> = {
  confounder: 60,
  selection: 85,
  reverse_causal: 80,
  causal: 45,
  chance: 10,
};

function interestScore(pair: AnalysisPair): number {
  let base = INTEREST_BASE[pair.verdict.verdict];
  if (pair.verdict.verdict === "confounder" && pair.verification?.collapsed) {
    base = 100; // a verified confounder is the most compelling finding
  }
  return base + Math.min(1, Math.abs(pair.stat.effect_size));
}

/** Index of the single most interesting pair to feature as the headline. */
export function headlineIndex(pairs: AnalysisPair[]): number {
  if (pairs.length === 0) return -1;
  let best = 0;
  let bestScore = -Infinity;
  pairs.forEach((p, i) => {
    const s = interestScore(p);
    if (s > bestScore) {
      bestScore = s;
      best = i;
    }
  });
  return best;
}

/** Count pairs per verdict category, preserving the canonical order. */
export function verdictCounts(
  pairs: AnalysisPair[]
): { label: VerdictLabel; count: number }[] {
  const counts = new Map<VerdictLabel, number>();
  for (const p of pairs) {
    counts.set(p.verdict.verdict, (counts.get(p.verdict.verdict) ?? 0) + 1);
  }
  return VERDICT_ORDER.filter((l) => counts.has(l)).map((label) => ({
    label,
    count: counts.get(label) ?? 0,
  }));
}
