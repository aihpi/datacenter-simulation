"""Schema validation for the locked contract types."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.schemas import AnalysisPair, AnalyzeResponse, PlotData, VerificationResult
from engine.llm.base import CorrelationStat, PairContext, Verdict


def _stat() -> CorrelationStat:
    return CorrelationStat(
        method="pearson",
        coefficient=0.8,
        effect_size=0.8,
        p_value=1e-9,
        p_adjusted=1e-8,
        n=100,
        significant=True,
    )


def test_verdict_valid():
    v = Verdict(
        x="a",
        y="b",
        verdict="confounder",
        confidence=0.7,
        confounder="z",
        confounder_in_data=True,
        reasoning="r",
        needed_data="n",
    )
    assert v.verdict == "confounder"
    assert v.ruled_out == []  # optional, defaults to empty


def test_verdict_accepts_ruled_out():
    v = Verdict(
        x="a", y="b", verdict="causal", confidence=0.9,
        reasoning="r", needed_data="n",
        ruled_out=[{"label": "chance", "why": "effect too strong"}],
    )
    assert v.ruled_out[0].label == "chance"
    assert v.ruled_out[0].why == "effect too strong"


def test_verdict_ruled_out_rejects_bad_label():
    with pytest.raises(ValidationError):
        Verdict(
            x="a", y="b", verdict="causal", confidence=0.9,
            reasoning="r", needed_data="n",
            ruled_out=[{"label": "not_a_category", "why": "x"}],
        )


def test_verdict_rejects_bad_label():
    with pytest.raises(ValidationError):
        Verdict(
            x="a", y="b", verdict="spurious", confidence=0.5,
            reasoning="r", needed_data="n",
        )


@pytest.mark.parametrize("bad", [-0.1, 1.1, 2.0])
def test_verdict_confidence_bounds(bad):
    with pytest.raises(ValidationError):
        Verdict(
            x="a", y="b", verdict="chance", confidence=bad,
            reasoning="r", needed_data="n",
        )


def test_pair_context_defaults():
    from engine.llm.base import ColumnInfo

    ctx = PairContext(
        x="a",
        y="b",
        dataset_description="d",
        x_info=ColumnInfo(name="a", dtype="numeric"),
        y_info=ColumnInfo(name="b", dtype="numeric"),
        stat=_stat(),
    )
    assert ctx.other_columns == []
    assert ctx.n_tested_pairs == 1


def test_analyze_response_roundtrip():
    pair = AnalysisPair(
        x="a",
        y="b",
        stat=_stat(),
        verdict=Verdict(
            x="a", y="b", verdict="causal", confidence=0.9,
            reasoning="r", needed_data="n",
        ),
        verification=VerificationResult(
            confounder="z", method="partial_pearson", r_before=0.8, r_after=0.02,
            p_after=0.5, n=100, threshold_abs=0.15, collapsed=True, note="ok",
        ),
        plot=PlotData(kind="scatter", x_label="a", y_label="b"),
    )
    resp = AnalyzeResponse(
        dataset="d.csv", description="x", n_tested_pairs=3, pairs=[pair]
    )
    # serialize and re-validate
    again = AnalyzeResponse.model_validate(resp.model_dump())
    assert again.pairs[0].verdict.verdict == "causal"
    assert again.pairs[0].verification.collapsed is True
