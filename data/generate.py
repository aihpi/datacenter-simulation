"""Seeded, reproducible synthetic data generator with KNOWN causal structure.

Run: `uv run python data/generate.py`
Writes: data/synthetic.csv, data/ground_truth.json,
        data/fixtures/*.csv + data/fixtures/*.label.json

The true causal structure is known by construction, so correctness is objectively
checkable by eval/run_eval.py.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
DATA_DIR = Path(__file__).resolve().parent
FIX_DIR = DATA_DIR / "fixtures"

DATASET_DESCRIPTION = (
    "Seeded synthetic dataset with a known causal structure spanning study/exam, "
    "exercise/heart-rate, weather-driven ice-cream/drownings, wealth-driven "
    "TV/life-expectancy, a selection (collider) pair, diet/cholesterol, "
    "smoking/lung-issues, and eight independent pure-noise columns."
)

RAND_COLS = [f"rand_{c}" for c in "abcdefgh"]  # 8 i.i.d. noise columns


def generate_main() -> pd.DataFrame:
    """Generate the main synthetic.csv table (the whole table is the selected
    sample for the collider archetype; selection on talent+looks is independent
    of every other variable, so all other relationships are preserved)."""
    rng = np.random.default_rng(SEED)
    n_full = 2500  # after talent+looks selection ~600 rows remain

    # --- collider / selection: talent and looks are INDEPENDENT ---
    talent = rng.normal(0, 1, n_full)
    looks = rng.normal(0, 1, n_full)
    keep = (talent + looks) > 1.0  # select the "admitted/celebrity" subset
    idx = np.where(keep)[0]
    n = idx.size  # number of rows in the final table

    talent = talent[idx]
    looks = looks[idx]

    # --- direct causal: hours_studied -> exam_score ---
    hours_studied = rng.uniform(0, 10, n)
    exam_score = np.clip(8.0 * hours_studied + rng.normal(0, 6, n), 0, 100)

    # --- reverse causal: exercise_minutes -> resting_heart_rate ---
    exercise_minutes = rng.uniform(0, 90, n)
    resting_heart_rate = 80.0 - 0.12 * exercise_minutes + rng.normal(0, 3, n)

    # --- confounded, confounder PRESENT: temperature drives both ---
    temperature = rng.uniform(-5, 35, n)
    ice_cream_sales = np.clip(30.0 * temperature + 200 + rng.normal(0, 80, n), 0, None)
    drownings = np.clip(0.4 * temperature + 2 + rng.normal(0, 3, n), 0, None)

    # --- confounded, confounder ABSENT: hidden WEALTH drives both ---
    wealth = rng.uniform(10_000, 60_000, n)  # NOT written to the CSV
    tv_per_capita = np.clip(0.0002 * wealth + rng.normal(0, 1.5, n), 0, None)
    life_expectancy = 55.0 + 0.0004 * wealth + rng.normal(0, 2, n)

    # --- causal (mixed: categorical -> numeric): diet_type -> cholesterol ---
    diet_type = rng.choice(["low_fat", "balanced", "high_fat"], size=n)
    diet_effect = np.select(
        [diet_type == "low_fat", diet_type == "balanced", diet_type == "high_fat"],
        [-12.0, 4.0, 22.0],
        default=0.0,
    )
    cholesterol = 184.0 + diet_effect + rng.normal(0, 15, n)

    # --- causal (categorical/categorical): smoker -> lung_issue ---
    smoker = rng.choice(["no", "yes"], size=n, p=[0.6, 0.4])
    p_lung = np.where(smoker == "yes", 0.45, 0.08)
    lung_issue = np.where(rng.random(n) < p_lung, "yes", "no")

    data = {
        "record_id": np.arange(n),  # id-like -> dropped by profiling
        "study_version": ["v1"] * n,  # constant -> dropped by profiling
        "hours_studied": hours_studied,
        "exam_score": exam_score,
        "exercise_minutes": exercise_minutes,
        "resting_heart_rate": resting_heart_rate,
        "temperature": temperature,
        "ice_cream_sales": ice_cream_sales,
        "drownings": drownings,
        "tv_per_capita": tv_per_capita,
        "life_expectancy": life_expectancy,
        "talent": talent,
        "looks": looks,
        "diet_type": diet_type,
        "cholesterol": cholesterol,
        "smoker": smoker,
        "lung_issue": lung_issue,
    }
    for c in RAND_COLS:
        data[c] = rng.normal(0, 1, n)

    return pd.DataFrame(data)


def build_ground_truth() -> list[dict]:
    gt: list[dict] = [
        {
            "x": "hours_studied",
            "y": "exam_score",
            "true_label": "causal",
            "confounder": None,
            "confounder_in_data": False,
            "notes": "exam_score = 8*hours_studied + noise; direct causal X->Y.",
        },
        {
            "x": "resting_heart_rate",
            "y": "exercise_minutes",
            "true_label": "reverse_causal",
            "confounder": None,
            "confounder_in_data": False,
            "notes": "exercise lowers resting heart rate; arrow is Y->X.",
        },
        {
            "x": "ice_cream_sales",
            "y": "drownings",
            "true_label": "confounder",
            "confounder": "temperature",
            "confounder_in_data": True,
            "notes": "both driven by temperature, which IS a column.",
        },
        {
            "x": "temperature",
            "y": "ice_cream_sales",
            "true_label": "causal",
            "confounder": None,
            "confounder_in_data": False,
            "notes": "temperature drives ice cream sales (the root cause itself).",
        },
        {
            "x": "temperature",
            "y": "drownings",
            "true_label": "causal",
            "confounder": None,
            "confounder_in_data": False,
            "notes": "temperature drives drownings (the root cause itself).",
        },
        {
            "x": "tv_per_capita",
            "y": "life_expectancy",
            "true_label": "confounder",
            "confounder": "national_wealth",
            "confounder_in_data": False,
            "notes": "both driven by hidden WEALTH, which is NOT a column.",
        },
        {
            "x": "talent",
            "y": "looks",
            "true_label": "selection",
            "confounder": None,
            "confounder_in_data": False,
            "notes": "independent in the population; collider selection on talent+looks.",
        },
        {
            "x": "diet_type",
            "y": "cholesterol",
            "true_label": "causal",
            "confounder": None,
            "confounder_in_data": False,
            "notes": "diet category drives cholesterol; mixed (categorical->numeric).",
        },
        {
            "x": "smoker",
            "y": "lung_issue",
            "true_label": "causal",
            "confounder": None,
            "confounder_in_data": False,
            "notes": "smoking raises lung-issue probability; categorical/categorical.",
        },
    ]
    # All pairs among the 8 independent noise columns -> pure chance.
    for a, b in itertools.combinations(RAND_COLS, 2):
        gt.append(
            {
                "x": a,
                "y": b,
                "true_label": "chance",
                "confounder": None,
                "confounder_in_data": False,
                "notes": "independent noise columns; any association is sampling noise.",
            }
        )
    return gt


def write_fixtures() -> None:
    """Small hand-built demo fixtures, each a tiny CSV + a label.json."""
    FIX_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED + 7)

    # ice cream vs drownings, temperature PRESENT (confounder in data)
    n = 45
    temp = rng.uniform(-2, 32, n)
    ice = np.clip(28 * temp + 180 + rng.normal(0, 70, n), 0, None)
    drown = np.clip(0.38 * temp + 2 + rng.normal(0, 2.5, n), 0, None)
    pd.DataFrame(
        {
            "temperature": np.round(temp, 2),
            "ice_cream_sales": np.round(ice, 1),
            "drownings": np.round(drown, 2),
        }
    ).to_csv(FIX_DIR / "ice_cream_drownings.csv", index=False)
    (FIX_DIR / "ice_cream_drownings.label.json").write_text(
        json.dumps(
            {
                "description": "Ice cream sales vs drownings, with temperature recorded.",
                "pairs": [
                    {
                        "x": "ice_cream_sales",
                        "y": "drownings",
                        "true_label": "confounder",
                        "confounder": "temperature",
                        "confounder_in_data": True,
                        "notes": "Classic summer confounder; temperature is present so it is verifiable.",
                    }
                ],
            },
            indent=2,
        )
    )

    # chocolate vs Nobel, national wealth ABSENT
    n = 28
    wealth = rng.uniform(8_000, 70_000, n)
    choc = np.clip(0.00012 * wealth + rng.normal(0, 1.0, n), 0, None)
    nobel = np.clip(0.0004 * wealth + rng.normal(0, 4.0, n), 0, None)
    pd.DataFrame(
        {
            "chocolate_kg": np.round(choc, 2),
            "nobel_per_capita": np.round(nobel, 2),
        }
    ).to_csv(FIX_DIR / "chocolate_nobel.csv", index=False)
    (FIX_DIR / "chocolate_nobel.label.json").write_text(
        json.dumps(
            {
                "description": "Per-capita chocolate consumption vs Nobel laureates.",
                "pairs": [
                    {
                        "x": "chocolate_kg",
                        "y": "nobel_per_capita",
                        "true_label": "confounder",
                        "confounder": "national_wealth",
                        "confounder_in_data": False,
                        "notes": "National wealth drives both; it is absent from the data.",
                    }
                ],
            },
            indent=2,
        )
    )

    # storks vs births, development/area ABSENT
    n = 30
    development = rng.uniform(0, 100, n)
    storks = np.clip(1.5 * development + rng.normal(0, 25, n), 0, None)
    births = np.clip(2.2 * development + rng.normal(0, 30, n), 0, None)
    pd.DataFrame(
        {
            "stork_pairs": np.round(storks, 0),
            "human_births": np.round(births, 0),
        }
    ).to_csv(FIX_DIR / "storks_births.csv", index=False)
    (FIX_DIR / "storks_births.label.json").write_text(
        json.dumps(
            {
                "description": "Stork pairs vs human births across regions.",
                "pairs": [
                    {
                        "x": "stork_pairs",
                        "y": "human_births",
                        "true_label": "confounder",
                        "confounder": "regional_development",
                        "confounder_in_data": False,
                        "notes": "Region size/development drives both; absent from the data.",
                    }
                ],
            },
            indent=2,
        )
    )


def write_forecast() -> None:
    """Single hourly time series for the regression/forecast feature (/predict).

    Target `it_stromverbrauch_kw` is a linear function of the compute-load
    features (GPU dominant, CPU secondary) plus a mild weekday effect; the
    outside temperature is included as a feature but does NOT drive IT power, so
    a correct model gives it a near-zero weight. Time-ordered, so the last slice
    is a clean hold-out window for the forecast chart.
    """
    rng = np.random.default_rng(606)
    n = 672  # 28 days, hourly
    zeit = pd.date_range("2026-01-01", periods=n, freq="h")
    stunde = np.arange(n) % 24
    wochentag = (np.arange(n) // 24) % 7
    is_weekend = wochentag >= 5

    daily = np.sin((stunde - 14) / 24 * 2 * np.pi)
    weekly = np.where(is_weekend, 0.7, 1.0)  # lighter load on weekends
    aktive_jobs = np.clip((120 + 60 * daily) * weekly + rng.normal(0, 18, n), 0, None).round()

    gpu = np.clip(0.45 * aktive_jobs + rng.normal(0, 6, n), 0, 100).round(1)
    cpu = np.clip(15 + 0.30 * aktive_jobs + rng.normal(0, 6, n), 0, 100).round(1)
    aussentemp = (8 + 6 * np.sin((stunde - 15) / 24 * 2 * np.pi) + rng.normal(0, 1.5, n)).round(1)

    # IT power: GPU dominant, CPU secondary, small weekend dip; outside temp has
    # NO effect (a good model learns ~0 weight for it).
    it_strom = np.clip(
        40 + 1.1 * gpu + 0.5 * cpu - 2.0 * is_weekend + rng.normal(0, 4, n), 0, None
    ).round(1)

    # ── Downstream cooling subsystem (rich structure for the analysis phase) ──
    # IT power is the ROOT cause. Cooling power rises with the IT heat load (plus
    # a little with outside temperature). Server-room temperature and fan speed
    # are ALSO driven by the IT load -- not by each other -- so any correlation
    # WITHIN {kuehlung, serverraum_temp, luefterdrehzahl} is a CONFOUNDER story
    # with it_stromverbrauch_kw as the common cause. Network latency is
    # near-independent noise: a decoy feature that should land as "chance".
    kuehlung = np.clip(
        0.45 * it_strom + 0.6 * aussentemp + rng.normal(0, 3, n), 0, None
    ).round(1)
    serverraum_temp = (20 + 0.05 * it_strom + rng.normal(0, 0.5, n)).round(2)
    luefterdrehzahl = np.clip(
        2000 + 14 * it_strom + rng.normal(0, 90, n), 0, None
    ).round()
    netzwerk_latenz = np.clip(18 + rng.normal(0, 4, n), 0, None).round(1)

    load_cols = {
        "zeitstempel": zeit.strftime("%Y-%m-%d %H:%M"),
        "stunde": stunde,
        "wochentag": wochentag,
        "aktive_jobs": aktive_jobs,
        "gpu_auslastung_pct": gpu,
        "cpu_auslastung_pct": cpu,
        "aussentemperatur_c": aussentemp,
        "it_stromverbrauch_kw": it_strom,
    }

    # rechenzentrum_load.csv -- upstream inputs only; the honest forecast set
    # (downstream columns would leak the target, so they live in _full).
    out = DATA_DIR / "rechenzentrum_load.csv"
    pd.DataFrame(load_cols).to_csv(out, index=False)
    print(f"Wrote {out} with {n} rows (forecast target: it_stromverbrauch_kw).")

    # rechenzentrum_full.csv -- inputs + target + the cooling subsystem; used by
    # the raw-data inspector and the correlation-analysis phase.
    full = DATA_DIR / "rechenzentrum_full.csv"
    pd.DataFrame(
        {
            **load_cols,
            "kuehlung_stromverbrauch_kw": kuehlung,
            "serverraum_temp_c": serverraum_temp,
            "luefterdrehzahl_rpm": luefterdrehzahl,
            "netzwerk_latenz_ms": netzwerk_latenz,
        }
    ).to_csv(full, index=False)
    print(f"Wrote {full} with {n} rows (enriched: + cooling subsystem).")


def main() -> None:
    df = generate_main()
    out_csv = DATA_DIR / "synthetic.csv"
    df.to_csv(out_csv, index=False)

    gt = build_ground_truth()
    (DATA_DIR / "ground_truth.json").write_text(json.dumps(gt, indent=2))

    write_fixtures()
    write_forecast()

    print(f"Wrote {out_csv} with {len(df)} rows, {df.shape[1]} columns.")
    print(f"Wrote ground_truth.json with {len(gt)} labeled pairs.")
    print(f"Wrote fixtures to {FIX_DIR}/")


if __name__ == "__main__":
    main()
