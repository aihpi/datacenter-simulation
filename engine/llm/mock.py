"""Deterministic mock LLM backend.

For labeled / fixture pairs it returns the ground-truth-correct Verdict (keyed by
the unordered (x, y) column pair). For any unknown pair it defaults to
verdict="chance" with low confidence. This makes the whole pipeline testable
offline and lets the pipeline/eval gates pass without a network.

Beyond the bare label, the mock now synthesises *grounded* reasoning and a full
``ruled_out`` elimination list for every pair, parametrised by the actual column
and confounder names. Curated label files may override any of these fields
(``reasoning``, ``needed_data``, ``confidence``, ``ruled_out``) to supply richer,
hand-written grounds — the more data stored alongside a pair, the better the
explanation the model can show.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.llm.base import VERDICT_LABELS, PairContext, RuledOut, Verdict, VerdictLabel

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _specific_reasoning(
    label: str, x: str, y: str, confounder: str | None, in_data: bool
) -> str:
    """Concrete, column-aware reasoning. Never invents numeric statistics."""
    z = confounder
    if label == "confounder" and z:
        where = "present in the data" if in_data else "not measured here"
        return (
            f"{x} and {y} most plausibly move together because both are driven by "
            f"{z} ({where}) — not because one causes the other. Controlling for "
            f"{z} should make the association largely disappear."
        )
    if label == "confounder":
        return (
            f"{x} and {y} most plausibly share a common cause rather than acting on "
            f"each other; the link should weaken once that third variable is held fixed."
        )
    if label == "causal":
        return (
            f"A direct mechanism from {x} to {y} is plausible and the effect is "
            f"strong, and no common cause among the other columns stands out."
        )
    if label == "reverse_causal":
        return (
            f"The dependency more plausibly runs from {y} to {x}, so the causal "
            f"arrow points back rather than forward."
        )
    if label == "selection":
        return (
            f"The {x}–{y} link looks like an artifact of how the sample was selected "
            f"(conditioning on a collider), not a real relationship."
        )
    return (
        f"The {x}–{y} association is weak and consistent with sampling noise once "
        f"multiple testing across all pairs is taken into account."
    )


_NEEDED = {
    "causal": "A randomized experiment that manipulates {x} and measures {y}.",
    "reverse_causal": "An intervention on {y} to confirm the direction of the effect.",
    "confounder": "{z} measured and controlled for (e.g. via partial correlation).",
    "selection": "The unselected population, or the rule that defined the sample.",
    "chance": "More data, or a pre-registered hypothesis linking {x} and {y}.",
}


def _specific_needed(label: str, x: str, y: str, confounder: str | None) -> str:
    z = confounder or "the common cause"
    return _NEEDED.get(label, _NEEDED["chance"]).format(x=x, y=y, z=z)


def _why_not(chosen: str, other: str, x: str, y: str, confounder: str | None) -> str:
    """One short clause explaining why `other` was rejected in favour of `chosen`."""
    z = confounder or "a common cause"
    table: dict[tuple[str, str], str] = {
        # chosen = confounder
        ("confounder", "causal"): f"A direct {x}→{y} effect is unlikely once {z} is recognised as driving both.",
        ("confounder", "reverse_causal"): f"Reversing the arrow ({y}→{x}) still wouldn't explain why both track {z}.",
        ("confounder", "selection"): "Both columns are full measurements, so a selection/collider artifact doesn't fit.",
        ("confounder", "chance"): "The association is too strong and systematic to be sampling noise.",
        # chosen = causal
        ("causal", "reverse_causal"): f"The plausible mechanism runs {x}→{y}, not {y}→{x}.",
        ("causal", "confounder"): f"No third variable stands out that would drive both {x} and {y}.",
        ("causal", "selection"): "Nothing about how the sample was built would manufacture this link.",
        ("causal", "chance"): "The effect is strong and survives multiple-testing correction, so not noise.",
        # chosen = reverse_causal
        ("reverse_causal", "causal"): f"{x}→{y} is the less plausible direction here.",
        ("reverse_causal", "confounder"): "No common driver explains the dependency better than direct reverse causation.",
        ("reverse_causal", "selection"): "The link isn't an artifact of sample selection.",
        ("reverse_causal", "chance"): "The relationship is too systematic to be chance.",
        # chosen = selection
        ("selection", "causal"): f"A direct {x}→{y} effect disappears outside the selected sample.",
        ("selection", "reverse_causal"): f"A reverse {y}→{x} effect also doesn't survive outside the selection.",
        ("selection", "confounder"): "No common cause is needed — conditioning on a collider induces the link.",
        ("selection", "chance"): "The pattern is systematic within the selected sample, not noise.",
        # chosen = chance
        ("chance", "causal"): f"No plausible direct {x}→{y} mechanism, and the effect is weak.",
        ("chance", "reverse_causal"): f"No plausible reverse {y}→{x} mechanism either.",
        ("chance", "confounder"): "No common cause stands out among the available columns.",
        ("chance", "selection"): "No selection rule obviously manufactures the association.",
    }
    return table.get((chosen, other), f"Less consistent with the evidence than {chosen}.")


def _auto_ruled_out(
    chosen: str, x: str, y: str, confounder: str | None
) -> list[RuledOut]:
    """Build a why-not for each of the four categories that were not chosen."""
    return [
        RuledOut(label=other, why=_why_not(chosen, other, x, y, confounder))
        for other in VERDICT_LABELS
        if other != chosen
    ]


def _key(x: str, y: str) -> frozenset[str]:
    return frozenset((x, y))


def _load_label_files() -> list[dict]:
    """Load ground_truth.json plus every *.label.json pair entry under
    fixtures/ and examples/ (the themed example bundles)."""
    entries: list[dict] = []
    gt = _DATA_DIR / "ground_truth.json"
    if gt.exists():
        entries.extend(json.loads(gt.read_text()))
    for subdir in ("fixtures", "examples"):
        root = _DATA_DIR / subdir
        if not root.exists():
            continue
        for label_file in sorted(root.rglob("*.label.json")):
            payload = json.loads(label_file.read_text())
            entries.extend(payload.get("pairs", []))
    return entries


class MockLLMClient:
    """Implements the LLMClient protocol deterministically from the answer key."""

    def __init__(self, entries: list[dict] | None = None) -> None:
        if entries is None:
            entries = _load_label_files()
        self._answers: dict[frozenset[str], dict] = {
            _key(e["x"], e["y"]): e for e in entries
        }

    def _ruled_out_from_entry(
        self, entry: dict, chosen: str, x: str, y: str, confounder: str | None
    ) -> list[RuledOut]:
        """Use curated ruled_out from the label if present, else auto-generate."""
        curated = entry.get("ruled_out")
        if curated:
            return [
                RuledOut(label=item["label"], why=item["why"])
                for item in curated
                if item.get("label") != chosen
            ]
        return _auto_ruled_out(chosen, x, y, confounder)

    def classify(self, ctx: PairContext) -> Verdict:
        x, y = ctx.x, ctx.y
        entry = self._answers.get(_key(x, y))

        if entry is None:
            # Unknown pair -> default to chance with low confidence, but still
            # spell out what was excluded so the card is never a dead end.
            return Verdict(
                x=x,
                y=y,
                verdict="chance",
                confidence=0.2,
                confounder=None,
                confounder_in_data=False,
                reasoning=_specific_reasoning("chance", x, y, None, False),
                needed_data=_specific_needed("chance", x, y, None),
                ruled_out=_auto_ruled_out("chance", x, y, None),
            )

        label: VerdictLabel = entry["true_label"]
        confounder = entry.get("confounder")
        in_data = bool(entry.get("confounder_in_data", False))
        confidence = float(
            entry.get("confidence", 0.9 if label != "chance" else 0.3)
        )
        reasoning = entry.get("reasoning") or _specific_reasoning(
            label, x, y, confounder, in_data
        )
        needed_data = entry.get("needed_data") or _specific_needed(
            label, x, y, confounder
        )
        ruled_out = self._ruled_out_from_entry(entry, label, x, y, confounder)

        return Verdict(
            x=x,
            y=y,
            verdict=label,
            confidence=confidence,
            confounder=confounder,
            confounder_in_data=in_data,
            reasoning=reasoning,
            needed_data=needed_data,
            ruled_out=ruled_out,
        )
