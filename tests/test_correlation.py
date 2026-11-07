"""Correlation measures, dispatch, and Benjamini-Hochberg FDR correction."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.correlation import (
    associate,
    benjamini_hochberg,
    compute_correlations,
    correlation_ratio,
    cramers_v,
    point_biserial,
    pearson,
    rank_survivors,
    spearman,
)
from engine.profiling import profile_dataframe


@pytest.fixture
def rng():
    return np.random.default_rng(123)


def test_pearson_detects_linear(rng):
    x = pd.Series(rng.normal(0, 1, 500))
    y = 3 * x + pd.Series(rng.normal(0, 0.5, 500))
    r, p, n = pearson(x, y)
    assert r > 0.9 and p < 1e-10 and n == 500


def test_spearman_detects_monotone_nonlinear(rng):
    x = pd.Series(np.linspace(0, 5, 400))
    y = pd.Series(np.exp(x.to_numpy()) + rng.normal(0, 0.01, 400))
    sr, sp, _ = spearman(x, y)
    assert sr > 0.99 and sp < 1e-10


def test_point_biserial_signed(rng):
    cat = pd.Series(rng.choice(["lo", "hi"], 400))
    num = pd.Series(
        np.where(cat == "hi", 1.0, 0.0) * 5 + rng.normal(0, 1, 400)
    )
    r, p, n = point_biserial(cat, num)
    # sign depends on sorted level coding; magnitude is what matters
    assert abs(r) > 0.5 and p < 1e-10 and n == 400


def test_correlation_ratio_multi_level(rng):
    cat = pd.Series(rng.choice(["a", "b", "c"], 600))
    base = {"a": 0.0, "b": 5.0, "c": 10.0}
    num = pd.Series([base[c] for c in cat]) + pd.Series(rng.normal(0, 1, 600))
    eta, p, n = correlation_ratio(cat, num)
    assert 0.8 < eta <= 1.0 and p < 1e-10 and n == 600


def test_cramers_v_association(rng):
    a = pd.Series(rng.choice(["x", "y"], 600))
    # b strongly depends on a
    b = pd.Series(
        np.where(rng.random(600) < np.where(a == "x", 0.85, 0.15), "p", "q")
    )
    v, p, n = cramers_v(a, b)
    assert v > 0.5 and p < 1e-10 and n == 600


def test_cramers_v_independent_is_small(rng):
    a = pd.Series(rng.choice(["x", "y"], 600))
    b = pd.Series(rng.choice(["p", "q"], 600))
    v, p, _ = cramers_v(a, b)
    assert v < 0.2


def test_benjamini_hochberg_known_values():
    # Classic worked example.
    pvals = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216]
    q = benjamini_hochberg(pvals)
    assert len(q) == len(pvals)
    # monotonic non-decreasing in p-order
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    sorted_q = [q[i] for i in order]
    assert all(a <= b + 1e-12 for a, b in zip(sorted_q, sorted_q[1:]))
    # smallest adjusted = 0.001 * 10 / 1 = 0.01
    assert abs(q[0] - 0.01) < 1e-9
    # all adjusted >= raw
    assert all(q[i] >= pvals[i] - 1e-12 for i in range(len(pvals)))


def test_benjamini_hochberg_clips_to_one():
    assert benjamini_hochberg([0.9, 0.95]) == [0.95, 0.95]
    assert all(v <= 1.0 for v in benjamini_hochberg([0.5, 0.6, 0.99]))


def test_benjamini_hochberg_empty():
    assert benjamini_hochberg([]) == []


def test_dispatch_methods_by_type_pair():
    rng = np.random.default_rng(7)
    n = 400
    df = pd.DataFrame(
        {
            "num1": rng.normal(0, 1, n),
            "num2": rng.normal(0, 1, n),
            "cat2": rng.choice(["yes", "no"], n),
            "cat3": rng.choice(["a", "b", "c"], n),
        }
    )
    df["num2"] = 2 * df["num1"] + rng.normal(0, 0.3, n)
    prof = profile_dataframe(df)
    assert associate(df, "num1", "num2", prof).method in ("pearson", "spearman")
    assert associate(df, "cat2", "cat3", prof).method == "cramers_v"
    assert associate(df, "cat2", "num1", prof).method == "point_biserial"
    assert associate(df, "cat3", "num1", prof).method == "correlation_ratio"


def test_compute_correlations_fdr_and_rank():
    rng = np.random.default_rng(99)
    n = 500
    df = pd.DataFrame({f"r{i}": rng.normal(0, 1, n) for i in range(6)})
    df["real_x"] = rng.normal(0, 1, n)
    df["real_y"] = 4 * df["real_x"] + rng.normal(0, 0.5, n)
    prof = profile_dataframe(df)
    pairs = compute_correlations(df, prof)
    # every pair has an adjusted p in [0,1]
    assert all(0.0 <= p.stat.p_adjusted <= 1.0 for p in pairs)
    survivors = rank_survivors(pairs)
    # the strong planted pair must survive and rank at the top
    top = survivors[0]
    assert {top.x, top.y} == {"real_x", "real_y"}
    # ranked by effect size, descending
    effects = [s.stat.effect_size for s in survivors]
    assert effects == sorted(effects, reverse=True)
