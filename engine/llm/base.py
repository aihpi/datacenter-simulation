"""Locked LLM contract and shared data structures.

This module is the integration surface for the whole system. Every other
module (stats engine, mock/vertex clients, backend, eval) imports the types
defined here. Do not change field names or the verdict taxonomy without
updating every consumer.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

# The five-way taxonomy. This ordering is canonical and used for color maps,
# confusion matrices, and validation everywhere.
VerdictLabel = Literal[
    "causal",  # X -> Y (X causes Y)
    "reverse_causal",  # Y -> X (Y causes X; the arrow points back)
    "confounder",  # X <- Z -> Y (a third variable Z drives both)
    "selection",  # spurious association induced by conditioning/selection (collider)
    "chance",  # sampling noise; no real relationship
]

VERDICT_LABELS: tuple[str, ...] = (
    "causal",
    "reverse_causal",
    "confounder",
    "selection",
    "chance",
)


class ColumnInfo(BaseModel):
    """Per-column metadata handed to the LLM. Never carries raw row data."""

    name: str
    dtype: Literal["numeric", "categorical", "datetime", "id_like", "constant"]
    units: str | None = None
    sample_values: list[str] = Field(default_factory=list)
    n_unique: int | None = None


class CorrelationStat(BaseModel):
    """The statistical association between one X-Y pair."""

    method: Literal[
        "pearson",
        "spearman",
        "cramers_v",
        "point_biserial",
        "correlation_ratio",
    ]
    coefficient: float  # signed where meaningful; in [-1, 1] (or [0,1] for V/eta)
    effect_size: float  # |coefficient|, used for ranking survivors
    p_value: float
    p_adjusted: float  # Benjamini-Hochberg FDR-adjusted p across all tested pairs
    n: int  # complete-case sample size used
    significant: bool  # survived FDR at the configured alpha


class PairContext(BaseModel):
    """Everything the LLM needs to classify one pair -- and nothing raw.

    Carries column names, the dataset's one-line description, per-column
    type/units/sample values, the correlation stats, and the names of the
    *other* available columns (so the model may name a confounder that is
    present in the data).
    """

    x: str
    y: str
    dataset_description: str
    x_info: ColumnInfo
    y_info: ColumnInfo
    stat: CorrelationStat
    other_columns: list[str] = Field(default_factory=list)
    n_tested_pairs: int = 1  # how many pairs were tested overall (selection prior)


class RuledOut(BaseModel):
    """One alternative explanation the model considered and rejected.

    Together the four ``RuledOut`` entries on a Verdict spell out the elimination
    reasoning: for every category that was *not* chosen, a one-line why-not. This
    is what the UI surfaces as "what was excluded".
    """

    label: VerdictLabel  # the rejected category
    why: str  # one short clause: why this alternative is less likely


class Verdict(BaseModel):
    """The LLM's classification of a single correlation. The contract output."""

    x: str
    y: str
    verdict: VerdictLabel
    confidence: float = Field(ge=0.0, le=1.0)
    confounder: str | None = None  # suspected third variable, or null
    confounder_in_data: bool = False  # is that confounder present as a column?
    reasoning: str  # <= 3 sentences, no fabricated stats
    needed_data: str  # what would be required to be sure
    # The alternatives the model excluded (one per non-chosen category). Optional
    # and defaults to empty so older payloads / backends remain valid.
    ruled_out: list[RuledOut] = Field(default_factory=list)


@runtime_checkable
class LLMClient(Protocol):
    """The single interface every backend implements (mock, vertex, ...)."""

    def classify(self, ctx: PairContext) -> Verdict: ...
