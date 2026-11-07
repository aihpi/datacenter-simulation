"""Spec-based synthetic datacenter load generator.

IT power is ``n_gpus * (idle + (tdp - idle) * occupancy * chip_load)``.
Occupancy is the fraction of GPUs with work; chip_load is how hard a busy
GPU runs as a fraction of (TDP − idle). Cooling is ``it * (pue - 1)`` plus
a cooling-type climate term.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

Workload = Literal["training", "inference"]
Climate = Literal["kalt", "gemaessigt", "warm"]
GpuType = Literal["l40s", "a100", "h100", "h200", "b200"]
Cooling = Literal["luft", "warmwasser", "direktchip", "immersion"]
ModelClass = Literal["klein", "70b", "120b"]
Arch = Literal["dense", "moe"]
InferencePhase = Literal["decode", "prefill"]

GPU_SPECS: dict[GpuType, tuple[float, float]] = {
    "l40s": (0.350, 50.0),
    "a100": (0.400, 75.0),
    "h100": (0.700, 100.0),
    "h200": (0.700, 100.0),
    "b200": (1.000, 150.0),
}

COOLING_SPECS: dict[Cooling, tuple[float, float]] = {
    "luft": (1.50, 0.025),
    "warmwasser": (1.30, 0.015),
    "direktchip": (1.15, 0.006),
    "immersion": (1.08, 0.002),
}

CLIMATE_BASE_TEMP_C = {
    "kalt": 2.0,
    "gemaessigt": 8.0,
    "warm": 18.0,
}

GPU_LABEL = {
    "l40s": "L40S",
    "a100": "A100",
    "h100": "H100",
    "h200": "H200",
    "b200": "B200",
}

COOLING_LABEL = {
    "luft": "Luft",
    "warmwasser": "Warmwasser",
    "direktchip": "Direktchip",
    "immersion": "Immersion",
}

MODEL_LABEL = {
    "klein": "klein",
    "70b": "70B",
    "120b": "120B",
}

CLIMATE_LABEL = {
    "kalt": "kalt",
    "gemaessigt": "gemäßigt",
    "warm": "warm",
}

METER_NOISE_REL = 0.01
"""Relative standard deviation of the IT power meter.

Without an independent error term the power channel is an exact function of the
GPU utilisation column, so any regression that includes it scores R² = 1 and the
forecast tab shows a tautology instead of a forecast. Real facility meters have
about a percent of jitter; the seeded dataset (``data/generate.py``) models the
same thing with an additive noise term.
"""


@dataclass(frozen=True)
class DatacenterSpec:
    n_gpus: int = 50_000
    gpu_type: GpuType = "h100"
    workload: Workload = "training"
    model_class: ModelClass = "70b"
    arch: Arch = "dense"
    inference_phase: InferencePhase = "decode"
    cooling: Cooling = "warmwasser"
    pue: float = 1.3
    climate: Climate = "gemaessigt"
    occupancy_pct: float = 100.0
    chip_load_pct: float = 75.0
    idle_w: float = 100.0
    tdp_w: float = 700.0
    moe_anteil_pct: float = 12.5
    batch_size: int = 16
    days: int = 14
    seed: int = 606


def default_occupancy_chip(
    workload: Workload,
    model_class: ModelClass,
    arch: Arch,
    inference_phase: InferencePhase,
    moe_anteil_pct: float = 12.5,
    batch_size: int = 16,
) -> tuple[float, float]:
    model_occ = {"klein": -12.0, "70b": 0.0, "120b": 10.0}[model_class]
    model_chip = {"klein": -3.0, "70b": 0.0, "120b": 3.0}[model_class]
    if arch == "moe":
        anteil = float(np.clip(moe_anteil_pct / 100.0, 0.01, 1.0))
        moe = 8.0 * (1.0 - anteil)
    else:
        moe = 0.0
    batch = max(float(batch_size), 1.0)
    if workload == "training":
        occ = 100.0
        chip = 75.0 + model_chip + 2.0 * np.log2(batch / 64.0) - moe
    elif inference_phase == "prefill":
        occ = float(np.clip(85.0 + model_occ * 0.5, 20.0, 100.0))
        chip = 95.0 - moe + 2.5 * np.log2(batch / 8.0)
    else:
        sat = 1.0 - np.exp(-batch / 16.0)
        occ = float(np.clip(40.0 + model_occ + 25.0 * sat, 15.0, 95.0))
        chip = 38.0 + 52.0 * sat - moe + model_chip
    return occ, float(np.clip(chip, 20.0, 100.0))


PRESETS: dict[str, DatacenterSpec] = {
    "50k-h100-training": DatacenterSpec(
        n_gpus=50_000,
        gpu_type="h100",
        workload="training",
        model_class="70b",
        arch="dense",
        inference_phase="decode",
        cooling="direktchip",
        pue=1.2,
        climate="kalt",
        occupancy_pct=100.0,
        chip_load_pct=75.0,
        idle_w=100.0,
        tdp_w=700.0,
    ),
    "100k-h100-training-kalt": DatacenterSpec(
        n_gpus=100_000,
        gpu_type="h100",
        workload="training",
        model_class="120b",
        arch="dense",
        inference_phase="decode",
        cooling="direktchip",
        pue=1.15,
        climate="kalt",
        occupancy_pct=100.0,
        chip_load_pct=78.0,
        idle_w=100.0,
        tdp_w=700.0,
    ),
    "10k-h100-inference-warm": DatacenterSpec(
        n_gpus=10_000,
        gpu_type="h100",
        workload="inference",
        model_class="70b",
        arch="dense",
        inference_phase="decode",
        cooling="luft",
        pue=1.6,
        climate="warm",
        occupancy_pct=56.0,
        chip_load_pct=71.0,
        idle_w=100.0,
        tdp_w=700.0,
    ),
    "aws-global-aggregat": DatacenterSpec(
        n_gpus=500_000,
        gpu_type="h100",
        workload="inference",
        model_class="70b",
        arch="dense",
        inference_phase="decode",
        cooling="warmwasser",
        pue=1.35,
        climate="gemaessigt",
        occupancy_pct=50.0,
        chip_load_pct=70.0,
        idle_w=100.0,
        tdp_w=700.0,
    ),
}

PRESET_NAMES: dict[str, str] = {
    "50k-h100-training": "50k H100, Training",
    "100k-h100-training-kalt": "100k H100, Training, kalt",
    "10k-h100-inference-warm": "10k H100, Inference, warm",
    "aws-global-aggregat": "AWS-Aggregat 500k",
}

WORKLOAD_LABEL = {"training": "Training", "inference": "Inference"}
PHASE_LABEL = {"decode": "Decode", "prefill": "Prefill"}
ARCH_LABEL = {"dense": "dicht", "moe": "MoE"}


def _de(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def spec_label(spec: DatacenterSpec) -> str:
    phase = (
        f" ({PHASE_LABEL[spec.inference_phase]})" if spec.workload == "inference" else ""
    )
    moe = (
        f" {_de(spec.moe_anteil_pct)} %" if spec.arch == "moe" else ""
    )
    return (
        f"{spec.n_gpus:,}".replace(",", ".")
        + f" × {GPU_LABEL[spec.gpu_type]}, {WORKLOAD_LABEL[spec.workload]}{phase}, "
        f"{MODEL_LABEL[spec.model_class]}, {ARCH_LABEL[spec.arch]}{moe}, "
        f"Batch {spec.batch_size}, "
        f"Belegung {spec.occupancy_pct:.0f} %, Last {spec.chip_load_pct:.0f} %, "
        f"{COOLING_LABEL[spec.cooling]}, PUE {_de(spec.pue)}, {CLIMATE_LABEL[spec.climate]}"
    )


def synthesize_rechenzentrum(spec: DatacenterSpec) -> pd.DataFrame:
    rng = np.random.default_rng(spec.seed)
    n = max(spec.days, 1) * 24
    zeit = pd.date_range("2026-01-01", periods=n, freq="h")
    stunde = np.arange(n) % 24
    wochentag = (np.arange(n) // 24) % 7
    is_weekend = wochentag >= 5

    if spec.workload == "training":
        amplitude, noise_std = 0.04, 0.02
    elif spec.inference_phase == "prefill":
        amplitude, noise_std = 0.10, 0.04
    else:
        amplitude, noise_std = 0.22, 0.07
    batch_smooth = float(
        np.clip(1.0 / np.sqrt(max(spec.batch_size, 1) / 16.0), 0.4, 2.0)
    )
    amplitude *= batch_smooth
    noise_std *= batch_smooth

    mean_occ = float(np.clip(spec.occupancy_pct / 100.0, 0.02, 1.0))
    chip = float(np.clip(spec.chip_load_pct / 100.0, 0.05, 1.0))
    daily = np.sin((stunde - 14) / 24 * 2 * np.pi)
    weekly = np.where(is_weekend, 0.85, 1.0)
    occupancy = np.clip(
        (mean_occ + amplitude * daily) * weekly + rng.normal(0, noise_std, n),
        0.02,
        1.0,
    )
    utilization = np.clip(occupancy * chip, 0.02, 1.0)

    gpu_util_pct = (utilization * 100).round(1)
    cpu_util_pct = np.clip(gpu_util_pct * 0.55 + rng.normal(0, 4, n), 0, 100).round(1)
    aktive_jobs = np.clip(
        (spec.n_gpus / 400) * occupancy + rng.normal(0, spec.n_gpus / 2000, n), 0, None
    ).round()

    tdp_kw = max(float(spec.tdp_w), 1.0) / 1000.0
    idle_kw = max(float(spec.idle_w), 0.0) / 1000.0
    idle_kw = min(idle_kw, tdp_kw)
    it_stromverbrauch_kw = (
        spec.n_gpus
        * (idle_kw + (tdp_kw - idle_kw) * utilization)
        * (1.0 + rng.normal(0, METER_NOISE_REL, n))
    ).round(1)

    base_temp = CLIMATE_BASE_TEMP_C[spec.climate]
    _, climate_k = COOLING_SPECS[spec.cooling]
    aussentemperatur_c = (
        base_temp + 6 * np.sin((stunde - 15) / 24 * 2 * np.pi) + rng.normal(0, 1.5, n)
    ).round(1)

    kuehlung_stromverbrauch_kw = np.clip(
        it_stromverbrauch_kw * (spec.pue - 1)
        + climate_k * it_stromverbrauch_kw * (aussentemperatur_c - base_temp)
        + rng.normal(0, it_stromverbrauch_kw.std() * 0.02 + 1e-6, n),
        0,
        None,
    ).round(1)
    gesamt_stromverbrauch_kw = (
        it_stromverbrauch_kw + kuehlung_stromverbrauch_kw
    ).round(1)

    return pd.DataFrame(
        {
            "zeitstempel": zeit.strftime("%Y-%m-%d %H:%M"),
            "stunde": stunde,
            "wochentag": wochentag,
            "aktive_jobs": aktive_jobs,
            "gpu_auslastung_pct": gpu_util_pct,
            "cpu_auslastung_pct": cpu_util_pct,
            "aussentemperatur_c": aussentemperatur_c,
            "it_stromverbrauch_kw": it_stromverbrauch_kw,
            "kuehlung_stromverbrauch_kw": kuehlung_stromverbrauch_kw,
            "gesamt_stromverbrauch_kw": gesamt_stromverbrauch_kw,
        }
    )
