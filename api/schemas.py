"""API response schemas. Locked integration surface for the frontend.

The /analyze endpoint returns an AnalyzeResponse whose `pairs` is a list of
AnalysisPair. Each AnalysisPair embeds the LLM `Verdict` plus the statistics,
the (optional) partial-correlation verification, and lightweight plotting data.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from engine.llm.base import CorrelationStat, Verdict


class VerificationResult(BaseModel):
    """Outcome of controlling for a proposed confounder Z via partial correlation."""

    confounder: str
    method: str  # e.g. "partial_pearson"
    r_before: float  # original X-Y coefficient
    r_after: float  # partial X-Y coefficient controlling for Z
    p_after: float
    n: int
    threshold_abs: float
    collapsed: bool  # True => the data CONFIRMS the confounder explains X-Y
    note: str


class PlotPoint(BaseModel):
    x: float
    y: float


class BarGroup(BaseModel):
    category: str
    value: float  # mean of the numeric variable (mixed) or count (cat/cat)
    n: int


class PlotData(BaseModel):
    """Minimal data for the frontend mini-chart."""

    kind: Literal["scatter", "grouped_bar"]
    x_label: str
    y_label: str
    points: list[PlotPoint] = Field(default_factory=list)
    bars: list[BarGroup] = Field(default_factory=list)
    value_label: str | None = None  # e.g. "mean exam_score" or "count"


class PlainStats(BaseModel):
    """Everyday-language readout derived from CorrelationStat (engine.plain).

    Translates the coefficient and significance flag into plain German for lay
    readers. Carries no causal claim -- the verdict badge does that.
    """

    summary: str  # one-line Klartext: strength + direction + explained% + chance
    strength_label: str  # "sehr schwach"/"schwach"/"mittelstark"/"stark"/"sehr stark"
    strength_pct: int  # round(|coefficient| * 100), for the strength bar fill
    direction: Literal["positiv", "negativ", "keine"]
    explained_pct: int | None = None  # round(coefficient**2 * 100); None for V
    rule_of_thumb: str | None = None  # "Pro +1 X: +b Y"; numeric-vs-numeric only
    chance_text: str  # significance reframed in words


class AnalysisPair(BaseModel):
    """One row of the analysis: the stat, the LLM verdict, verification, and plot."""

    x: str
    y: str
    stat: CorrelationStat
    verdict: Verdict
    verification: VerificationResult | None = None
    plot: PlotData
    # Everyday-language readout. Optional so older payloads remain valid; the
    # pipeline always populates it.
    plain: PlainStats | None = None


class DroppedColumn(BaseModel):
    name: str
    reason: str  # the profiled kind, e.g. "id_like" or "constant"


class AnalyzeResponse(BaseModel):
    dataset: str
    description: str
    n_tested_pairs: int
    pairs: list[AnalysisPair]
    # Columns excluded from analysis (id-like / constant / datetime), so an empty
    # `pairs` list is explained rather than silent.
    dropped_columns: list[DroppedColumn] = Field(default_factory=list)


class FeatureWeight(BaseModel):
    """One regression feature's raw slope and standardized influence."""

    name: str
    coefficient: float  # target units per 1 unit of the feature
    std_importance: float  # |beta * std(x) / std(y)|, comparable across features


class FeatureStat(BaseModel):
    """Per-feature slope + value range, for the prediction explainers."""

    name: str
    coefficient: float
    mean: float
    min: float
    max: float


class FeatureCandidate(BaseModel):
    """A numeric column's correlation with the target, reported whether or not
    it's currently included in the fitted model — powers the feature checklist.

    `same_measure` marks another meter of the target quantity (total vs. IT vs.
    cooling power): selectable by hand, never auto-selected, because regressing
    one meter on the others reproduces an accounting identity instead of
    forecasting.
    """

    name: str
    correlation: float
    effect_size: float
    included: bool
    same_measure: bool = False


class ForecastPoint(BaseModel):
    """One row of the hold-out window: actual vs predicted target value."""

    index: int
    actual: float
    predicted: float
    label: str | None = None  # e.g. the timestamp
    values: dict[str, float] | None = None  # feature values at this row


class PredictResponse(BaseModel):
    """Result of a linear-regression forecast on a time-ordered hold-out."""

    dataset: str
    target: str
    features: list[str]
    method: str
    n_train: int
    n_test: int
    r2: float
    mae: float
    rmse: float
    baseline_mae: float
    intercept: float
    weights: list[FeatureWeight]
    series: list[ForecastPoint]
    feature_stats: list[FeatureStat] = Field(default_factory=list)
    candidates: list[FeatureCandidate] = Field(default_factory=list)
    min_correlation: float = 0.0
    # Every numeric column that could be forecast, so the UI can offer a target
    # picker -- an uploaded CSV rarely uses the default column name.
    available_targets: list[str] = Field(default_factory=list)


class PredictRequest(BaseModel):
    """Forecast a numeric target from the other numeric columns of a dataset.

    `dataset` is a filename under data/ (default: the seeded datacenter load
    series); ignored if `rows` is given (e.g. an upload or a synthesized
    series). `target` unset lets the engine pick — the facility-wide power
    meter if the data has one, else any power column, else the last numeric
    column — so an uploaded CSV with unknown names still forecasts.
    `test_fraction` is the time-ordered hold-out share (last rows).
    `min_correlation` auto-selects features whose correlation with the target
    meets the threshold (ignored if `feature_cols` is given). `feature_cols`,
    if given, overrides the threshold with an explicit manual pick.
    """

    dataset: str = "rechenzentrum_load.csv"
    rows: list[dict] | None = None
    target: str | None = None
    test_fraction: float = 0.2
    min_correlation: float = 0.0
    feature_cols: list[str] | None = None


class CorrelationMatrixResponse(BaseModel):
    """Full pairwise correlation matrix over a dataset's numeric columns.

    Both Pearson (linear) and Spearman (monotone) are returned so the UI can
    toggle without a refetch. Cells are None where a column has no variance.
    """

    dataset: str
    columns: list[str]
    n: int  # rows used (complete numeric rows)
    pearson: list[list[float | None]]
    spearman: list[list[float | None]]


class PairPoint(BaseModel):
    x: float
    y: float


class PairResponse(BaseModel):
    """Scatter + correlation for one X-Y pair, optionally controlling for Z.

    When `z` is given, `partial_r` is the Pearson correlation of the residuals
    of X and Y after regressing each on Z, and `residual_points` are those
    residuals -- so a collapsing correlation is visible directly.
    """

    dataset: str
    x: str
    y: str
    n: int
    r: float | None  # Pearson X-Y
    rho: float | None  # Spearman X-Y
    points: list[PairPoint]
    z: str | None = None
    partial_r: float | None = None
    residual_points: list[PairPoint] = Field(default_factory=list)


class RawColumn(BaseModel):
    """One column's type and lightweight profile for the raw-data view."""

    name: str
    dtype: Literal["numeric", "text"]
    n_missing: int
    # numeric-only summary (None for text columns)
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    std: float | None = None
    # text-only summary
    n_unique: int | None = None
    example: str | None = None


class RawDataResponse(BaseModel):
    """A dataset's raw rows (bounded preview) plus a per-column profile."""

    dataset: str
    n_rows: int  # total rows in the file
    n_cols: int
    columns: list[RawColumn]
    rows: list[dict]  # first `returned_rows` rows, values JSON-safe
    returned_rows: int  # how many rows `rows` actually contains (<= n_rows)


class AnalyzeRequest(BaseModel):
    """Either reference a CSV under data/ by name, or pass inline rows.

    `dataset` is a filename relative to the data/ directory (e.g. "synthetic.csv"
    or "fixtures/ice_cream.csv"). `rows` + `description` allow inline analysis.
    """

    dataset: str | None = None
    description: str | None = None
    rows: list[dict] | None = None
    top_k: int | None = None  # cap on number of returned pairs (by effect size)


class SynthesizeRequest(BaseModel):
    """Generate a plausible datacenter load series from a few specs instead of
    a CSV -- for exploring "what if this datacenter had 50,000 H100s doing
    inference" without needing real measurements. `preset`, if given, overrides
    the other fields with one of the named presets in `engine.synth.PRESETS`.
    """

    n_gpus: int = 50_000
    gpu_type: Literal["l40s", "a100", "h100", "h200", "b200"] = "h100"
    workload: Literal["training", "inference"] = "training"
    model_class: Literal["klein", "70b", "120b"] = "70b"
    arch: Literal["dense", "moe"] = "dense"
    inference_phase: Literal["decode", "prefill"] = "decode"
    cooling: Literal["luft", "warmwasser", "direktchip", "immersion"] = "warmwasser"
    pue: float = 1.3
    climate: Literal["kalt", "gemaessigt", "warm"] = "gemaessigt"
    occupancy_pct: float = 100.0
    chip_load_pct: float = 75.0
    idle_w: float = 100.0
    tdp_w: float = 700.0
    moe_anteil_pct: float = 12.5
    batch_size: int = 16
    days: int = 14
    preset: str | None = None


class SynthesizeResponse(BaseModel):
    label: str  # human-readable summary of the spec used
    rows: list[dict]
    columns: list[str]


class UploadRowsResponse(BaseModel):
    """Combined rows from one or more uploaded CSVs, for feeding the forecast
    tab directly (as opposed to /upload, which runs the full correlation
    pipeline and returns verdicts instead of raw rows)."""

    label: str
    rows: list[dict]
    columns: list[str]
