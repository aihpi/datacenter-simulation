"""Pairwise association measures with the right statistic per type pair, plus
Benjamini-Hochberg FDR correction across all tested pairs.

Measure selection:
  numeric  x numeric      -> Pearson and Spearman (the stronger |coef| is reported)
  categorical x categorical -> Cramer's V (chi-square)
  binary-categorical x numeric -> point-biserial (signed)
  multi-categorical x numeric  -> correlation ratio (eta, one-way ANOVA)
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from engine.config import ALPHA, MIN_EFFECT_SIZE
from engine.llm.base import CorrelationStat
from engine.profiling import Profile, analyzable_columns

# ----------------------------------------------------------------------------
# Individual measures. Each returns (coefficient, p_value, n). Each is unit-tested.
# ----------------------------------------------------------------------------


def _has_no_variance(*series: pd.Series) -> bool:
    """True if any input is empty or constant (correlation undefined)."""
    return any(s.nunique() < 2 for s in series)


def pearson(x: pd.Series, y: pd.Series) -> tuple[float, float, int]:
    s = pd.concat([x, y], axis=1).dropna()
    n = len(s)
    # n<3 or a constant column => correlation is undefined; report no effect.
    if n < 3 or _has_no_variance(s.iloc[:, 0], s.iloc[:, 1]):
        return 0.0, 1.0, n
    r, p = stats.pearsonr(s.iloc[:, 0], s.iloc[:, 1])
    return float(r), float(p), n


def spearman(x: pd.Series, y: pd.Series) -> tuple[float, float, int]:
    s = pd.concat([x, y], axis=1).dropna()
    n = len(s)
    if n < 3 or _has_no_variance(s.iloc[:, 0], s.iloc[:, 1]):
        return 0.0, 1.0, n
    r, p = stats.spearmanr(s.iloc[:, 0], s.iloc[:, 1])
    return float(r), float(p), n


def point_biserial(cat: pd.Series, num: pd.Series) -> tuple[float, float, int]:
    """cat has exactly 2 levels; coded 0/1 by sorted level order (signed)."""
    s = pd.concat([cat, num], axis=1).dropna()
    s.columns = ["cat", "num"]
    n = len(s)
    levels = sorted(s["cat"].astype(str).unique())
    if n < 3 or len(levels) != 2 or _has_no_variance(s["num"]):
        return 0.0, 1.0, n
    coding = {levels[0]: 0, levels[1]: 1}
    binary = s["cat"].astype(str).map(coding).to_numpy(dtype=float)
    r, p = stats.pointbiserialr(binary, s["num"].to_numpy(dtype=float))
    return float(r), float(p), n


def correlation_ratio(cat: pd.Series, num: pd.Series) -> tuple[float, float, int]:
    """eta = sqrt(SS_between / SS_total); p from one-way ANOVA F-test."""
    s = pd.concat([cat, num], axis=1).dropna()
    s.columns = ["cat", "num"]
    n = len(s)
    groups = [g["num"].to_numpy(dtype=float) for _, g in s.groupby("cat")]
    groups = [g for g in groups if len(g) > 0]
    if n < 3 or len(groups) < 2:
        return 0.0, 1.0, n
    grand = s["num"].mean()
    ss_total = float(((s["num"] - grand) ** 2).sum())
    ss_between = float(sum(len(g) * (g.mean() - grand) ** 2 for g in groups))
    eta = float(np.sqrt(ss_between / ss_total)) if ss_total > 0 else 0.0
    try:
        _, p = stats.f_oneway(*groups)
        p = float(p)
        if np.isnan(p):
            p = 1.0
    except Exception:
        p = 1.0
    return eta, p, n


def cramers_v(a: pd.Series, b: pd.Series) -> tuple[float, float, int]:
    """Bias-uncorrected Cramer's V from a contingency table; p from chi-square."""
    s = pd.concat([a, b], axis=1).dropna()
    n = len(s)
    if n < 3:
        return 0.0, 1.0, n
    table = pd.crosstab(s.iloc[:, 0], s.iloc[:, 1])
    if table.shape[0] < 2 or table.shape[1] < 2:
        return 0.0, 1.0, n
    chi2, p, _, _ = stats.chi2_contingency(table)
    k = min(table.shape)
    v = float(np.sqrt(chi2 / (n * (k - 1)))) if n * (k - 1) > 0 else 0.0
    return min(v, 1.0), float(p), n


# ----------------------------------------------------------------------------
# Benjamini-Hochberg FDR correction.
# ----------------------------------------------------------------------------


def benjamini_hochberg(pvals: list[float]) -> list[float]:
    """Return BH-adjusted p-values (q-values), order-preserving, clipped to 1.0.

    Non-finite inputs (NaN/inf) are treated as p=1.0 so a single undefined test
    cannot reorder or falsely "significant"-ify the other pairs.
    """
    m = len(pvals)
    if m == 0:
        return []
    clean = [
        min(max(float(p), 0.0), 1.0) if math.isfinite(p) else 1.0 for p in pvals
    ]
    order = sorted(range(m), key=lambda i: clean[i])
    adjusted = [0.0] * m
    prev = 1.0
    # Walk from largest p to smallest, enforcing monotonicity.
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        q = clean[i] * m / (rank + 1)
        prev = min(prev, q)
        adjusted[i] = min(prev, 1.0)
    return adjusted


# ----------------------------------------------------------------------------
# Pair dispatch + full-dataset correlation.
# ----------------------------------------------------------------------------


@dataclass
class PairAssociation:
    x: str
    y: str
    stat: CorrelationStat


def _pick_method(kx: str, ky: str) -> str:
    if kx == "numeric" and ky == "numeric":
        return "pearson_or_spearman"
    if kx == "categorical" and ky == "categorical":
        return "cramers_v"
    return "mixed"


def associate(
    df: pd.DataFrame, x: str, y: str, profiles: dict[str, Profile]
) -> CorrelationStat:
    """Compute the single best association statistic for one pair (no FDR yet)."""
    kx, ky = profiles[x].kind, profiles[y].kind
    kind = _pick_method(kx, ky)

    if kind == "pearson_or_spearman":
        pr, pp, pn = pearson(df[x], df[y])
        sr, sp, sn = spearman(df[x], df[y])
        if abs(sr) > abs(pr):
            method, coef, p, n = "spearman", sr, sp, sn
        else:
            method, coef, p, n = "pearson", pr, pp, pn
    elif kind == "cramers_v":
        coef, p, n = cramers_v(df[x], df[y])
        method = "cramers_v"
    else:  # mixed: orient as (categorical, numeric)
        if kx == "categorical":
            cat_col, num_col = x, y
        else:
            cat_col, num_col = y, x
        if profiles[cat_col].n_unique == 2:
            coef, p, n = point_biserial(df[cat_col], df[num_col])
            method = "point_biserial"
        else:
            coef, p, n = correlation_ratio(df[cat_col], df[num_col])
            method = "correlation_ratio"

    return CorrelationStat(
        method=method,  # type: ignore[arg-type]
        coefficient=round(coef, 6),
        effect_size=round(abs(coef), 6),
        p_value=p,
        p_adjusted=p,  # filled by compute_correlations after FDR
        n=n,
        significant=False,  # filled after FDR
    )


def compute_correlations(
    df: pd.DataFrame,
    profiles: dict[str, Profile],
    alpha: float = ALPHA,
) -> list[PairAssociation]:
    """Compute associations for every analyzable pair, then apply BH-FDR."""
    cols = analyzable_columns(profiles)
    pairs: list[PairAssociation] = []
    for x, y in itertools.combinations(cols, 2):
        pairs.append(PairAssociation(x=x, y=y, stat=associate(df, x, y, profiles)))

    qvals = benjamini_hochberg([p.stat.p_value for p in pairs])
    for pa, q in zip(pairs, qvals):
        pa.stat.p_adjusted = q
        pa.stat.significant = q < alpha
    return pairs


def rank_survivors(
    pairs: list[PairAssociation], min_effect: float = MIN_EFFECT_SIZE
) -> list[PairAssociation]:
    """Significant pairs with effect size >= min_effect, sorted by effect desc."""
    survivors = [
        p for p in pairs if p.stat.significant and p.stat.effect_size >= min_effect
    ]
    return sorted(survivors, key=lambda p: p.stat.effect_size, reverse=True)


def association_lookup(
    pairs: list[PairAssociation],
) -> dict[frozenset[str], CorrelationStat]:
    """Order-insensitive lookup from a column pair to its stat."""
    return {frozenset((p.x, p.y)): p.stat for p in pairs}
