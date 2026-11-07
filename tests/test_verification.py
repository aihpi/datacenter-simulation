"""Gate 4: partial-correlation verification numerics.

For every ground-truth case with confounder_in_data == true, controlling for the
named confounder Z must drop the X-Y association below the configured threshold.
Also checks that an absent/irrelevant control does NOT collapse a true link.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine.config import PARTIAL_COLLAPSE_ABS
from engine.profiling import profile_dataframe
from engine.verification import can_verify, verify_confounder

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def synthetic() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "synthetic.csv")


@pytest.fixture(scope="module")
def ground_truth() -> list[dict]:
    return json.loads((ROOT / "data" / "ground_truth.json").read_text())


def test_confounder_in_data_cases_collapse(synthetic, ground_truth):
    profiles = profile_dataframe(synthetic)
    cases = [e for e in ground_truth if e["confounder_in_data"]]
    assert cases, "expected at least one confounder_in_data case"
    for e in cases:
        x, y, z = e["x"], e["y"], e["confounder"]
        assert can_verify(x, y, z, profiles), f"cannot verify {x},{y}|{z}"
        res = verify_confounder(synthetic, x, y, z)
        assert abs(res.r_before) > 0.5, f"{x}~{y} should start strongly correlated"
        assert abs(res.r_after) < PARTIAL_COLLAPSE_ABS, (
            f"controlling for {z}: |r_after|={abs(res.r_after):.3f} "
            f">= {PARTIAL_COLLAPSE_ABS}"
        )
        assert res.collapsed is True


def test_irrelevant_control_does_not_collapse_true_causal(synthetic):
    # hours_studied -> exam_score is a genuine link; controlling for an unrelated
    # noise column must NOT make it collapse.
    res = verify_confounder(synthetic, "hours_studied", "exam_score", "rand_a")
    assert abs(res.r_after) > 0.5
    assert res.collapsed is False


def test_can_verify_requires_numeric():
    df = pd.DataFrame(
        {
            "a": np.arange(50, dtype=float),
            "b": np.arange(50, dtype=float) * 2,
            "c": ["x", "y"] * 25,  # categorical -> not verifiable as a covariate
        }
    )
    profiles = profile_dataframe(df)
    assert can_verify("a", "b", "c", profiles) is False
    assert can_verify("a", "b", "missing", profiles) is False
