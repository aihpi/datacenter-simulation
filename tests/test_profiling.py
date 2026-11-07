"""Profiling: type inference and dropping id-like / constant columns."""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.profiling import analyzable_columns, profile_dataframe


def _frame() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n = 200
    return pd.DataFrame(
        {
            "record_id": np.arange(n),  # id-like
            "study_version": ["v1"] * n,  # constant
            "score": rng.normal(50, 10, n),  # numeric
            "category": rng.choice(["a", "b", "c"], n),  # categorical
            "flag": rng.choice(["yes", "no"], n),  # categorical (2-level)
            "when": pd.date_range("2020-01-01", periods=n, freq="D"),  # datetime
        }
    )


def test_kinds_inferred():
    p = profile_dataframe(_frame())
    assert p["record_id"].kind == "id_like"
    assert p["study_version"].kind == "constant"
    assert p["score"].kind == "numeric"
    assert p["category"].kind == "categorical"
    assert p["flag"].kind == "categorical"
    assert p["when"].kind == "datetime"


def test_analyzable_drops_id_constant_datetime():
    p = profile_dataframe(_frame())
    cols = analyzable_columns(p)
    assert "record_id" not in cols
    assert "study_version" not in cols
    assert "when" not in cols
    assert set(cols) == {"score", "category", "flag"}


def test_low_cardinality_integer_is_categorical():
    df = pd.DataFrame({"rating": [1, 2, 3, 1, 2, 3, 1, 2, 3, 2] * 10})
    p = profile_dataframe(df)
    assert p["rating"].kind == "categorical"


def test_column_info_roundtrip():
    p = profile_dataframe(_frame())
    ci = p["score"].to_column_info()
    assert ci.name == "score"
    assert ci.dtype == "numeric"
    assert ci.n_unique is not None and ci.n_unique > 0


def test_named_id_column_dropped_even_if_lower_cardinality():
    df = pd.DataFrame({"user_id": [f"u{i % 50}" for i in range(50)], "v": range(50)})
    p = profile_dataframe(df)
    assert p["user_id"].kind == "id_like"
