"""Seeded generator for themed, real-world EXAMPLE CSV bundles.

Each theme is a set of CSV files that share a key column, so the upload feature
can merge them and search for correlations ACROSS files. The causal structure is
built in on purpose (a confounder, a causal chain, a reverse-causal pair, ...) so
the verdicts are interpretable and make contextual sense.

Run: `uv run python data/generate_examples.py`
Writes: data/examples/<slug>/*.csv
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"


def _write(slug: str, files: dict[str, pd.DataFrame]) -> None:
    out = EXAMPLES_DIR / slug
    out.mkdir(parents=True, exist_ok=True)
    for name, df in files.items():
        df.to_csv(out / name, index=False)
    print(f"  {slug}/: {', '.join(files)}  ({len(next(iter(files.values())))} rows)")


def _causal(x: str, y: str) -> dict:
    return {"x": x, "y": y, "true_label": "causal", "confounder": None,
            "confounder_in_data": False, "notes": ""}


def _confounder(x: str, y: str, z: str, in_data: bool = True) -> dict:
    return {"x": x, "y": y, "true_label": "confounder", "confounder": z,
            "confounder_in_data": in_data, "notes": ""}


def _chance(x: str, y: str) -> dict:
    return {"x": x, "y": y, "true_label": "chance", "confounder": None,
            "confounder_in_data": False, "notes": ""}


def _write_labels(slug: str, pairs: list[dict]) -> None:
    """Answer key consumed by the mock LLM (keyed by the unordered column pair)."""
    out = EXAMPLES_DIR / slug / "answers.label.json"
    out.write_text(json.dumps({"pairs": pairs}, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Theme 1 — Eisdiele im Sommer  (classic confounder: temperature)
#   eis_verkauf  ~ temperatur ;  ertrinkungsunfaelle ~ badegaeste ~ temperatur
#   => eis_verkauf vs ertrinkungsunfaelle correlates, but collapses when you
#      control for temperatur. Key: datum.
# ---------------------------------------------------------------------------
def eisdiele() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(101)
    n = 180
    datum = pd.date_range("2025-04-01", periods=n, freq="D").strftime("%Y-%m-%d")

    # seasonal temperature curve + noise
    t = np.linspace(0, np.pi, n)
    temperatur = 12 + 16 * np.sin(t) + rng.normal(0, 2.0, n)
    sonnenstunden = np.clip(temperatur * 0.35 + rng.normal(0, 1.2, n), 0, 15)

    eis_verkauf = np.clip(35 * temperatur + rng.normal(0, 60, n), 0, None).round()
    kaltgetraenke = np.clip(22 * temperatur + rng.normal(0, 45, n), 0, None).round()
    badegaeste = np.clip(40 * temperatur + rng.normal(0, 90, n), 0, None).round()
    # drownings are driven by how many people are at the pool, not by ice cream
    ertrinkungsunfaelle = np.clip(
        0.012 * badegaeste + rng.normal(0, 1.0, n), 0, None
    ).round()

    return {
        "wetter.csv": pd.DataFrame(
            {"datum": datum, "temperatur_c": temperatur.round(1), "sonnenstunden": sonnenstunden.round(1)}
        ),
        "kiosk_verkauf.csv": pd.DataFrame(
            {"datum": datum, "eis_verkauf": eis_verkauf, "kaltgetraenke_verkauf": kaltgetraenke}
        ),
        "freibad.csv": pd.DataFrame(
            {"datum": datum, "badegaeste": badegaeste, "ertrinkungsunfaelle": ertrinkungsunfaelle}
        ),
    }


# ---------------------------------------------------------------------------
# Theme 2 — Online-Shop Marketing  (causal chain)
#   werbebudget -> besucher -> bestellungen -> umsatz ; newsletter -> besucher
#   Key: tag.
# ---------------------------------------------------------------------------
def online_shop() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(202)
    n = 150
    tag = np.arange(1, n + 1)

    werbebudget = np.clip(rng.normal(500, 180, n), 50, None).round()
    newsletter_versand = rng.integers(0, 5000, n)

    besucher = np.clip(
        2.1 * werbebudget + 0.18 * newsletter_versand + rng.normal(0, 120, n), 0, None
    ).round()
    verweildauer_min = np.clip(2.5 + rng.normal(0, 0.6, n), 0.5, None).round(2)

    bestellungen = np.clip(0.045 * besucher + rng.normal(0, 6, n), 0, None).round()
    umsatz_eur = np.clip(48 * bestellungen + rng.normal(0, 120, n), 0, None).round()

    return {
        "marketing.csv": pd.DataFrame(
            {"tag": tag, "werbebudget_eur": werbebudget, "newsletter_versand": newsletter_versand}
        ),
        "traffic.csv": pd.DataFrame(
            {"tag": tag, "besucher": besucher, "verweildauer_min": verweildauer_min}
        ),
        "umsatz.csv": pd.DataFrame(
            {"tag": tag, "bestellungen": bestellungen, "umsatz_eur": umsatz_eur}
        ),
    }


# ---------------------------------------------------------------------------
# Theme 3 — Gesundheit & Fitness  (reverse-causal + diet effect)
#   mehr sport -> niedrigerer ruhepuls ; mehr zucker -> mehr gewicht
#   Key: person_id.
# ---------------------------------------------------------------------------
def fitness() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(303)
    n = 220
    person_id = [f"P{1000 + i}" for i in range(n)]

    sport_minuten = np.clip(rng.normal(180, 90, n), 0, None).round()
    schritte = np.clip(4000 + 22 * sport_minuten + rng.normal(0, 1500, n), 0, None).round()

    ruhepuls = np.clip(78 - 0.06 * sport_minuten + rng.normal(0, 4, n), 40, 110).round()
    kalorien = np.clip(rng.normal(2200, 350, n), 1200, None).round()
    zucker_g = np.clip(0.03 * kalorien + rng.normal(0, 12, n), 0, None).round()
    gewicht_kg = np.clip(
        60 + 0.15 * zucker_g - 0.02 * sport_minuten + rng.normal(0, 6, n), 45, None
    ).round(1)

    return {
        "aktivitaet.csv": pd.DataFrame(
            {"person_id": person_id, "sport_minuten": sport_minuten, "schritte": schritte}
        ),
        "vitalwerte.csv": pd.DataFrame(
            {"person_id": person_id, "ruhepuls": ruhepuls, "gewicht_kg": gewicht_kg}
        ),
        "ernaehrung.csv": pd.DataFrame(
            {"person_id": person_id, "kalorien": kalorien, "zucker_g": zucker_g}
        ),
    }


# ---------------------------------------------------------------------------
# Theme 4 — Schule & Lernen  (straightforward causal)
#   lernstunden -> pruefungsnote ; anwesenheit hilft ; schlaf leicht positiv
#   Note: in DE sind kleinere Noten besser, daher negativer Zusammenhang.
#   Key: schueler_id.
# ---------------------------------------------------------------------------
def schule() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(404)
    n = 160
    schueler_id = [f"S{i:03d}" for i in range(1, n + 1)]

    # Hidden "Fleiß"/diligence factor (NOT exported) drives BOTH study hours and
    # attendance -> they correlate via a confounder that is not in the data.
    fleiss = rng.normal(0, 1, n)
    lernstunden = np.clip(8 + 3.0 * fleiss + rng.normal(0, 1.0, n), 0, None).round(1)
    anwesenheit_prozent = np.clip(86 + 7.0 * fleiss + rng.normal(0, 3.0, n), 40, 100).round()
    schlafstunden = np.clip(rng.normal(7, 1.0, n), 4, 11).round(1)

    # better (=lower) grade with more studying and attendance (sleep stays weak)
    note_roh = (
        5.2
        - 0.16 * lernstunden
        - 0.020 * anwesenheit_prozent
        - 0.04 * schlafstunden
        + rng.normal(0, 0.30, n)
    )
    pruefungsnote = np.clip(note_roh, 1.0, 6.0).round(1)

    return {
        "lernverhalten.csv": pd.DataFrame(
            {"schueler_id": schueler_id, "lernstunden": lernstunden, "schlafstunden": schlafstunden}
        ),
        "ergebnisse.csv": pd.DataFrame(
            {
                "schueler_id": schueler_id,
                "pruefungsnote": pruefungsnote,
                "anwesenheit_prozent": anwesenheit_prozent,
            }
        ),
    }


# ---------------------------------------------------------------------------
# Theme 5 — Rechenzentrum: Stromverbrauch  (physically grounded confounders)
#   aktive_jobs -> gpu_auslastung, cpu_auslastung -> it_stromverbrauch
#   it_stromverbrauch -> serverraum_temp -> luefterdrehzahl (Abwärme)
#   it_stromverbrauch + aussentemperatur -> kuehlung_stromverbrauch
#   => gpu ↔ cpu correlates (both driven by aktive_jobs); serverraum_temp ↔
#      kuehlung_stromverbrauch correlates (both driven by IT-Abwärme). Both
#      collapse when the common cause is controlled. Key: zeitstempel.
# ---------------------------------------------------------------------------
def rechenzentrum() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(505)
    n = 336  # 14 days, hourly
    zeit = pd.date_range("2026-01-01", periods=n, freq="h").strftime("%Y-%m-%d %H:%M")
    hour = np.arange(n) % 24

    # Exogenous workload with a daily cycle (afternoon peak).
    daily = np.sin((hour - 14) / 24 * 2 * np.pi)
    aktive_jobs = np.clip(120 + 60 * daily + rng.normal(0, 20, n), 0, None).round()

    # Compute load: GPU and CPU utilisation both driven by the job count
    # (=> they correlate with each other via a common cause, aktive_jobs).
    gpu_auslastung = np.clip(0.45 * aktive_jobs + rng.normal(0, 6, n), 0, 100).round(1)
    cpu_auslastung = np.clip(15 + 0.30 * aktive_jobs + rng.normal(0, 6, n), 0, 100).round(1)

    # IT power draw is caused by GPU+CPU utilisation.
    it_stromverbrauch = np.clip(
        40 + 1.1 * gpu_auslastung + 0.5 * cpu_auslastung + rng.normal(0, 4, n), 0, None
    ).round(1)

    # Waste heat raises the server-room temperature (climate-controlled: only the
    # IT load matters here, outside weather is decoupled).
    serverraum_temp = (19 + 0.06 * it_stromverbrauch + rng.normal(0, 0.4, n)).round(2)

    # Outside temperature: an independent daily curve.
    aussentemperatur = (8 + 6 * np.sin((hour - 15) / 24 * 2 * np.pi) + rng.normal(0, 1.5, n)).round(1)

    # Cooling power is driven by the IT heat load AND the outside temperature
    # (=> serverraum_temp ↔ kuehlung correlate via the shared IT-load cause).
    kuehlung_stromverbrauch = np.clip(
        10 + 0.35 * it_stromverbrauch + 0.6 * aussentemperatur + rng.normal(0, 2, n), 0, None
    ).round(1)

    # Fan speed follows the room temperature.
    luefterdrehzahl = np.clip(
        1500 + 90 * serverraum_temp + rng.normal(0, 120, n), 0, None
    ).round()

    # Pure-noise sensor: correlates with nothing (chance guard).
    netzwerk_latenz = np.clip(rng.normal(20, 5, n), 1, None).round(1)

    return {
        "server_last.csv": pd.DataFrame(
            {
                "zeitstempel": zeit,
                "aktive_jobs": aktive_jobs,
                "gpu_auslastung_pct": gpu_auslastung,
                "cpu_auslastung_pct": cpu_auslastung,
            }
        ),
        "energie.csv": pd.DataFrame(
            {
                "zeitstempel": zeit,
                "it_stromverbrauch_kw": it_stromverbrauch,
                "kuehlung_stromverbrauch_kw": kuehlung_stromverbrauch,
            }
        ),
        "umgebung.csv": pd.DataFrame(
            {
                "zeitstempel": zeit,
                "aussentemperatur_c": aussentemperatur,
                "serverraum_temp_c": serverraum_temp,
                "luefterdrehzahl_rpm": luefterdrehzahl,
                "netzwerk_latenz_ms": netzwerk_latenz,
            }
        ),
    }


# Answer keys (the KNOWN causal structure for each theme). Pairs are matched by
# unordered column name, so the same verdicts apply whether a theme is run as a
# curated topic or re-uploaded by the user.
def _labels_eisdiele() -> list[dict]:
    T, S, I, K, B, D = (
        "temperatur_c", "sonnenstunden", "eis_verkauf",
        "kaltgetraenke_verkauf", "badegaeste", "ertrinkungsunfaelle",
    )
    return [
        _causal(I, T), _causal(K, T), _causal(B, T), _causal(D, T),
        _causal(T, S), _causal(B, D),
        # everything driven by temperature -> confounded with each other
        _confounder(I, K, T), _confounder(B, I, T), _confounder(B, K, T),
        _confounder(D, K, T), _confounder(I, D, T), _confounder(K, S, T),
        _confounder(I, S, T), _confounder(B, S, T), _confounder(D, S, T),
    ]


def _labels_online_shop() -> list[dict]:
    W, N, V, O, U = (
        "werbebudget_eur", "newsletter_versand", "besucher",
        "bestellungen", "umsatz_eur",
    )
    # a clean causal chain W,N -> V -> O -> U (indirect links labelled causal)
    return [
        _causal(O, U), _causal(V, O), _causal(V, U), _causal(W, V),
        _causal(W, O), _causal(W, U), _causal(N, O), _causal(N, V), _causal(N, U),
    ]


def _labels_fitness() -> list[dict]:
    Sp, St, C, Z, R, G = (
        "sport_minuten", "schritte", "kalorien", "zucker_g",
        "ruhepuls", "gewicht_kg",
    )
    return [
        _causal(Sp, St), _causal(Sp, R), _causal(C, Z),
        _causal(Z, G), _causal(C, G), _causal(Sp, G),
        # steps & resting-pulse, steps & weight are confounded by exercise
        _confounder(St, R, Sp), _confounder(St, G, Sp),
        _chance(R, G),
    ]


def _labels_schule() -> list[dict]:
    P, A, L, Sl = (
        "pruefungsnote", "anwesenheit_prozent", "lernstunden", "schlafstunden",
    )
    return [
        _causal(P, L), _causal(P, A),
        # study-hours & attendance correlate via hidden diligence (not in data)
        _confounder(A, L, "Fleiß / Lerntyp", in_data=False),
        _chance(A, Sl),
    ]


def _labels_rechenzentrum() -> list[dict]:
    """Full answer key for all 36 column pairs.

    The load cascade  aktive_jobs -> {gpu,cpu} -> it_stromverbrauch ->
    {serverraum_temp -> luefterdrehzahl, kuehlung}  makes every column in the
    cascade correlate. Direct AND indirect (mediated) links count as causal
    (same convention as the online-shop chain). Three pairs are genuine
    common-cause confounders that collapse under partial correlation. The
    outside temperature only drives cooling; the network-latency sensor is noise.
    """
    J, G, C, IT, K, AT, RT, F, NL = (
        "aktive_jobs", "gpu_auslastung_pct", "cpu_auslastung_pct",
        "it_stromverbrauch_kw", "kuehlung_stromverbrauch_kw",
        "aussentemperatur_c", "serverraum_temp_c", "luefterdrehzahl_rpm",
        "netzwerk_latenz_ms",
    )
    # Common-cause confounders (neither variable causes the other).
    confounders = [_confounder(G, C, J), _confounder(RT, K, IT), _confounder(F, K, IT)]

    # Everything else inside the load cascade is a direct or mediated causal link.
    cascade = [J, G, C, IT, K, RT, F]
    confounded = {frozenset((G, C)), frozenset((RT, K)), frozenset((F, K))}
    causal = [
        _causal(a, b)
        for i, a in enumerate(cascade)
        for b in cascade[i + 1:]
        if frozenset((a, b)) not in confounded
    ]
    causal.append(_causal(AT, K))  # outside temperature drives cooling

    # Outside temperature is decoupled from the load; latency is pure noise.
    chance = [_chance(AT, v) for v in (J, G, C, IT, RT, F)]
    chance += [_chance(NL, v) for v in (J, G, C, IT, K, RT, F, AT)]

    return confounders + causal + chance


THEMES = {
    "eisdiele-sommer": (eisdiele, _labels_eisdiele),
    "online-shop": (online_shop, _labels_online_shop),
    "gesundheit-fitness": (fitness, _labels_fitness),
    "schule-lernen": (schule, _labels_schule),
    "rechenzentrum": (rechenzentrum, _labels_rechenzentrum),
}


def main() -> None:
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Writing example bundles to {EXAMPLES_DIR} ...")
    for slug, (data_fn, label_fn) in THEMES.items():
        _write(slug, data_fn())
        _write_labels(slug, label_fn())
    print("done.")


if __name__ == "__main__":
    main()
