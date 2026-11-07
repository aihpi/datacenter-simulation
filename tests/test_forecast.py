"""Tests for the OLS forecast engine (engine/forecast.py)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.forecast import fit_forecast, select_features


def _linear_df(n: int = 200, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(0, 1, n)
    # Exact linear target: y = 2*x1 + 3*x2 (+ tiny noise so lstsq is well-posed).
    y = 2.0 * x1 + 3.0 * x2 + rng.normal(0, 1e-6, n)
    return pd.DataFrame({"x1": x1, "x2": x2, "y": y})


def test_recovers_known_linear_coefficients():
    res = fit_forecast(_linear_df(), "y")
    assert res.r2 > 0.999
    coef = {w.name: w.coefficient for w in res.weights}
    assert coef["x1"] == pytest.approx(2.0, abs=1e-2)
    assert coef["x2"] == pytest.approx(3.0, abs=1e-2)


def test_weights_sorted_by_importance():
    res = fit_forecast(_linear_df(), "y")
    imps = [w.std_importance for w in res.weights]
    assert imps == sorted(imps, reverse=True)
    # x2 has the larger slope AND is standardized -> ranks first.
    assert res.weights[0].name == "x2"


def test_time_ordered_split_no_shuffle():
    """The hold-out must be the LAST rows, not a random sample."""
    df = _linear_df(n=100)
    res = fit_forecast(df, "y", test_fraction=0.2)
    assert res.n_test == 20
    assert res.n_train == 80
    # First series point corresponds to row 80 (start of the hold-out).
    assert res.series[0].index == 80
    assert res.series[-1].index == 99


def test_series_actuals_match_source_rows():
    df = _linear_df(n=100)
    res = fit_forecast(df, "y", test_fraction=0.1)
    # Actuals in the series are the untouched target values of the last rows.
    tail = df["y"].to_numpy()[-res.n_test :]
    got = [p.actual for p in res.series]
    assert np.allclose(got, tail, atol=1e-3)


def test_labels_from_label_column():
    df = _linear_df(n=50)
    df["ts"] = [f"t{i}" for i in range(50)]
    res = fit_forecast(df, "y", feature_cols=["x1", "x2"], label_col="ts")
    assert res.series[0].label == f"t{res.n_train}"


def test_select_features_excludes_target_and_non_numeric():
    df = _linear_df(n=20)
    df["name"] = ["a"] * 20
    feats = select_features(df, "y")
    assert feats == ["x1", "x2"]  # "name" (object) and "y" (target) excluded


def test_rejects_missing_target():
    with pytest.raises(ValueError, match="not found"):
        fit_forecast(_linear_df(), "nope")


def test_rejects_non_numeric_target():
    df = _linear_df(n=20)
    df["label"] = ["x"] * 20
    with pytest.raises(ValueError, match="not numeric"):
        fit_forecast(df, "label")


def test_rejects_too_few_rows():
    with pytest.raises(ValueError, match="complete rows"):
        fit_forecast(_linear_df(n=5), "y")


def test_datacenter_dataset_predicts_well():
    """On the seeded datacenter load series the model should be strong and
    correctly downweight the outside temperature (which does not drive IT power)."""
    df = pd.read_csv("data/rechenzentrum_load.csv")
    res = fit_forecast(df, "it_stromverbrauch_kw", label_col="zeitstempel")
    assert res.r2 > 0.9
    assert res.mae < res.baseline_mae  # beats the mean-predicting baseline
    imp = {w.name: w.std_importance for w in res.weights}
    # GPU utilisation dominates; outside temperature is near-irrelevant.
    assert imp["gpu_auslastung_pct"] == max(imp.values())
    assert imp["aussentemperatur_c"] < 0.1
