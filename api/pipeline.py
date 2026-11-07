"""End-to-end analysis pipeline: profiling -> correlation+FDR -> LLM classify ->
verification -> plot. Shared by the FastAPI app and the eval harness so both run
identical logic.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from api.schemas import (
    AnalysisPair,
    AnalyzeResponse,
    BarGroup,
    DroppedColumn,
    PlainStats,
    PlotData,
    PlotPoint,
    VerificationResult,
)
from engine.config import MAX_PLOT_POINTS
from engine.correlation import (
    PairAssociation,
    association_lookup,
    compute_correlations,
    rank_survivors,
)
from engine.llm.base import CorrelationStat, LLMClient, PairContext, Verdict
from engine.plain import build_plain
from engine.profiling import Profile, analyzable_columns, profile_dataframe
from engine.verification import can_verify, verify_confounder

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

DEFAULT_DESCRIPTION = "User-supplied tabular dataset."


# ----------------------------------------------------------------------------
# Dataset loading
# ----------------------------------------------------------------------------


def resolve_dataset_path(name: str) -> Path:
    """Resolve a dataset name to a path strictly under data/ (no traversal)."""
    candidate = (DATA_DIR / name).resolve()
    if not str(candidate).startswith(str(DATA_DIR.resolve())):
        raise ValueError(f"Dataset path escapes the data directory: {name!r}")
    if not candidate.exists():
        raise FileNotFoundError(f"Dataset not found: {name!r}")
    return candidate


def load_dataframe(
    dataset: str | None,
    rows: list[dict] | None,
    description: str | None,
) -> tuple[pd.DataFrame, str, str]:
    """Return (df, description, dataset_label) from a name reference or inline rows."""
    if rows is not None:
        df = pd.DataFrame(rows)
        return df, description or DEFAULT_DESCRIPTION, "inline"
    if dataset is not None:
        path = resolve_dataset_path(dataset)
        df = pd.read_csv(path)
        return df, description or _describe_dataset(dataset), dataset
    raise ValueError("Provide either `dataset` or `rows`.")


# ----------------------------------------------------------------------------
# Multi-CSV upload combination
# ----------------------------------------------------------------------------

# A shared column qualifies as a join key when it is highly unique within every
# file (so the merge stays 1:1-ish) and its values actually overlap across files.
KEY_UNIQUE_FRACTION = 0.8
KEY_MIN_OVERLAP = 2


def _stem(filename: str) -> str:
    """Filename without directory or .csv extension, used to namespace columns."""
    return Path(filename).stem or filename


def _unique_fraction(series: pd.Series) -> float:
    n = int(series.notna().sum())
    if n == 0:
        return 0.0
    return series.nunique(dropna=True) / n


def _pick_join_key(named: list[tuple[str, pd.DataFrame]]) -> str | None:
    """Choose a column present in every file that looks like a join key:
    near-unique in each file and with overlapping values across files."""
    common = set(named[0][1].columns)
    for _, df in named[1:]:
        common &= set(df.columns)

    best: str | None = None
    best_score = 0.0
    for col in common:
        score = min(_unique_fraction(df[col]) for _, df in named)
        if score < KEY_UNIQUE_FRACTION:
            continue
        value_sets = [set(df[col].dropna().tolist()) for _, df in named]
        overlap = len(set.intersection(*value_sets)) if value_sets else 0
        if overlap < KEY_MIN_OVERLAP:
            continue
        if score > best_score:
            best_score, best = score, col
    return best


def _disambiguate(
    named: list[tuple[str, pd.DataFrame]], keep: set[str]
) -> list[tuple[str, pd.DataFrame]]:
    """Prefix any column name shared by more than one file with that file's
    stem (e.g. `sales.value`), leaving `keep` (the join key) untouched."""
    counts: Counter[str] = Counter()
    for _, df in named:
        counts.update(df.columns)
    out: list[tuple[str, pd.DataFrame]] = []
    for stem, df in named:
        rename = {
            c: f"{stem}.{c}"
            for c in df.columns
            if c not in keep and counts[c] > 1
        }
        out.append((stem, df.rename(columns=rename) if rename else df))
    return out


def combine_uploaded_frames(
    frames: list[tuple[str, pd.DataFrame]],
) -> tuple[pd.DataFrame, str, str]:
    """Combine one or more uploaded CSVs into a single dataframe for analysis.

    Strategy ("auto"): if the files share a near-unique key column with
    overlapping values, outer-merge on it (cross-file correlations align by
    key); otherwise line the rows up by position (truncating to the shortest
    file). Colliding column names are namespaced by file stem.

    Returns (combined_df, dataset_label, description).
    """
    if not frames:
        raise ValueError("No files provided.")

    named = [(_stem(name), df) for name, df in frames]
    file_list = ", ".join(name for name, _ in frames)

    if len(named) == 1:
        name, df = frames[0]
        return df, _stem(name), f"Uploaded file '{name}'."

    key = _pick_join_key(named)

    if key is not None:
        disambig = _disambiguate(named, keep={key})
        merged = disambig[0][1]
        for _, df in disambig[1:]:
            merged = merged.merge(df, on=key, how="outer")
        label = f"uploaded ({len(named)} files, merged on '{key}')"
        desc = (
            f"Uploaded files [{file_list}] merged on shared key '{key}'. "
            "Correlations are searched across columns from all files; each is "
            "classified into a causal category and in-data confounders are "
            "verified by partial correlation."
        )
        return merged, label, desc

    # No usable key: align by row position.
    aligned = _disambiguate(named, keep=set())
    min_len = min(len(df) for _, df in aligned)
    parts = [df.iloc[:min_len].reset_index(drop=True) for _, df in aligned]
    combined = pd.concat(parts, axis=1)
    label = f"uploaded ({len(named)} files, row-aligned)"
    desc = (
        f"Uploaded files [{file_list}] aligned by row order ({min_len} rows; "
        "no shared key column found). Correlations are searched across columns "
        "from all files; each is classified into a causal category and in-data "
        "confounders are verified by partial correlation."
    )
    return combined, label, desc


def _describe_dataset(name: str) -> str:
    if name == "synthetic.csv":
        return (
            "Seeded synthetic dataset with a known causal structure (study/exam, "
            "exercise/heart-rate, weather-driven ice-cream/drownings, wealth-driven "
            "TV/life-expectancy, a selection pair, diet/cholesterol, smoking, and "
            "eight independent pure-noise columns)."
        )
    return f"Dataset '{name}'."


# ----------------------------------------------------------------------------
# Context, plotting, verification
# ----------------------------------------------------------------------------


def build_pair_context(
    df: pd.DataFrame,
    profiles: dict[str, Profile],
    x: str,
    y: str,
    stat: CorrelationStat,
    description: str,
    n_tested_pairs: int,
) -> PairContext:
    analyzable = analyzable_columns(profiles)
    others = [c for c in analyzable if c not in (x, y)]
    return PairContext(
        x=x,
        y=y,
        dataset_description=description,
        x_info=profiles[x].to_column_info(),
        y_info=profiles[y].to_column_info(),
        stat=stat,
        other_columns=others,
        n_tested_pairs=n_tested_pairs,
    )


def _match_confounder_column(name: str | None, profiles: dict[str, Profile]) -> str | None:
    if not name:
        return None
    if name in profiles:
        return name
    lowered = {c.lower(): c for c in profiles}
    return lowered.get(name.lower())


def build_verification(
    df: pd.DataFrame,
    profiles: dict[str, Profile],
    x: str,
    y: str,
    verdict: Verdict,
) -> VerificationResult | None:
    """Run partial-correlation verification when the LLM names an in-data,
    numeric confounder."""
    if not verdict.confounder_in_data:
        return None
    z = _match_confounder_column(verdict.confounder, profiles)
    if z is None or z in (x, y) or not can_verify(x, y, z, profiles):
        return None
    res = verify_confounder(df, x, y, z)
    return VerificationResult(
        confounder=res.confounder,
        method=res.method,
        r_before=res.r_before,
        r_after=res.r_after,
        p_after=res.p_after,
        n=res.n,
        threshold_abs=res.threshold_abs,
        collapsed=res.collapsed,
        note=res.note,
    )


def build_plot(
    df: pd.DataFrame, profiles: dict[str, Profile], x: str, y: str
) -> PlotData:
    kx, ky = profiles[x].kind, profiles[y].kind

    if kx == "numeric" and ky == "numeric":
        sub = df[[x, y]].dropna()
        if len(sub) > MAX_PLOT_POINTS:
            step = max(1, len(sub) // MAX_PLOT_POINTS)
            sub = sub.iloc[::step].head(MAX_PLOT_POINTS)
        points = [
            PlotPoint(x=float(a), y=float(b))
            for a, b in zip(sub[x].to_numpy(), sub[y].to_numpy())
        ]
        return PlotData(kind="scatter", x_label=x, y_label=y, points=points)

    # categorical/categorical: bars show how y's modal class shifts across x
    if kx == "categorical" and ky == "categorical":
        sub = df[[x, y]].dropna()
        modal_y = sub[y].astype(str).mode().iloc[0]
        bars = []
        for level, g in sub.groupby(x):
            frac = float((g[y].astype(str) == modal_y).mean())
            bars.append(BarGroup(category=str(level), value=round(frac, 4), n=int(len(g))))
        bars.sort(key=lambda b: b.category)
        return PlotData(
            kind="grouped_bar",
            x_label=x,
            y_label=y,
            bars=bars,
            value_label=f"P({y}={modal_y})",
        )

    # mixed: bars = mean of the numeric column per category of the categorical one
    cat_col, num_col = (x, y) if kx == "categorical" else (y, x)
    sub = df[[cat_col, num_col]].dropna()
    bars = []
    for level, g in sub.groupby(cat_col):
        bars.append(
            BarGroup(
                category=str(level),
                value=round(float(g[num_col].mean()), 4),
                n=int(len(g)),
            )
        )
    bars.sort(key=lambda b: b.value)
    return PlotData(
        kind="grouped_bar",
        x_label=cat_col,
        y_label=num_col,
        bars=bars,
        value_label=f"Mittelwert {num_col}",
    )


# ----------------------------------------------------------------------------
# Per-pair and whole-dataset analysis
# ----------------------------------------------------------------------------


def build_plain_stats(
    df: pd.DataFrame,
    profiles: dict[str, Profile],
    x: str,
    y: str,
    stat: CorrelationStat,
) -> PlainStats:
    """Everyday-language readout. The raw columns are passed only for
    numeric-vs-numeric pairs, where the rule-of-thumb slope is meaningful."""
    numeric = profiles[x].kind == "numeric" and profiles[y].kind == "numeric"
    xs = df[x] if numeric else None
    ys = df[y] if numeric else None
    res = build_plain(
        stat.method, stat.coefficient, stat.significant, x, y, xs, ys
    )
    return PlainStats(
        summary=res.summary,
        strength_label=res.strength_label,
        strength_pct=res.strength_pct,
        direction=res.direction,  # type: ignore[arg-type]
        explained_pct=res.explained_pct,
        rule_of_thumb=res.rule_of_thumb,
        chance_text=res.chance_text,
    )


def analyze_pair(
    df: pd.DataFrame,
    profiles: dict[str, Profile],
    x: str,
    y: str,
    stat: CorrelationStat,
    llm: LLMClient,
    description: str,
    n_tested_pairs: int,
) -> AnalysisPair:
    ctx = build_pair_context(df, profiles, x, y, stat, description, n_tested_pairs)
    verdict = llm.classify(ctx)
    verification = build_verification(df, profiles, x, y, verdict)
    plot = build_plot(df, profiles, x, y)
    plain = build_plain_stats(df, profiles, x, y, stat)
    return AnalysisPair(
        x=x,
        y=y,
        stat=stat,
        verdict=verdict,
        verification=verification,
        plot=plot,
        plain=plain,
    )


def analyze_dataframe_events(
    df: pd.DataFrame,
    description: str,
    dataset_label: str,
    llm: LLMClient,
    top_k: int | None = None,
) -> Iterator[tuple[str, dict | AnalyzeResponse]]:
    """Same pipeline as :func:`analyze_dataframe`, but yields progress events so a
    caller can stream "what's happening" to the UI.

    Yields ``("step", {...})`` events as each real stage runs, then exactly one
    terminal ``("result", AnalyzeResponse)``.
    """

    def step(stage: str, label: str, progress: float, **extra: object) -> tuple[str, dict]:
        return ("step", {"type": "step", "stage": stage, "label": label,
                         "progress": round(progress, 3), **extra})

    yield step("profiling", "Spalten werden profiliert …", 0.04)
    profiles = profile_dataframe(df)
    analyzable = analyzable_columns(profiles)
    dropped = [
        DroppedColumn(name=name, reason=p.kind)
        for name, p in profiles.items()
        if not p.analyzable
    ]
    yield step(
        "profiling",
        "Spaltentypen erkannt",
        0.14,
        detail=f"{len(analyzable)} analysierbar, {len(dropped)} verworfen",
    )

    yield step("correlation", "Korrelationen werden berechnet …", 0.22)
    associations = compute_correlations(df, profiles)
    n_tested = len(associations)
    yield step(
        "correlation",
        "Paarweise Korrelationen berechnet",
        0.34,
        detail=f"{n_tested} Paare getestet",
    )

    yield step(
        "fdr",
        "Korrektur für multiples Testen (Benjamini-Hochberg)",
        0.44,
    )
    survivors = rank_survivors(associations)
    if top_k is not None:
        survivors = survivors[:top_k]
    yield step(
        "ranking",
        "Signifikante Zusammenhänge ausgewählt",
        0.52,
        detail=f"{len(survivors)} relevante Paare",
    )

    pairs: list[AnalysisPair] = []
    total = max(len(survivors), 1)
    for i, pa in enumerate(survivors, start=1):
        yield step(
            "classify",
            f"Ursache wird eingeordnet: {pa.x} ↔ {pa.y}",
            0.55 + 0.4 * (i / total),
            detail=f"{i}/{len(survivors)}",
            pair={"x": pa.x, "y": pa.y},
        )
        pairs.append(
            analyze_pair(df, profiles, pa.x, pa.y, pa.stat, llm, description, n_tested)
        )

    yield step("done", "Analyse abgeschlossen", 1.0, detail=f"{len(pairs)} Karten")
    yield (
        "result",
        AnalyzeResponse(
            dataset=dataset_label,
            description=description,
            n_tested_pairs=n_tested,
            pairs=pairs,
            dropped_columns=dropped,
        ),
    )


def analyze_dataframe(
    df: pd.DataFrame,
    description: str,
    dataset_label: str,
    llm: LLMClient,
    top_k: int | None = None,
) -> AnalyzeResponse:
    """Full pipeline over a dataframe: returns ranked survivor pairs as verdicts."""
    result: AnalyzeResponse | None = None
    for kind, payload in analyze_dataframe_events(
        df, description, dataset_label, llm, top_k=top_k
    ):
        if kind == "result":
            assert isinstance(payload, AnalyzeResponse)
            result = payload
    assert result is not None  # the generator always emits a terminal result
    return result


def analyze_ground_truth_pairs(
    df: pd.DataFrame,
    description: str,
    gt_pairs: list[dict],
    llm: LLMClient,
) -> list[AnalysisPair]:
    """Classify a specific list of (x, y) pairs (used by the eval). The
    correlation stat is taken from the full-dataset FDR run; pairs whose stat
    is missing get a neutral placeholder so the LLM is still exercised."""
    profiles = profile_dataframe(df)
    associations = compute_correlations(df, profiles)
    n_tested = len(associations)
    lookup = association_lookup(associations)

    out: list[AnalysisPair] = []
    for entry in gt_pairs:
        x, y = entry["x"], entry["y"]
        stat = lookup.get(frozenset((x, y)))
        if stat is None:
            stat = CorrelationStat(
                method="pearson",
                coefficient=0.0,
                effect_size=0.0,
                p_value=1.0,
                p_adjusted=1.0,
                n=int(len(df)),
                significant=False,
            )
        out.append(
            analyze_pair(df, profiles, x, y, stat, llm, description, n_tested)
        )
    return out
