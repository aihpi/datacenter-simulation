"""Write the spec-based datacenter presets out as CSV files.

The forecast tab can synthesize these live, but having them on disk makes them
importable through the normal CSV upload path -- useful for a demo where the
"real data" story is told with a file rather than a form.

    uv run python data/generate_synthetic_rz.py
"""

from __future__ import annotations

from pathlib import Path

from engine.synth import PRESETS, synthesize_rechenzentrum

OUT_DIR = Path(__file__).resolve().parent / "synthetisch"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for slug, spec in PRESETS.items():
        df = synthesize_rechenzentrum(spec)
        out = OUT_DIR / f"{slug}.csv"
        df.to_csv(out, index=False)
        print(
            f"Wrote {out} ({len(df)} rows, {spec.n_gpus:,} GPUs, "
            f"{spec.workload}, PUE {spec.pue}, {spec.climate})"
        )


if __name__ == "__main__":
    main()
