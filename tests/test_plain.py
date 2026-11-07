"""Unit tests for the everyday-language readout (engine.plain)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.plain import (
    build_plain,
    direction,
    explained_pct,
    slope,
    strength_label,
)


@pytest.mark.parametrize(
    "coef, expected",
    [
        (0.0, "sehr schwach"),
        (0.05, "sehr schwach"),
        (0.2, "schwach"),
        (0.4, "mittelstark"),
        (0.6, "stark"),
        (0.9, "sehr stark"),
        (-0.9, "sehr stark"),  # sign-independent
        (1.0, "sehr stark"),
    ],
)
def test_strength_label_bands(coef, expected):
    assert strength_label(coef) == expected


def test_direction_signed_vs_unsigned():
    assert direction("pearson", 0.5) == "positiv"
    assert direction("pearson", -0.5) == "negativ"
    assert direction("spearman", -0.1) == "negativ"
    assert direction("point_biserial", 0.3) == "positiv"
    assert direction("pearson", 0.0) == "keine"
    # unsigned measures have no meaningful direction
    assert direction("cramers_v", 0.5) == "keine"
    assert direction("correlation_ratio", 0.66) == "keine"


def test_explained_pct():
    assert explained_pct("pearson", 0.9) == 81
    assert explained_pct("correlation_ratio", 0.66) == 44  # 0.4356 -> 44
    assert explained_pct("point_biserial", -0.5) == 25
    # Cramer's V**2 is not a variance-explained fraction
    assert explained_pct("cramers_v", 0.8) is None


def test_slope_recovers_linear_relationship():
    x = pd.Series(np.arange(0.0, 50.0))
    y = 3.0 * x + 5.0
    assert slope(x, y) == pytest.approx(3.0, abs=1e-9)


def test_slope_guards():
    assert slope(pd.Series([1.0, 2.0]), pd.Series([1.0, 2.0])) is None  # n < 3
    const_x = pd.Series([2.0, 2.0, 2.0, 2.0])
    assert slope(const_x, pd.Series([1.0, 2.0, 3.0, 4.0])) is None  # no x variance


def test_build_plain_positive_numeric_with_rule_of_thumb():
    x = pd.Series(np.arange(0.0, 100.0))
    y = 4.0 * x + 10.0
    res = build_plain("pearson", 0.95, True, "lernzeit", "note", x, y)

    assert res.direction == "positiv"
    assert res.strength_label == "sehr stark"
    assert res.strength_pct == 95
    assert res.explained_pct == 90  # 0.95**2 = 0.9025 -> 90
    assert res.rule_of_thumb is not None
    assert res.rule_of_thumb.startswith("Pro +1 lernzeit: +4")
    assert "Je mehr lernzeit, desto mehr note." in res.summary
    assert "Zufallsbefund ist sehr unwahrscheinlich" in res.summary
    # the explained share lives in its own bar, not in the sentence
    assert "%" not in res.summary
    assert "Schwankung" not in res.summary


def test_build_plain_negative_direction_wording():
    res = build_plain("pearson", -0.6, True, "sport", "ruhepuls")
    assert res.direction == "negativ"
    assert "Je mehr sport, desto weniger ruhepuls." in res.summary
    # no series passed -> no rule of thumb even for a numeric method
    assert res.rule_of_thumb is None


def test_build_plain_unsigned_method_has_no_direction_or_slope():
    res = build_plain("cramers_v", 0.7, True, "region", "partei")
    assert res.direction == "keine"
    assert res.explained_pct is None
    assert res.rule_of_thumb is None
    assert "region und partei hängen zusammen." in res.summary


def test_build_plain_not_significant_chance_text():
    res = build_plain("pearson", 0.18, False, "a", "b")
    assert "könnte allerdings auch Zufall sein" in res.chance_text
    assert res.chance_text in res.summary


def test_build_plain_correlation_ratio_unsigned_but_explains():
    # eta is unsigned but eta**2 IS a variance-explained share
    res = build_plain("correlation_ratio", 0.66, True, "diaet", "cholesterin")
    assert res.direction == "keine"
    assert res.explained_pct == 44
    assert res.rule_of_thumb is None  # not an ordinary numeric-vs-numeric trend
