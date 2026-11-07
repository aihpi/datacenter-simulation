"""Multiple linear regression forecast (classical ordinary least squares).

Fits a numeric target (e.g. ``it_stromverbrauch_kw``) on the other numeric
columns with ``numpy.linalg.lstsq`` and evaluates it on a **time-ordered**
hold-out window — the last ``test_fraction`` of the rows, with no shuffling, so
it mimics forecasting the future from the past. Reports R², MAE and RMSE on the
hold-out, a mean-predicting baseline for comparison, and standardized
coefficients so feature influence is comparable across units.

Kept deliberately dependency-free (numpy only) and in the same "classical
statistics, then explain" spirit as the correlation engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engine.correlation import pearson, spearman

DEFAULT_TEST_FRACTION = 0.2
MIN_ROWS = 10
MAX_SERIES_POINTS = 400  # cap the actual-vs-predicted payload sent to the UI


@dataclass
class FeatureWeight:
    name: str
    coefficient: float  # raw OLS slope (target units per 1 unit of the feature)
    std_importance: float  # |beta * std(x) / std(y)|, comparable across features


@dataclass
class FeatureStat:
    """Per-feature info for explaining a prediction: slope + value range."""

    name: str
    coefficient: float  # target units per 1 unit of the feature
    mean: float
    min: float
    max: float


@dataclass
class FeatureCandidate:
    """A numeric column's correlation with the target, reported whether or not
    it's currently included — lets the UI offer every column as a toggle, not
    just the ones that pass the current threshold."""

    name: str
    correlation: float  # signed, stronger of Pearson/Spearman with the target
    effect_size: float  # abs(correlation)
    same_measure: bool = False


@dataclass
class ForecastPoint:
    index: int  # row position (0-based over the full valid set)
    actual: float
    predicted: float
    label: str | None = None  # e.g. the timestamp for this row
    # Feature values at this row (by name), so the UI can decompose the
    # prediction into per-feature contributions (coefficient * value).
    values: dict[str, float] | None = None


@dataclass
class ForecastResult:
    target: str
    features: list[str]
    method: str
    n_train: int
    n_test: int
    r2: float
    mae: float
    rmse: float
    baseline_mae: float  # MAE of always predicting the train mean
    intercept: float
    weights: list[FeatureWeight] = field(default_factory=list)
    series: list[ForecastPoint] = field(default_factory=list)
    feature_stats: list[FeatureStat] = field(default_factory=list)
    candidates: list[FeatureCandidate] = field(default_factory=list)
    min_correlation: float = 0.0


def select_features(df: pd.DataFrame, target: str) -> list[str]:
    """Every numeric column except the target, in column order."""
    numeric = df.select_dtypes(include="number").columns.tolist()
    return [c for c in numeric if c != target]


# Column-name fragments that mark a plausible forecast target (power draw), and
# ones that mark a calendar/index column that must never be picked as a target.
TARGET_HINTS = ("stromverbrauch", "verbrauch", "power", "energie", "_kw", "kwh")
NON_TARGET_HINTS = ("stunde", "hour", "wochentag", "weekday", "tag", "index")
TOTAL_HINTS = ("gesamt", "total", "facility")


def is_measure(name: str) -> bool:
    """True if the column name marks it as a power/energy meter reading."""
    return any(hint in name.lower() for hint in TARGET_HINTS)


def measure_siblings(target: str, candidates: list[str]) -> list[str]:
    """Columns metering the same quantity as the target instead of driving it.

    A datacenter's power meters form an accounting identity — total = IT +
    cooling, and cooling is itself IT × (PUE − 1). Regressing one meter on the
    others reproduces that identity (R² = 1, MAE = 0) instead of forecasting
    anything, and pushes the real drivers (utilisation, jobs, temperature) to a
    coefficient of zero. Such columns stay selectable but are never picked
    automatically.
    """
    if not is_measure(target):
        return []
    return [c for c in candidates if c != target and is_measure(c)]


def numeric_targets(df: pd.DataFrame) -> list[str]:
    """Numeric columns that make sense to forecast (calendar columns excluded)."""
    numeric = df.select_dtypes(include="number").columns.tolist()
    return [
        c for c in numeric if not any(h in c.lower() for h in NON_TARGET_HINTS)
    ] or numeric


def resolve_target(df: pd.DataFrame, requested: str | None) -> str:
    """Pick the column to forecast.

    Uses ``requested`` when the data actually has it as a numeric column;
    otherwise falls back to a name hint — the facility-wide meter first (total
    power including cooling, the figure a datacenter is actually billed for),
    then any power/consumption column — and, as a last resort, the last numeric
    column, so an uploaded CSV with different column names still yields a
    forecast instead of a hard error.
    """
    candidates = numeric_targets(df)
    if not candidates:
        raise ValueError("No numeric columns available to forecast.")
    if requested and requested in candidates:
        return requested
    for name in candidates:
        if is_measure(name) and any(hint in name.lower() for hint in TOTAL_HINTS):
            return name
    for name in candidates:
        if is_measure(name):
            return name
    return candidates[-1]


def candidate_correlations(
    df: pd.DataFrame, target: str, candidates: list[str] | None = None
) -> list[FeatureCandidate]:
    """Correlation of every numeric candidate with the target (stronger of
    Pearson/Spearman wins), regardless of whether it's currently selected."""
    if candidates is None:
        candidates = select_features(df, target)
    y = pd.to_numeric(df[target], errors="coerce")
    out = []
    for name in candidates:
        x = pd.to_numeric(df[name], errors="coerce")
        pr, _, _ = pearson(x, y)
        sr, _, _ = spearman(x, y)
        r = sr if abs(sr) > abs(pr) else pr
        out.append(FeatureCandidate(name=name, correlation=round(r, 4), effect_size=round(abs(r), 4)))
    return out


def fit_forecast(
    df: pd.DataFrame,
    target: str,
    feature_cols: list[str] | None = None,
    test_fraction: float = DEFAULT_TEST_FRACTION,
    label_col: str | None = None,
    min_correlation: float = 0.0,
) -> ForecastResult:
    """Fit an OLS forecast for ``target`` and score it on a time-ordered hold-out.

    ``feature_cols=None`` auto-selects: every numeric column whose correlation
    with the target (Pearson/Spearman) meets ``min_correlation``, minus the
    other meters of the target quantity (see ``measure_siblings``). Pass an
    explicit ``feature_cols`` to override both with a manual pick.
    """
    if target not in df.columns:
        raise ValueError(f"Target column not found: {target!r}")
    if not pd.api.types.is_numeric_dtype(df[target]):
        raise ValueError(f"Target column {target!r} is not numeric.")

    candidates = candidate_correlations(df, target)
    siblings = set(measure_siblings(target, [c.name for c in candidates]))
    for candidate in candidates:
        candidate.same_measure = candidate.name in siblings
    if feature_cols is None:
        feature_cols = [
            c.name
            for c in candidates
            if not c.same_measure and c.effect_size >= min_correlation
        ]
    feature_cols = [c for c in feature_cols if c != target]
    if not feature_cols:
        if not candidates:
            raise ValueError("No numeric feature columns available for regression.")
        if all(c.same_measure for c in candidates):
            raise ValueError(
                f"Only other meters of {target!r} are available as features; "
                "those reproduce an accounting identity instead of forecasting."
            )
        raise ValueError(
            "No numeric feature columns meet the correlation threshold "
            f"({min_correlation!r})."
        )

    if not 0.05 <= test_fraction <= 0.9:
        raise ValueError("test_fraction must be between 0.05 and 0.9.")

    # Coerce to numeric and keep only rows where target + all features are present.
    cols = feature_cols + [target]
    numeric = df[cols].apply(pd.to_numeric, errors="coerce")
    mask = numeric.notna().all(axis=1).to_numpy()
    if int(mask.sum()) < MIN_ROWS:
        raise ValueError(f"Need at least {MIN_ROWS} complete rows to fit a model.")

    X = numeric.loc[mask, feature_cols].to_numpy(dtype=float)
    y = numeric.loc[mask, target].to_numpy(dtype=float)
    labels: np.ndarray | None = None
    if label_col and label_col in df.columns:
        labels = df.loc[mask, label_col].astype(str).to_numpy()

    n = y.shape[0]
    n_test = max(1, int(round(n * test_fraction)))
    n_test = min(n_test, n - 2)  # always keep >= 2 training rows
    n_train = n - n_test

    X_train, X_test = X[:n_train], X[n_train:]
    y_train, y_test = y[:n_train], y[n_train:]

    # OLS with an intercept column: solve [1 | X] @ [b0; betas] ~= y.
    design = np.column_stack([np.ones(n_train), X_train])
    coef, *_ = np.linalg.lstsq(design, y_train, rcond=None)
    intercept = float(coef[0])
    betas = coef[1:]

    pred = intercept + X_test @ betas
    resid = y_test - pred
    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((y_test - y_test.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    mae = float(np.mean(np.abs(resid)))
    rmse = float(np.sqrt(np.mean(resid**2)))
    # Baseline: predict the training mean for every hold-out row.
    baseline_mae = float(np.mean(np.abs(y_test - y_train.mean())))

    # Standardized importance so |influence| is comparable across mixed units.
    y_std = float(y_train.std()) or 1.0
    x_std = X_train.std(axis=0)
    weights = [
        FeatureWeight(
            name=name,
            coefficient=float(b),
            std_importance=float(abs(b) * xs / y_std),
        )
        for name, b, xs in zip(feature_cols, betas, x_std)
    ]
    weights.sort(key=lambda w: w.std_importance, reverse=True)

    # Per-feature value range (over the whole valid set) for the explainers.
    x_all_mean = X.mean(axis=0)
    x_all_min = X.min(axis=0)
    x_all_max = X.max(axis=0)
    feature_stats = [
        FeatureStat(
            name=name,
            coefficient=float(b),
            mean=float(x_all_mean[k]),
            min=float(x_all_min[k]),
            max=float(x_all_max[k]),
        )
        for k, (name, b) in enumerate(zip(feature_cols, betas))
    ]

    series = _build_series(y_test, pred, n_train, n_test, labels, X_test, feature_cols)

    return ForecastResult(
        target=target,
        features=feature_cols,
        method="ols_linear",
        n_train=n_train,
        n_test=n_test,
        r2=r2,
        mae=mae,
        rmse=rmse,
        baseline_mae=baseline_mae,
        intercept=intercept,
        weights=weights,
        series=series,
        feature_stats=feature_stats,
        candidates=candidates,
        min_correlation=min_correlation,
    )


def _build_series(
    y_test: np.ndarray,
    pred: np.ndarray,
    n_train: int,
    n_test: int,
    labels: np.ndarray | None,
    x_test: np.ndarray,
    feature_cols: list[str],
) -> list[ForecastPoint]:
    """Actual-vs-predicted points over the hold-out window (downsampled if huge)."""
    step = max(1, n_test // MAX_SERIES_POINTS)
    points: list[ForecastPoint] = []
    for i in range(0, n_test, step):
        row = n_train + i
        label = str(labels[row]) if labels is not None else None
        values = {
            name: round(float(x_test[i, k]), 4)
            for k, name in enumerate(feature_cols)
        }
        points.append(
            ForecastPoint(
                index=row,
                actual=round(float(y_test[i]), 4),
                predicted=round(float(pred[i]), 4),
                label=label,
                values=values,
            )
        )
    return points
