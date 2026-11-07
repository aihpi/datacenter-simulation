"""Prompt construction and defensive JSON parsing shared by LLM backends."""

from __future__ import annotations

import json
import re

from engine.llm.base import VERDICT_LABELS, PairContext, Verdict

SYSTEM_PREAMBLE = (
    "You are a careful causal-inference assistant. You classify an observed "
    "statistical association between two columns into exactly one of five "
    "categories. You never fabricate statistics; you reason only from the "
    "information given."
)

TAXONOMY = (
    "- causal: X directly causes Y.\n"
    "- reverse_causal: Y directly causes X (the arrow points back).\n"
    "- confounder: a third variable Z causes both X and Y (X<-Z->Y).\n"
    "- selection: the association is an artifact of how the sample was selected "
    "or conditioned (a collider), not a real link.\n"
    "- chance: sampling noise; no real relationship.\n"
)


def build_prompt(ctx: PairContext) -> str:
    """Build the classification prompt. Forces the five-way taxonomy, the
    selection-from-many prior toward chance, a candidate confounder with an
    in-data flag, and a JSON-only response matching the Verdict schema."""

    def col_block(label: str, ci) -> str:
        units = f", units={ci.units}" if ci.units else ""
        samples = ", ".join(map(str, ci.sample_values[:5]))
        return (
            f"  {label}: name='{ci.name}', type={ci.dtype}{units}, "
            f"n_unique={ci.n_unique}, examples=[{samples}]"
        )

    stat = ctx.stat
    others = ", ".join(ctx.other_columns) if ctx.other_columns else "(none)"

    return f"""{SYSTEM_PREAMBLE}

Dataset: {ctx.dataset_description}

The pair under review:
{col_block("X", ctx.x_info)}
{col_block("Y", ctx.y_info)}

Measured association between X='{ctx.x}' and Y='{ctx.y}':
  method={stat.method}, coefficient={stat.coefficient:.4f}, n={stat.n},
  p_value={stat.p_value:.4g}, FDR_adjusted_p={stat.p_adjusted:.4g},
  survived_FDR={stat.significant}

Other columns available in the dataset (a confounder you name MAY be among these):
  {others}

IMPORTANT PRIOR: this pair was surfaced from {ctx.n_tested_pairs} tested pairs.
Many associations that survive screening are still spurious, so your prior should
lean toward 'chance' unless the evidence (effect size, plausibility, a concrete
mechanism or confounder) clearly supports something else.

Classify the association into exactly ONE of:
{TAXONOMY}

Rules:
- Always propose your single best candidate confounder (a real-world third
  variable). If none is plausible, set "confounder" to null.
- Set "confounder_in_data" to true ONLY if that confounder is among the listed
  "Other columns available" (match by name/meaning); otherwise false.
- "reasoning" must be at most 3 sentences and must not invent numeric statistics.
- "needed_data" states what you would need to be sure (an experiment, a control
  variable, the unselected population, etc.).
- "ruled_out" must contain EXACTLY ONE entry for EACH of the four categories you
  did NOT choose. Each entry is {{"label": <that category>, "why": <one short
  clause why it is less likely than your verdict>}}. Do not include your chosen
  verdict in "ruled_out".

Respond with JSON ONLY (no prose, no code fences), exactly this shape:
{{"x": "{ctx.x}", "y": "{ctx.y}", "verdict": <one of {list(VERDICT_LABELS)}>,
"confidence": <float 0..1>, "confounder": <string or null>,
"confounder_in_data": <true|false>, "reasoning": <string>,
"needed_data": <string>,
"ruled_out": [{{"label": <one of the other four>, "why": <string>}}, ...]}}
"""


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(raw: str) -> dict:
    """Strip code fences / surrounding prose and parse the first JSON object."""
    text = raw.strip()
    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()
    # Fall back to the outermost {...} span.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def parse_verdict(raw: str, ctx: PairContext) -> Verdict:
    """Parse model text into a validated Verdict, backfilling x/y from context."""
    data = extract_json(raw)
    data.setdefault("x", ctx.x)
    data.setdefault("y", ctx.y)
    return Verdict(**data)
