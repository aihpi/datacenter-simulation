"""FastAPI app for datacenter-simulation.

Endpoints:
  GET  /health   -> {"status": "ok"}
  POST /analyze  -> AnalyzeResponse (profiling -> correlation+FDR -> classify -> verify)
  GET  /datasets -> list of available dataset names under data/
  POST /upload   -> stubbed (out of scope for the Definition of Done)
"""

from __future__ import annotations

import asyncio
import io
import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.pipeline import (
    DATA_DIR,
    analyze_dataframe,
    analyze_dataframe_events,
    combine_uploaded_frames,
    load_dataframe,
    resolve_dataset_path,
)
from api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    CorrelationMatrixResponse,
    FeatureCandidate,
    FeatureStat,
    FeatureWeight,
    ForecastPoint,
    PairPoint,
    PairResponse,
    PredictRequest,
    PredictResponse,
    RawColumn,
    RawDataResponse,
    SynthesizeRequest,
    SynthesizeResponse,
    UploadRowsResponse,
)
from engine.correlation import pearson, spearman
from api.themes import THEMES, get_theme, resolve_theme
from engine.forecast import fit_forecast, numeric_targets, resolve_target
from engine.llm import get_client
from engine.synth import (
    PRESET_NAMES,
    PRESETS,
    DatacenterSpec,
    spec_label,
    synthesize_rechenzentrum,
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB per file
# Small pause between streamed progress events so the UI's step bar is visible
# even though the mock backend computes everything almost instantly.
STREAM_STEP_DELAY = 0.12

load_dotenv()

app = FastAPI(title="datacenter-simulation", version="0.1.0")

# Local demo: allow the Vite frontend (any localhost port) to call us directly.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/datasets")
def datasets() -> dict[str, list[str]]:
    names: list[str] = []
    if DATA_DIR.exists():
        for p in sorted(DATA_DIR.rglob("*.csv")):
            names.append(str(p.relative_to(DATA_DIR)))
    return {"datasets": names}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    if req.dataset is None and req.rows is None:
        raise HTTPException(status_code=422, detail="Provide `dataset` or `rows`.")
    try:
        df, description, label = load_dataframe(req.dataset, req.rows, req.description)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if df.shape[1] < 2:
        raise HTTPException(status_code=400, detail="Dataset needs >= 2 columns.")

    llm = get_client()
    return analyze_dataframe(df, description, label, llm, top_k=req.top_k)


async def _frames_from_uploads(
    files: list[UploadFile],
) -> list[tuple[str, pd.DataFrame]]:
    """Validate + parse uploaded CSVs into (filename, dataframe) frames."""
    if not files:
        raise HTTPException(status_code=422, detail="Provide at least one CSV file.")
    frames: list[tuple[str, pd.DataFrame]] = []
    for f in files:
        name = f.filename or "upload.csv"
        if not name.lower().endswith(".csv"):
            raise HTTPException(
                status_code=400, detail=f"{name!r}: only .csv files are supported."
            )
        raw = await f.read()
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"{name!r} exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
            )
        try:
            df = pd.read_csv(io.BytesIO(raw))
        except Exception as exc:  # noqa: BLE001 - surface any parse error to the client
            raise HTTPException(
                status_code=400, detail=f"Could not parse {name!r} as CSV: {exc}"
            ) from exc
        if df.empty or df.shape[1] == 0:
            raise HTTPException(status_code=400, detail=f"{name!r} has no data.")
        frames.append((name, df))
    return frames


def _combine_or_400(
    frames: list[tuple[str, pd.DataFrame]],
) -> tuple[pd.DataFrame, str, str]:
    try:
        df, label, description = combine_uploaded_frames(frames)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if df.shape[1] < 2:
        raise HTTPException(
            status_code=400,
            detail="Combined data needs >= 2 columns to search for correlations.",
        )
    return df, label, description


@app.post("/upload", response_model=AnalyzeResponse)
async def upload(
    files: list[UploadFile] = File(...),
    top_k: int | None = None,
) -> AnalyzeResponse:
    """Analyze one or more uploaded CSV files.

    Multiple files are combined ("auto": merge on a shared key column when one
    exists, otherwise align by row order), then run through the same pipeline as
    /analyze: correlations across all columns -> causal classification ->
    partial-correlation verification of in-data confounders.
    """
    frames = await _frames_from_uploads(files)
    df, label, description = _combine_or_400(frames)
    llm = get_client()
    return analyze_dataframe(df, description, label, llm, top_k=top_k)


@app.post("/upload/rows", response_model=UploadRowsResponse)
async def upload_rows(files: list[UploadFile] = File(...)) -> UploadRowsResponse:
    """Combine one or more uploaded CSVs and return the raw rows (not verdicts) --
    for feeding the forecast tab (/predict) directly with real, uploaded data."""
    frames = await _frames_from_uploads(files)
    df, label, _description = _combine_or_400(frames)
    return UploadRowsResponse(
        label=label,
        rows=json.loads(df.to_json(orient="records")),
        columns=df.columns.tolist(),
    )


# ----------------------------------------------------------------------------
# Raw data (inspect a dataset's rows + column profile before any modelling)
# ----------------------------------------------------------------------------

RAW_ROW_LIMIT = 2000  # cap the preview so large files stay responsive


@app.get("/raw", response_model=RawDataResponse)
def raw(dataset: str = "rechenzentrum_load.csv", limit: int = 100) -> RawDataResponse:
    """Return a bounded preview of a dataset's rows plus a per-column profile,
    so the raw inputs can be inspected before any analysis or forecast."""
    try:
        path = resolve_dataset_path(dataset)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    df = pd.read_csv(path)
    n_rows = int(df.shape[0])

    columns: list[RawColumn] = []
    for name in df.columns:
        col = df[name]
        n_missing = int(col.isna().sum())
        if pd.api.types.is_numeric_dtype(col):
            valid = col.dropna()
            columns.append(
                RawColumn(
                    name=str(name),
                    dtype="numeric",
                    n_missing=n_missing,
                    min=float(valid.min()) if not valid.empty else None,
                    max=float(valid.max()) if not valid.empty else None,
                    mean=float(valid.mean()) if not valid.empty else None,
                    std=float(valid.std()) if len(valid) > 1 else None,
                )
            )
        else:
            valid = col.dropna().astype(str)
            columns.append(
                RawColumn(
                    name=str(name),
                    dtype="text",
                    n_missing=n_missing,
                    n_unique=int(valid.nunique()),
                    example=str(valid.iloc[0]) if not valid.empty else None,
                )
            )

    n = max(0, min(limit, RAW_ROW_LIMIT))
    # NaN -> None so the JSON stays valid; native Python types for the rows.
    preview = df.head(n).where(pd.notna(df.head(n)), None).to_dict(orient="records")

    return RawDataResponse(
        dataset=dataset,
        n_rows=n_rows,
        n_cols=int(df.shape[1]),
        columns=columns,
        rows=preview,
        returned_rows=len(preview),
    )


# ----------------------------------------------------------------------------
# Correlations (interactive relationship explorer between input variables)
# ----------------------------------------------------------------------------

PAIR_MAX_POINTS = 500  # cap the scatter payload sent to the UI


def _downsample(xs: np.ndarray, ys: np.ndarray) -> list[PairPoint]:
    step = max(1, len(xs) // PAIR_MAX_POINTS)
    return [
        PairPoint(x=round(float(xs[i]), 4), y=round(float(ys[i]), 4))
        for i in range(0, len(xs), step)
    ]


@app.get("/correlations", response_model=CorrelationMatrixResponse)
def correlations(
    dataset: str = "rechenzentrum_full.csv",
) -> CorrelationMatrixResponse:
    """Full pairwise Pearson + Spearman matrix over the numeric columns."""
    try:
        path = resolve_dataset_path(dataset)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    num = pd.read_csv(path).select_dtypes(include="number")
    if num.shape[1] < 2:
        raise HTTPException(status_code=400, detail="Need >= 2 numeric columns.")
    cols = [str(c) for c in num.columns]
    sub = num.dropna()

    def matrix(method: str) -> list[list[float | None]]:
        m = sub.corr(method=method)
        return [
            [
                None if pd.isna(m.iat[i, j]) else round(float(m.iat[i, j]), 4)
                for j in range(len(cols))
            ]
            for i in range(len(cols))
        ]

    return CorrelationMatrixResponse(
        dataset=dataset,
        columns=cols,
        n=int(len(sub)),
        pearson=matrix("pearson"),
        spearman=matrix("spearman"),
    )


def _residuals(v: np.ndarray, z: np.ndarray) -> np.ndarray:
    """OLS residuals of v regressed on z (with intercept)."""
    design = np.column_stack([np.ones(len(z)), z])
    coef, *_ = np.linalg.lstsq(design, v, rcond=None)
    return v - design @ coef


@app.get("/pair", response_model=PairResponse)
def pair(
    dataset: str = "rechenzentrum_full.csv",
    x: str = "",
    y: str = "",
    z: str | None = None,
) -> PairResponse:
    """Scatter + correlation for one X-Y pair, optionally controlling for Z
    (partial correlation on the residuals after regressing X and Y on Z)."""
    try:
        path = resolve_dataset_path(dataset)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    df = pd.read_csv(path)
    wanted = [c for c in (x, y, z) if c]
    for col in wanted:
        if col not in df.columns:
            raise HTTPException(status_code=404, detail=f"Column not found: {col!r}")
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise HTTPException(status_code=400, detail=f"Column {col!r} is not numeric.")
    if not x or not y:
        raise HTTPException(status_code=422, detail="Provide `x` and `y`.")

    sub = df[wanted].apply(pd.to_numeric, errors="coerce").dropna()
    if len(sub) < 3:
        raise HTTPException(status_code=400, detail="Need >= 3 complete rows.")

    xs = sub[x].to_numpy(dtype=float)
    ys = sub[y].to_numpy(dtype=float)
    r, _, n = pearson(sub[x], sub[y])
    rho, _, _ = spearman(sub[x], sub[y])

    resp = PairResponse(
        dataset=dataset,
        x=x,
        y=y,
        n=n,
        r=r,
        rho=rho,
        points=_downsample(xs, ys),
    )

    if z:
        rx = _residuals(xs, sub[z].to_numpy(dtype=float))
        ry = _residuals(ys, sub[z].to_numpy(dtype=float))
        partial_r, _, _ = pearson(pd.Series(rx), pd.Series(ry))
        resp.z = z
        resp.partial_r = partial_r
        resp.residual_points = _downsample(rx, ry)

    return resp


# ----------------------------------------------------------------------------
# Synthesize (spec-based datacenter load series, no CSV needed)
# ----------------------------------------------------------------------------


@app.post("/synthesize", response_model=SynthesizeResponse)
def synthesize(req: SynthesizeRequest) -> SynthesizeResponse:
    """Generate a plausible hourly datacenter load series from a few specs
    (GPU count, workload, PUE, climate) instead of a CSV. `preset` overrides
    the other fields with one of `engine.synth.PRESETS`."""
    if req.preset is not None:
        if req.preset not in PRESETS:
            raise HTTPException(status_code=404, detail=f"Unknown preset: {req.preset!r}")
        spec = PRESETS[req.preset]
    else:
        try:
            spec = DatacenterSpec(
                n_gpus=req.n_gpus,
                gpu_type=req.gpu_type,
                workload=req.workload,
                model_class=req.model_class,
                arch=req.arch,
                inference_phase=req.inference_phase,
                cooling=req.cooling,
                pue=req.pue,
                climate=req.climate,
                occupancy_pct=req.occupancy_pct,
                chip_load_pct=req.chip_load_pct,
                idle_w=req.idle_w,
                tdp_w=req.tdp_w,
                moe_anteil_pct=req.moe_anteil_pct,
                batch_size=req.batch_size,
                days=req.days,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if spec.n_gpus <= 0:
        raise HTTPException(status_code=400, detail="n_gpus must be positive.")
    if not 1.0 <= spec.pue <= 3.0:
        raise HTTPException(status_code=400, detail="pue must be between 1.0 and 3.0.")
    if not 1 <= spec.days <= 90:
        raise HTTPException(status_code=400, detail="days must be between 1 and 90.")
    if not 2.0 <= spec.occupancy_pct <= 100.0:
        raise HTTPException(status_code=400, detail="occupancy_pct must be between 2 and 100.")
    if not 5.0 <= spec.chip_load_pct <= 100.0:
        raise HTTPException(status_code=400, detail="chip_load_pct must be between 5 and 100.")
    if spec.idle_w < 0:
        raise HTTPException(status_code=400, detail="idle_w must be >= 0.")
    if spec.tdp_w <= 0:
        raise HTTPException(status_code=400, detail="tdp_w must be positive.")
    if not 1.0 <= spec.moe_anteil_pct <= 100.0:
        raise HTTPException(status_code=400, detail="moe_anteil_pct must be between 1 and 100.")
    if not 1 <= spec.batch_size <= 65536:
        raise HTTPException(status_code=400, detail="batch_size must be between 1 and 65536.")

    df = synthesize_rechenzentrum(spec)
    label = spec_label(spec)
    return SynthesizeResponse(
        label=label,
        rows=json.loads(df.to_json(orient="records")),
        columns=df.columns.tolist(),
    )


@app.get("/synthesize/presets")
def synthesize_presets() -> dict[str, list[dict]]:
    return {
        "presets": [
            {
                "slug": slug,
                "name": PRESET_NAMES.get(slug, slug),
                "label": spec_label(spec),
                "n_gpus": spec.n_gpus,
                "gpu_type": spec.gpu_type,
                "workload": spec.workload,
                "model_class": spec.model_class,
                "arch": spec.arch,
                "inference_phase": spec.inference_phase,
                "cooling": spec.cooling,
                "pue": spec.pue,
                "climate": spec.climate,
                "occupancy_pct": spec.occupancy_pct,
                "chip_load_pct": spec.chip_load_pct,
                "idle_w": spec.idle_w,
                "tdp_w": spec.tdp_w,
                "moe_anteil_pct": spec.moe_anteil_pct,
                "batch_size": spec.batch_size,
                "days": spec.days,
            }
            for slug, spec in PRESETS.items()
        ]
    }


# ----------------------------------------------------------------------------
# Forecast (linear-regression prediction of a numeric target)
# ----------------------------------------------------------------------------


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    """Fit an OLS forecast for `target` on the other numeric columns of a dataset
    (or inline `rows`, e.g. an upload or a synthesized series) and score it on a
    time-ordered hold-out window."""
    if req.rows is not None:
        df = pd.DataFrame(req.rows)
    else:
        try:
            path = resolve_dataset_path(req.dataset)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        df = pd.read_csv(path)
    # Use the first non-numeric column (e.g. a timestamp) as the point label.
    non_numeric = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
    label_col = non_numeric[0] if non_numeric else None

    # An uploaded CSV rarely uses the default target name, so fall back to a
    # sensible column instead of failing outright.
    try:
        target = resolve_target(df, req.target)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        res = fit_forecast(
            df,
            target,
            feature_cols=req.feature_cols,
            test_fraction=req.test_fraction,
            label_col=label_col,
            min_correlation=req.min_correlation,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    included = set(res.features)

    return PredictResponse(
        dataset=req.dataset,
        target=res.target,
        features=res.features,
        method=res.method,
        n_train=res.n_train,
        n_test=res.n_test,
        r2=res.r2,
        mae=res.mae,
        rmse=res.rmse,
        baseline_mae=res.baseline_mae,
        intercept=res.intercept,
        weights=[
            FeatureWeight(
                name=w.name, coefficient=w.coefficient, std_importance=w.std_importance
            )
            for w in res.weights
        ],
        series=[
            ForecastPoint(
                index=p.index,
                actual=p.actual,
                predicted=p.predicted,
                label=p.label,
                values=p.values,
            )
            for p in res.series
        ],
        feature_stats=[
            FeatureStat(
                name=s.name,
                coefficient=s.coefficient,
                mean=s.mean,
                min=s.min,
                max=s.max,
            )
            for s in res.feature_stats
        ],
        candidates=[
            FeatureCandidate(
                name=c.name,
                correlation=c.correlation,
                effect_size=c.effect_size,
                included=c.name in included,
                same_measure=c.same_measure,
            )
            for c in res.candidates
        ],
        min_correlation=res.min_correlation,
        available_targets=numeric_targets(df),
    )


# ----------------------------------------------------------------------------
# Themes (curated topics for the start screen)
# ----------------------------------------------------------------------------


@app.get("/themes")
def themes() -> dict[str, list[dict]]:
    return {"themes": [t.to_public() for t in THEMES]}


# ----------------------------------------------------------------------------
# Streaming analysis (newline-delimited JSON progress events + final result)
# ----------------------------------------------------------------------------


class AnalyzeStreamRequest(BaseModel):
    """Stream a curated theme by slug, or a raw dataset path under data/."""

    theme: str | None = None
    dataset: str | None = None
    top_k: int | None = None


async def _ndjson_stream(
    events: Iterator[tuple[str, object]],
) -> AsyncIterator[bytes]:
    """Turn the pipeline's (kind, payload) generator into an NDJSON byte stream,
    pausing briefly between events so the UI's progress bar is perceptible."""
    try:
        for kind, payload in events:
            if kind == "result":
                line = json.dumps(
                    {"type": "result", "data": payload.model_dump()},  # type: ignore[attr-defined]
                    ensure_ascii=False,
                )
            else:
                line = json.dumps(payload, ensure_ascii=False)
            yield (line + "\n").encode("utf-8")
            await asyncio.sleep(STREAM_STEP_DELAY)
    except Exception as exc:  # noqa: BLE001 - report mid-stream failures to the client
        err = json.dumps({"type": "error", "detail": str(exc)}, ensure_ascii=False)
        yield (err + "\n").encode("utf-8")


def _stream_response(
    df: pd.DataFrame, description: str, label: str, top_k: int | None
) -> StreamingResponse:
    llm = get_client()
    events = analyze_dataframe_events(df, description, label, llm, top_k=top_k)
    return StreamingResponse(_ndjson_stream(events), media_type="application/x-ndjson")


@app.post("/analyze/stream")
def analyze_stream(req: AnalyzeStreamRequest) -> StreamingResponse:
    """Stream analysis progress for a curated theme or a dataset path."""
    if req.theme is not None:
        theme = get_theme(req.theme)
        if theme is None:
            raise HTTPException(status_code=404, detail=f"Unknown theme: {req.theme!r}")
        try:
            df, label, description, top_k = resolve_theme(theme)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _stream_response(df, description, label, req.top_k or top_k)

    if req.dataset is not None:
        try:
            df, description, label = load_dataframe(req.dataset, None, None)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if df.shape[1] < 2:
            raise HTTPException(status_code=400, detail="Dataset needs >= 2 columns.")
        return _stream_response(df, description, label, req.top_k)

    raise HTTPException(status_code=422, detail="Provide `theme` or `dataset`.")


@app.post("/upload/stream")
async def upload_stream(
    files: list[UploadFile] = File(...),
    top_k: int | None = None,
) -> StreamingResponse:
    """Stream analysis progress for uploaded CSV file(s)."""
    frames = await _frames_from_uploads(files)
    df, label, description = _combine_or_400(frames)
    return _stream_response(df, description, label, top_k)
