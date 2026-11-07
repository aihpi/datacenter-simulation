"""Pipeline eval: run the full pipeline on every ground-truth pair and score it.

Usage:
    LLM_BACKEND=mock   uv run python eval/run_eval.py   # default; proves plumbing
    LLM_BACKEND=vertex uv run python eval/run_eval.py   # real explanation quality

Exits non-zero if the active backend's thresholds (see eval/criteria.md) fail.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Make the project root importable when run as a script.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from api.pipeline import analyze_ground_truth_pairs  # noqa: E402
from engine.llm import get_client  # noqa: E402
from engine.llm.base import VERDICT_LABELS  # noqa: E402

DATA_DIR = ROOT / "data"


def _confusion(rows: list[dict]) -> None:
    idx = {lbl: i for i, lbl in enumerate(VERDICT_LABELS)}
    mat = [[0] * len(VERDICT_LABELS) for _ in VERDICT_LABELS]
    for r in rows:
        mat[idx[r["true"]]][idx[r["pred"]]] += 1
    w = max(len(l) for l in VERDICT_LABELS)
    head = " " * (w + 2) + " ".join(f"{l[:6]:>7}" for l in VERDICT_LABELS)
    print("\nConfusion matrix (rows=true, cols=pred):")
    print(head)
    for i, lbl in enumerate(VERDICT_LABELS):
        line = f"{lbl:>{w}}  " + " ".join(f"{mat[i][j]:>7}" for j in range(len(VERDICT_LABELS)))
        print(line)


def main() -> int:
    backend = os.environ.get("LLM_BACKEND", "mock").lower()

    df = pd.read_csv(DATA_DIR / "synthetic.csv")
    gt = json.loads((DATA_DIR / "ground_truth.json").read_text())
    description = (
        "Seeded synthetic dataset with a known causal structure used to validate "
        "the correlation-explanation pipeline."
    )

    llm = get_client()
    results = analyze_ground_truth_pairs(df, description, gt, llm)

    rows: list[dict] = []
    for entry, ap in zip(gt, results):
        verdict_ok = ap.verdict.verdict == entry["true_label"]
        indata_ok = ap.verdict.confounder_in_data == bool(entry["confounder_in_data"])
        rows.append(
            {
                "x": entry["x"],
                "y": entry["y"],
                "true": entry["true_label"],
                "pred": ap.verdict.verdict,
                "true_indata": bool(entry["confounder_in_data"]),
                "pred_indata": ap.verdict.confounder_in_data,
                "conf": ap.verdict.confidence,
                "verdict_ok": verdict_ok,
                "indata_ok": indata_ok,
                "pass": verdict_ok and indata_ok,
            }
        )

    n = len(rows)
    n_correct = sum(r["verdict_ok"] for r in rows)
    n_indata = sum(r["indata_ok"] for r in rows)
    accuracy = n_correct / n if n else 0.0
    indata_rate = n_indata / n if n else 0.0

    chance_rows = [r for r in rows if r["true"] == "chance"]
    chance_correct = sum(r["pred"] == "chance" for r in chance_rows)
    chance_acc = chance_correct / len(chance_rows) if chance_rows else 1.0

    # ---- per-case table (cap verbose random pairs) ----
    print(f"=== datacenter-simulation eval (LLM_BACKEND={backend}) ===")
    print(f"\nPer-case (showing non-chance + first 3 chance):")
    print(f"  {'x':<20}{'y':<20}{'true':<15}{'pred':<15}{'in_data':<16}{'result'}")
    shown_chance = 0
    for r in rows:
        if r["true"] == "chance":
            shown_chance += 1
            if shown_chance > 3:
                continue
        indata = f"{int(r['true_indata'])}->{int(r['pred_indata'])}"
        res = "PASS" if r["pass"] else "FAIL"
        print(
            f"  {r['x']:<20}{r['y']:<20}{r['true']:<15}{r['pred']:<15}{indata:<16}{res}"
        )
    if len(chance_rows) > 3:
        print(f"  ... and {len(chance_rows) - 3} more chance pairs")

    _confusion(rows)

    print("\n=== Summary ===")
    print(f"  pairs evaluated         : {n}")
    print(f"  verdict accuracy        : {accuracy:.1%} ({n_correct}/{n})")
    print(f"  confounder_in_data match: {indata_rate:.1%} ({n_indata}/{n})")
    print(f"  chance accuracy (noise) : {chance_acc:.1%} ({chance_correct}/{len(chance_rows)})")

    # ---- thresholds ----
    if backend == "mock":
        acc_thresh, require_indata_full = 1.0, True
    else:
        acc_thresh, require_indata_full = 0.80, False
    chance_thresh = 0.90

    failures: list[str] = []
    if accuracy < acc_thresh:
        failures.append(f"verdict accuracy {accuracy:.1%} < {acc_thresh:.0%}")
    if chance_acc < chance_thresh:
        failures.append(f"chance accuracy {chance_acc:.1%} < {chance_thresh:.0%}")
    if require_indata_full and indata_rate < 1.0:
        failures.append(f"confounder_in_data match {indata_rate:.1%} < 100%")

    print("\n=== Gates ===")
    if failures:
        for f in failures:
            print(f"  FAIL: {f}")
        print("\nRESULT: FAIL")
        return 1
    print(f"  PASS: accuracy >= {acc_thresh:.0%}, chance >= {chance_thresh:.0%}"
          + (", confounder_in_data == 100%" if require_indata_full else ""))
    print("\nRESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
