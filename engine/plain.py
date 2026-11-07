"""Layperson-friendly readouts: turn a CorrelationStat into everyday German.

Pure, deterministic transforms of values the engine already computed. Two rules:

  * No new hypothesis test -- everything here is derived from the coefficient,
    the significance flag, and (for the rule of thumb) the raw columns.
  * No causal language. The verdict badge carries the causal claim; this module
    only describes the *association* in plain words ("gehen miteinander einher",
    never "verursacht").

The point is to translate the two hardest numbers on the card (r and p) into
words an everyday reader understands, not to add more jargon.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Methods whose coefficient is signed, so "je mehr X, desto ..." has a direction.
_SIGNED = {"pearson", "spearman", "point_biserial"}

# Methods where coefficient**2 is a meaningful "shared variation" share in [0, 1].
# Cramer's V is excluded on purpose: V**2 is not a variance-explained fraction.
_EXPLAINS = {"pearson", "spearman", "point_biserial", "correlation_ratio"}

# Methods that describe an ordinary number-vs-number trend, where a slope in the
# original units ("pro +1 X rund +b Y") is a faithful rule of thumb.
_NUMERIC = {"pearson", "spearman"}

# |coef| -> label. Labels are predicative ("Der Zusammenhang ist <label>") so no
# German adjective declension is needed. Thresholds follow the usual
# weak/medium/strong convention (0.1 / 0.3 / 0.5 / 0.7).
_BANDS: tuple[tuple[float, str], ...] = (
    (0.1, "sehr schwach"),
    (0.3, "schwach"),
    (0.5, "mittelstark"),
    (0.7, "stark"),
)


@dataclass
class PlainResult:
    """Everyday-language readout for one pair (see PlainStats in api.schemas)."""

    summary: str
    strength_label: str
    strength_pct: int
    direction: str  # "positiv" | "negativ" | "keine"
    explained_pct: int | None
    rule_of_thumb: str | None
    chance_text: str


def strength_label(coef: float) -> str:
    """Word for the magnitude of an association, ignoring its sign."""
    a = abs(coef)
    for hi, label in _BANDS:
        if a < hi:
            return label
    return "sehr stark"


def direction(method: str, coef: float) -> str:
    """'positiv' / 'negativ' for signed methods, else 'keine'."""
    if method not in _SIGNED or coef == 0:
        return "keine"
    return "positiv" if coef > 0 else "negativ"


def explained_pct(method: str, coef: float) -> int | None:
    """Shared variation as a percentage (coef**2), or None where it doesn't apply."""
    if method not in _EXPLAINS:
        return None
    return int(round(coef * coef * 100))


def _fmt_num(v: float) -> str:
    """Compact, human-readable magnitude: scale-aware precision, no trailing zeros."""
    a = abs(v)
    if a >= 100:
        return f"{v:.0f}"
    if a >= 10:
        digits = f"{v:.1f}"
    elif a >= 1:
        digits = f"{v:.2f}"
    else:
        digits = f"{v:.3f}"
    return digits.rstrip("0").rstrip(".")


def _fmt_signed(v: float) -> str:
    """Magnitude with an explicit leading +/- (for slopes)."""
    sign = "+" if v >= 0 else "-"
    return f"{sign}{_fmt_num(abs(v))}"


def slope(x: pd.Series, y: pd.Series) -> float | None:
    """Ordinary-least-squares slope of y on x in original units, or None if it
    can't be estimated (too few points or a constant x)."""
    s = pd.concat([x, y], axis=1).dropna()
    if len(s) < 3:
        return None
    xv = s.iloc[:, 0].to_numpy(dtype=float)
    yv = s.iloc[:, 1].to_numpy(dtype=float)
    if np.std(xv) == 0:
        return None
    try:
        with np.errstate(all="ignore"):
            b = float(np.polyfit(xv, yv, 1)[0])
    except (np.linalg.LinAlgError, ValueError):
        return None
    if not np.isfinite(b):
        return None
    return b


def build_plain(
    method: str,
    coef: float,
    significant: bool,
    x_name: str,
    y_name: str,
    x_series: pd.Series | None = None,
    y_series: pd.Series | None = None,
) -> PlainResult:
    """Assemble the everyday-language readout for one X-Y pair.

    Pass ``x_series``/``y_series`` only for numeric-vs-numeric pairs; they are
    used solely to estimate the rule-of-thumb slope.
    """
    strength = strength_label(coef)
    dir_ = direction(method, coef)
    expl = explained_pct(method, coef)
    strength_pct = int(round(min(abs(coef), 1.0) * 100))

    rule_of_thumb: str | None = None
    if method in _NUMERIC and x_series is not None and y_series is not None:
        b = slope(x_series, y_series)
        if b is not None and b != 0:
            rule_of_thumb = f"Pro +1 {x_name}: {_fmt_signed(b)} {y_name}"

    chance_text = (
        "Ein reiner Zufallsbefund ist sehr unwahrscheinlich."
        if significant
        else "Das könnte allerdings auch Zufall sein."
    )

    # Note: the explained share (expl) is intentionally NOT repeated in this
    # sentence -- the card renders it as its own "Erklärter Anteil" bar, so
    # stating it here too would be redundant.
    sentences = [f"Der Zusammenhang ist {strength}."]
    if dir_ == "positiv":
        sentences.append(f"Je mehr {x_name}, desto mehr {y_name}.")
    elif dir_ == "negativ":
        sentences.append(f"Je mehr {x_name}, desto weniger {y_name}.")
    else:
        sentences.append(f"{x_name} und {y_name} hängen zusammen.")
    sentences.append(chance_text)

    return PlainResult(
        summary=" ".join(sentences),
        strength_label=strength,
        strength_pct=strength_pct,
        direction=dir_,
        explained_pct=expl,
        rule_of_thumb=rule_of_thumb,
        chance_text=chance_text,
    )
