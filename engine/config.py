"""Shared, tunable thresholds. Single source of truth for the whole pipeline."""

from __future__ import annotations

# Significance level for FDR-adjusted p-values.
ALPHA: float = 0.05

# A pair is reported/considered "real enough to explain" if its effect size
# (|coefficient|) is at least this and it survives FDR.
MIN_EFFECT_SIZE: float = 0.15

# Verification: when we control for a proposed confounder Z, the X-Y association
# is considered to have "collapsed" (i.e. the data CONFIRMS the confounder) if
# the partial correlation's absolute value falls below this threshold...
PARTIAL_COLLAPSE_ABS: float = 0.15

# ...or if it drops to below this fraction of the original association.
PARTIAL_COLLAPSE_RATIO: float = 0.5

# Profiling: a column is "id-like" if its fraction of unique values exceeds this.
ID_UNIQUE_FRACTION: float = 0.95

# Profiling: a numeric column is treated as categorical if it has at most this
# many distinct values.
MAX_CATEGORICAL_CARDINALITY: int = 12

# Cap on points sent to the frontend scatter plot (keeps payloads small).
MAX_PLOT_POINTS: int = 300
