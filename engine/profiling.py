"""Column type profiling. Infers numeric / categorical / datetime / id_like /
constant, and decides which columns are analyzable (drops id-like + constant +
datetime)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from pandas.api import types as ptypes

from engine.config import ID_UNIQUE_FRACTION, MAX_CATEGORICAL_CARDINALITY
from engine.llm.base import ColumnInfo

ColumnKind = str  # "numeric" | "categorical" | "datetime" | "id_like" | "constant"


@dataclass
class Profile:
    name: str
    kind: ColumnKind
    n_nonnull: int
    n_unique: int
    units: str | None = None
    sample_values: list[str] = field(default_factory=list)

    @property
    def analyzable(self) -> bool:
        return self.kind in ("numeric", "categorical")

    def to_column_info(self) -> ColumnInfo:
        return ColumnInfo(
            name=self.name,
            dtype=self.kind,  # type: ignore[arg-type]
            units=self.units,
            sample_values=self.sample_values,
            n_unique=self.n_unique,
        )


_UNIT_HINTS = {
    "temperature": "deg C",
    "minutes": "min",
    "rate": "bpm",
    "score": "points",
    "sales": "units",
    "expectancy": "years",
    "cholesterol": "mg/dL",
    "hours": "hours",
}


def _guess_units(name: str) -> str | None:
    low = name.lower()
    for key, unit in _UNIT_HINTS.items():
        if key in low:
            return unit
    return None


def _looks_like_id(name: str) -> bool:
    low = name.lower()
    return low == "id" or low.endswith("_id") or low.endswith("id")


def _is_surrogate_sequence(nonnull: pd.Series) -> bool:
    """True if the distinct integer values form a contiguous run (e.g. 0..N-1) --
    the signature of a surrogate key. A genuine all-distinct integer measurement
    (sparse / non-contiguous values) returns False and is kept as numeric."""
    try:
        ints = np.asarray(pd.unique(nonnull), dtype="int64")
    except (ValueError, TypeError, OverflowError):
        return False
    if ints.size == 0:
        return False
    return int(ints.max() - ints.min()) == ints.size - 1


def profile_column(series: pd.Series) -> Profile:
    name = str(series.name)
    nonnull = series.dropna()
    n_nonnull = int(nonnull.shape[0])
    n_unique = int(nonnull.nunique())
    sample = [str(v) for v in pd.unique(nonnull)[:5]]
    units = _guess_units(name)

    # Constant (incl. all-null) -> drop.
    if n_unique <= 1:
        return Profile(name, "constant", n_nonnull, n_unique, units, sample)

    # Datetime -> profiled but not analyzed by the correlation measures here.
    if ptypes.is_datetime64_any_dtype(series):
        return Profile(name, "datetime", n_nonnull, n_unique, units, sample)

    if ptypes.is_numeric_dtype(series) and not ptypes.is_bool_dtype(series):
        unique_frac = n_unique / max(n_nonnull, 1)
        is_int_like = ptypes.is_integer_dtype(series) or (
            (nonnull == nonnull.round()).all()
        )
        # Integer identifier: an id-like NAME, or a (near-)unique contiguous
        # surrogate sequence. A high-cardinality but non-sequential integer
        # measurement is NOT treated as an id -- it stays numeric.
        if is_int_like and (unique_frac >= ID_UNIQUE_FRACTION or _looks_like_id(name)):
            if _looks_like_id(name) or _is_surrogate_sequence(nonnull):
                return Profile(name, "id_like", n_nonnull, n_unique, units, sample)
        # Integer-coded low-cardinality -> treat as categorical.
        if is_int_like and n_unique <= MAX_CATEGORICAL_CARDINALITY:
            return Profile(name, "categorical", n_nonnull, n_unique, units, sample)
        return Profile(name, "numeric", n_nonnull, n_unique, units, sample)

    # Object / string / categorical / bool.
    unique_frac = n_unique / max(n_nonnull, 1)
    # High-cardinality strings are not meaningful categoricals: surrogate keys,
    # dates-as-text, free-text notes, names. Drop them like ids so they don't
    # pollute the pairwise scan (and trigger degenerate group-of-one stats).
    if unique_frac >= ID_UNIQUE_FRACTION or n_unique > MAX_CATEGORICAL_CARDINALITY:
        return Profile(name, "id_like", n_nonnull, n_unique, units, sample)
    return Profile(name, "categorical", n_nonnull, n_unique, units, sample)


def profile_dataframe(df: pd.DataFrame) -> dict[str, Profile]:
    return {str(col): profile_column(df[col]) for col in df.columns}


def analyzable_columns(profiles: dict[str, Profile]) -> list[str]:
    """Return analyzable column names in their original order."""
    return [name for name, p in profiles.items() if p.analyzable]
