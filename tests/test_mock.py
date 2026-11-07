"""MockLLMClient: deterministic, answer-key-correct, defaults unknown to chance."""

from __future__ import annotations

from engine.llm.base import ColumnInfo, CorrelationStat, PairContext
from engine.llm.mock import MockLLMClient


def _ctx(x: str, y: str, others: list[str] | None = None) -> PairContext:
    stat = CorrelationStat(
        method="pearson", coefficient=0.5, effect_size=0.5,
        p_value=0.001, p_adjusted=0.01, n=100, significant=True,
    )
    return PairContext(
        x=x,
        y=y,
        dataset_description="d",
        x_info=ColumnInfo(name=x, dtype="numeric"),
        y_info=ColumnInfo(name=y, dtype="numeric"),
        stat=stat,
        other_columns=others or [],
    )


def test_known_confounder_pair():
    m = MockLLMClient()
    v = m.classify(_ctx("ice_cream_sales", "drownings", ["temperature"]))
    assert v.verdict == "confounder"
    assert v.confounder == "temperature"
    assert v.confounder_in_data is True
    assert 0.0 <= v.confidence <= 1.0


def test_known_pair_is_order_insensitive():
    m = MockLLMClient()
    v = m.classify(_ctx("drownings", "ice_cream_sales"))
    assert v.verdict == "confounder"


def test_causal_and_selection_and_reverse():
    m = MockLLMClient()
    assert m.classify(_ctx("hours_studied", "exam_score")).verdict == "causal"
    assert m.classify(_ctx("talent", "looks")).verdict == "selection"
    assert (
        m.classify(_ctx("resting_heart_rate", "exercise_minutes")).verdict
        == "reverse_causal"
    )


def test_unknown_pair_defaults_to_chance():
    m = MockLLMClient()
    v = m.classify(_ctx("totally_unknown_a", "totally_unknown_b"))
    assert v.verdict == "chance"
    assert v.confidence < 0.5
    assert v.confounder is None


def test_deterministic():
    m = MockLLMClient()
    a = m.classify(_ctx("hours_studied", "exam_score"))
    b = m.classify(_ctx("hours_studied", "exam_score"))
    assert a.model_dump() == b.model_dump()


def test_custom_entries_injection():
    entries = [
        {"x": "p", "y": "q", "true_label": "causal", "confounder": None,
         "confounder_in_data": False, "notes": ""}
    ]
    m = MockLLMClient(entries=entries)
    assert m.classify(_ctx("p", "q")).verdict == "causal"
    assert m.classify(_ctx("x", "y")).verdict == "chance"


def test_ruled_out_covers_the_other_four_categories():
    m = MockLLMClient()
    v = m.classify(_ctx("ice_cream_sales", "drownings", ["temperature"]))
    labels = {r.label for r in v.ruled_out}
    assert len(v.ruled_out) == 4
    assert v.verdict not in labels  # never rules out its own verdict
    assert labels == {"causal", "reverse_causal", "selection", "chance"}
    assert all(r.why for r in v.ruled_out)  # every exclusion carries a reason


def test_unknown_pair_still_explains_exclusions():
    m = MockLLMClient()
    v = m.classify(_ctx("totally_unknown_a", "totally_unknown_b"))
    assert v.verdict == "chance"
    assert len(v.ruled_out) == 4
    # the reasoning is column-aware even for the chance default
    assert "totally_unknown_a" in v.reasoning


def test_reasoning_is_column_aware():
    m = MockLLMClient()
    v = m.classify(_ctx("ice_cream_sales", "drownings", ["temperature"]))
    assert "temperature" in v.reasoning  # names the in-data confounder


def test_label_can_override_reasoning_and_ruled_out():
    entries = [
        {
            "x": "p", "y": "q", "true_label": "confounder",
            "confounder": "z", "confounder_in_data": True,
            "confidence": 0.42,
            "reasoning": "CURATED REASONING",
            "needed_data": "CURATED NEEDED",
            "ruled_out": [{"label": "causal", "why": "CURATED WHY"}],
            "notes": "",
        }
    ]
    m = MockLLMClient(entries=entries)
    v = m.classify(_ctx("p", "q", ["z"]))
    assert v.reasoning == "CURATED REASONING"
    assert v.needed_data == "CURATED NEEDED"
    assert v.confidence == 0.42
    assert [(r.label, r.why) for r in v.ruled_out] == [("causal", "CURATED WHY")]


def test_ruled_out_is_deterministic():
    m = MockLLMClient()
    a = m.classify(_ctx("hours_studied", "exam_score"))
    b = m.classify(_ctx("hours_studied", "exam_score"))
    assert a.model_dump() == b.model_dump()
