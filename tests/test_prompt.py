"""Prompt construction and defensive JSON extraction (used by the Vertex backend)."""

from __future__ import annotations

import pytest

from engine.llm.base import ColumnInfo, CorrelationStat, PairContext
from engine.llm.prompt import build_prompt, extract_json, parse_verdict


def _ctx() -> PairContext:
    return PairContext(
        x="ice_cream_sales",
        y="drownings",
        dataset_description="weather demo",
        x_info=ColumnInfo(name="ice_cream_sales", dtype="numeric"),
        y_info=ColumnInfo(name="drownings", dtype="numeric"),
        stat=CorrelationStat(
            method="pearson", coefficient=0.85, effect_size=0.85,
            p_value=1e-20, p_adjusted=1e-19, n=600, significant=True,
        ),
        other_columns=["temperature", "rand_a"],
        n_tested_pairs=120,
    )


def test_build_prompt_includes_key_signals():
    p = build_prompt(_ctx())
    assert "ice_cream_sales" in p and "drownings" in p
    assert "temperature" in p  # other columns listed
    assert "chance" in p  # taxonomy + selection-from-many prior
    assert "120" in p  # n_tested_pairs prior
    assert "JSON" in p
    assert "ruled_out" in p  # elimination list requested


def test_parse_verdict_reads_ruled_out():
    raw = (
        '{"verdict":"causal","confidence":0.9,"confounder":null,'
        '"confounder_in_data":false,"reasoning":"r","needed_data":"n",'
        '"ruled_out":[{"label":"chance","why":"effect strong"},'
        '{"label":"confounder","why":"no common cause"}]}'
    )
    v = parse_verdict(raw, _ctx())
    assert {r.label for r in v.ruled_out} == {"chance", "confounder"}


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_code_fence():
    raw = 'Here you go:\n```json\n{"verdict": "chance"}\n```\nthanks'
    assert extract_json(raw) == {"verdict": "chance"}


def test_extract_json_with_surrounding_prose():
    raw = 'The answer is {"verdict": "causal", "confidence": 0.9} ok?'
    assert extract_json(raw)["verdict"] == "causal"


def test_parse_verdict_backfills_xy():
    raw = '{"verdict":"confounder","confidence":0.8,"confounder":"temperature",' \
          '"confounder_in_data":true,"reasoning":"r","needed_data":"n"}'
    v = parse_verdict(raw, _ctx())
    assert v.x == "ice_cream_sales" and v.y == "drownings"
    assert v.verdict == "confounder"


def test_parse_verdict_rejects_garbage():
    with pytest.raises(Exception):
        parse_verdict("not json at all", _ctx())
