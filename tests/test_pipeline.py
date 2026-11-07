"""Pipeline integration: analyze_dataframe and ground-truth analysis with mock."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from api.pipeline import (
    analyze_dataframe,
    analyze_ground_truth_pairs,
    build_plot,
    load_dataframe,
)
from api.schemas import AnalyzeResponse
from engine.llm.mock import MockLLMClient
from engine.profiling import profile_dataframe

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def synthetic() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "synthetic.csv")


def test_analyze_dataframe_returns_ranked_survivors(synthetic):
    resp = analyze_dataframe(synthetic, "desc", "synthetic.csv", MockLLMClient())
    assert isinstance(resp, AnalyzeResponse)
    assert resp.pairs, "expected at least one survivor pair"
    effects = [p.stat.effect_size for p in resp.pairs]
    assert effects == sorted(effects, reverse=True)
    # id-like / constant columns must never appear
    appearing = {c for p in resp.pairs for c in (p.x, p.y)}
    assert "record_id" not in appearing
    assert "study_version" not in appearing


def test_ground_truth_pairs_all_classified(synthetic):
    gt = json.loads((ROOT / "data" / "ground_truth.json").read_text())
    results = analyze_ground_truth_pairs(synthetic, "desc", gt, MockLLMClient())
    assert len(results) == len(gt)
    # mock is correct by construction
    for entry, ap in zip(gt, results):
        assert ap.verdict.verdict == entry["true_label"]


def test_build_plot_scatter_and_bar(synthetic):
    profiles = profile_dataframe(synthetic)
    scatter = build_plot(synthetic, profiles, "hours_studied", "exam_score")
    assert scatter.kind == "scatter" and len(scatter.points) > 0
    bar = build_plot(synthetic, profiles, "diet_type", "cholesterol")
    assert bar.kind == "grouped_bar" and len(bar.bars) == 3
    catcat = build_plot(synthetic, profiles, "smoker", "lung_issue")
    assert catcat.kind == "grouped_bar" and len(catcat.bars) >= 2


def test_load_dataframe_from_name():
    df, desc, label = load_dataframe("synthetic.csv", None, None)
    assert label == "synthetic.csv"
    assert df.shape[0] > 0 and desc


def test_top_k_limits_pairs(synthetic):
    resp = analyze_dataframe(synthetic, "d", "synthetic.csv", MockLLMClient(), top_k=3)
    assert len(resp.pairs) <= 3
