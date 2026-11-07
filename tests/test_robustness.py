"""Regression tests for the adversarial-input defects found by the audit:
constant-on-overlap columns -> NaN p-values -> poisoned BH ordering, and the
id_like heuristic dropping genuine integer measurements."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from api.pipeline import analyze_dataframe
from api.schemas import AnalyzeResponse
from engine.correlation import (
    benjamini_hochberg,
    compute_correlations,
    pearson,
    point_biserial,
    spearman,
)
from engine.llm.mock import MockLLMClient
from engine.profiling import profile_dataframe


# --- constant-input guards (no NaN escapes the measures) ---

def test_constant_column_measures_return_no_effect():
    const = pd.Series([5.0] * 40)
    other = pd.Series(np.linspace(0, 1, 40))
    for fn in (pearson, spearman):
        r, p, n = fn(const, other)
        assert (r, p) == (0.0, 1.0) and n == 40
        assert math.isfinite(p)
    cat = pd.Series(["a", "b"] * 20)
    r, p, n = point_biserial(cat, const)  # constant numeric side
    assert (r, p) == (0.0, 1.0)


# --- BH is NaN-safe ---

def test_bh_sanitizes_nan_does_not_falsely_signify():
    # A NaN test must not flip an insignificant p (0.5) to significant.
    q = benjamini_hochberg([0.5, float("nan"), 0.001])
    assert all(math.isfinite(v) for v in q)
    assert q[0] > 0.05  # the 0.5 p-value stays non-significant
    # The smallest real p is still adjusted correctly (0.001 * 3 / 1).
    assert abs(q[2] - 0.003) < 1e-9


def test_bh_clamps_out_of_range_and_inf():
    q = benjamini_hochberg([float("inf"), -0.2, 1.5, 0.01])
    assert all(0.0 <= v <= 1.0 for v in q)


# --- end-to-end: a constant-on-overlap column cannot manufacture significance ---

def test_constant_overlap_does_not_create_false_positives():
    rng = np.random.default_rng(11)
    n = 120
    half = n // 2
    # `v` is constant exactly on the rows where `y` is observed: the per-pair
    # complete-case overlap (v, y) is constant -> would yield a NaN p-value.
    df = pd.DataFrame(
        {
            "a": rng.normal(0, 1, n),
            "b": rng.normal(0, 1, n),
            "v": np.r_[np.full(half, 3.0), rng.normal(0, 1, n - half)],
            "y": np.r_[rng.normal(0, 1, half), np.full(n - half, np.nan)],
        }
    )
    profiles = profile_dataframe(df)
    pairs = compute_correlations(df, profiles)
    by_pair = {frozenset((p.x, p.y)): p for p in pairs}
    # The constant-on-overlap pair yields a defined, non-significant result.
    vy = by_pair[frozenset(("v", "y"))]
    assert math.isfinite(vy.stat.p_value) and vy.stat.p_value == 1.0
    assert vy.stat.significant is False
    # No NaN/inf anywhere in the adjusted p-values.
    assert all(math.isfinite(p.stat.p_adjusted) for p in pairs)
    assert all(0.0 <= p.stat.p_adjusted <= 1.0 for p in pairs)
    # The independent noise pair must not be flagged significant.
    assert by_pair[frozenset(("a", "b"))].stat.significant is False


# --- profiling: genuine integer measurement is kept, surrogate key dropped ---

def test_non_contiguous_distinct_integers_stay_numeric():
    rng = np.random.default_rng(3)
    # all-distinct but sparse/non-sequential integer measurement
    vals = rng.choice(np.arange(0, 100_000), size=80, replace=False)
    df = pd.DataFrame({"sensor_reading": vals, "y": vals * 2 + rng.normal(0, 1, 80)})
    p = profile_dataframe(df)
    assert p["sensor_reading"].kind == "numeric"


def test_contiguous_surrogate_sequence_is_id_like():
    df = pd.DataFrame({"seq": np.arange(200), "y": np.random.default_rng(0).normal(0, 1, 200)})
    p = profile_dataframe(df)
    assert p["seq"].kind == "id_like"
    # a shuffled contiguous range is still a surrogate key
    shuffled = np.arange(200)
    np.random.default_rng(1).shuffle(shuffled)
    df2 = pd.DataFrame({"seq": shuffled, "y": np.arange(200.0)})
    assert profile_dataframe(df2)["seq"].kind == "id_like"


# --- observability: dropped columns are surfaced ---

def test_dropped_columns_reported():
    df = pd.DataFrame(
        {
            "record_id": np.arange(60),
            "const": ["v1"] * 60,
            "x": np.linspace(0, 1, 60),
            "y": np.linspace(0, 1, 60) + 0.01,
        }
    )
    resp = analyze_dataframe(df, "d", "inline", MockLLMClient())
    assert isinstance(resp, AnalyzeResponse)
    dropped = {d.name: d.reason for d in resp.dropped_columns}
    assert dropped.get("record_id") == "id_like"
    assert dropped.get("const") == "constant"
