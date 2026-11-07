"""Gate 5: API contract. /health returns 200; /analyze returns schema-valid JSON."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("LLM_BACKEND", "mock")

from api.main import app  # noqa: E402
from api.schemas import AnalyzeResponse  # noqa: E402
from engine.llm.base import VERDICT_LABELS  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_datasets_lists_synthetic():
    r = client.get("/datasets")
    assert r.status_code == 200
    names = r.json()["datasets"]
    assert "synthetic.csv" in names


def test_analyze_synthetic_is_schema_valid():
    r = client.post("/analyze", json={"dataset": "synthetic.csv"})
    assert r.status_code == 200, r.text
    parsed = AnalyzeResponse.model_validate(r.json())  # raises on contract drift
    assert parsed.n_tested_pairs > 0
    assert len(parsed.pairs) >= 1
    for pair in parsed.pairs:
        assert pair.verdict.verdict in VERDICT_LABELS
        assert 0.0 <= pair.verdict.confidence <= 1.0
        assert pair.plot.kind in ("scatter", "grouped_bar")


def test_analyze_surfaces_confounder_with_verification():
    r = client.post("/analyze", json={"dataset": "synthetic.csv"})
    parsed = AnalyzeResponse.model_validate(r.json())
    by_pair = {frozenset((p.x, p.y)): p for p in parsed.pairs}
    ic = by_pair.get(frozenset(("ice_cream_sales", "drownings")))
    assert ic is not None, "ice_cream/drownings should survive FDR and be returned"
    assert ic.verdict.verdict == "confounder"
    assert ic.verdict.confounder_in_data is True
    assert ic.verification is not None
    assert ic.verification.collapsed is True
    assert abs(ic.verification.r_after) < abs(ic.verification.r_before)


def test_analyze_inline_rows():
    rows = [{"a": i, "b": 2 * i + 1, "c": -i} for i in range(60)]
    r = client.post("/analyze", json={"dataset": None, "rows": rows, "description": "tiny"})
    assert r.status_code == 200, r.text
    AnalyzeResponse.model_validate(r.json())


def test_analyze_fixture_present_confounder():
    r = client.post("/analyze", json={"dataset": "fixtures/ice_cream_drownings.csv"})
    assert r.status_code == 200, r.text
    AnalyzeResponse.model_validate(r.json())


def test_analyze_missing_dataset_404():
    r = client.post("/analyze", json={"dataset": "does_not_exist.csv"})
    assert r.status_code == 404


def test_analyze_requires_input_422():
    r = client.post("/analyze", json={})
    assert r.status_code == 422


def test_analyze_path_traversal_blocked():
    r = client.post("/analyze", json={"dataset": "../pyproject.toml"})
    assert r.status_code in (400, 404)
