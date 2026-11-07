"""Verify a proposed confounder against the data via partial correlation.

Given X, Y and a candidate confounder Z (a column), compute the partial
correlation of X-Y controlling for Z. If the X-Y association collapses below the
configured threshold, the data CONFIRMS that Z explains the correlation.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pingouin as pg

from engine.config import PARTIAL_COLLAPSE_ABS, PARTIAL_COLLAPSE_RATIO
from engine.correlation import pearson
from engine.profiling import Profile


@dataclass
class PartialCorrResult:
    confounder: str
    method: str
    r_before: float
    r_after: float
    p_after: float
    n: int
    threshold_abs: float
    collapsed: bool
    note: str


def can_verify(x: str, y: str, z: str, profiles: dict[str, Profile]) -> bool:
    """Verification needs X, Y, Z all present and numeric for partial Pearson."""
    for c in (x, y, z):
        if c not in profiles or profiles[c].kind != "numeric":
            return False
    return True


def verify_confounder(
    df: pd.DataFrame,
    x: str,
    y: str,
    z: str,
    abs_threshold: float = PARTIAL_COLLAPSE_ABS,
    ratio_threshold: float = PARTIAL_COLLAPSE_RATIO,
) -> PartialCorrResult:
    """Partial correlation of X-Y controlling for Z. Assumes can_verify() is True."""
    r_before, _, _ = pearson(df[x], df[y])

    sub = df[[x, y, z]].dropna()
    res = pg.partial_corr(data=sub, x=x, y=y, covar=z)
    r_after = float(res["r"].iloc[0])
    # pingouin 0.6.x names the column "p_val".
    p_col = "p_val" if "p_val" in res.columns else ("p-val" if "p-val" in res.columns else res.columns[-1])
    p_after = float(res[p_col].iloc[0])
    n = int(res["n"].iloc[0]) if "n" in res.columns else int(len(sub))

    collapsed_abs = abs(r_after) < abs_threshold
    collapsed_ratio = abs(r_before) > 1e-9 and abs(r_after) < ratio_threshold * abs(r_before)
    collapsed = bool(collapsed_abs or collapsed_ratio)

    if collapsed:
        note = (
            f"Controlling for '{z}' collapses the association "
            f"({r_before:+.3f} -> {r_after:+.3f}): the data confirms the confounder."
        )
    else:
        note = (
            f"Controlling for '{z}' leaves the association largely intact "
            f"({r_before:+.3f} -> {r_after:+.3f}): the data does not confirm '{z}' "
            f"as the sole explanation."
        )

    return PartialCorrResult(
        confounder=z,
        method="partial_pearson",
        r_before=round(r_before, 6),
        r_after=round(r_after, 6),
        p_after=p_after,
        n=n,
        threshold_abs=abs_threshold,
        collapsed=collapsed,
        note=note,
    )
