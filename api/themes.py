"""Curated topics ("Themen") shown on the start screen.

A theme is either:
  * an "example" bundle — several CSVs under data/examples/<slug>/ that are
    merged on a shared key (cross-file correlation search), or
  * a "dataset" — a single CSV under data/ (the original samples/fixtures).

Resolving a theme returns a ready-to-analyze dataframe plus a label/description,
so the streaming endpoints treat every topic uniformly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from api.pipeline import DATA_DIR, combine_uploaded_frames, load_dataframe


@dataclass(frozen=True)
class Theme:
    slug: str
    title: str
    emoji: str
    summary: str
    kind: str  # "example" | "dataset"
    files: list[str] = field(default_factory=list)  # example: relative to slug dir
    dataset: str | None = None  # dataset: path relative to data/
    key_hint: str | None = None  # shown in UI; the shared key for example bundles
    top_k: int | None = None

    def to_public(self) -> dict:
        return {
            "slug": self.slug,
            "title": self.title,
            "emoji": self.emoji,
            "summary": self.summary,
            "kind": self.kind,
            "files": self.files,
            "key_hint": self.key_hint,
        }


THEMES: list[Theme] = [
    Theme(
        slug="eisdiele-sommer",
        title="Eisdiele im Sommer",
        emoji="🍦",
        summary=(
            "Wetter, Kiosk-Verkäufe und Freibad-Daten. Der Klassiker: Eisverkauf "
            "und Ertrinkungsunfälle korrelieren — aber die Temperatur ist die "
            "versteckte gemeinsame Ursache."
        ),
        kind="example",
        files=["wetter.csv", "kiosk_verkauf.csv", "freibad.csv"],
        key_hint="datum",
        top_k=15,
    ),
    Theme(
        slug="online-shop",
        title="Online-Shop Marketing",
        emoji="🛒",
        summary=(
            "Werbebudget, Traffic und Umsatz über drei Dateien. Eine saubere "
            "Wirkungskette: Werbung → Besucher → Bestellungen → Umsatz."
        ),
        kind="example",
        files=["marketing.csv", "traffic.csv", "umsatz.csv"],
        key_hint="tag",
        top_k=12,
    ),
    Theme(
        slug="gesundheit-fitness",
        title="Gesundheit & Fitness",
        emoji="🏃",
        summary=(
            "Aktivität, Vitalwerte und Ernährung pro Person. Sport senkt den "
            "Ruhepuls — und Schritte ↔ Ruhepuls werden von der Sportzeit "
            "konfundiert."
        ),
        kind="example",
        files=["aktivitaet.csv", "vitalwerte.csv", "ernaehrung.csv"],
        key_hint="person_id",
        top_k=12,
    ),
    Theme(
        slug="schule-lernen",
        title="Schule & Lernen",
        emoji="🎓",
        summary=(
            "Lernverhalten und Prüfungsergebnisse. Lernzeit und Anwesenheit "
            "korrelieren — über einen nicht erfassten Confounder (Fleiß)."
        ),
        kind="example",
        files=["lernverhalten.csv", "ergebnisse.csv"],
        key_hint="schueler_id",
        top_k=10,
    ),
    Theme(
        slug="rechenzentrum",
        title="Rechenzentrum: Stromverbrauch",
        emoji="🖥️",
        summary=(
            "Server-Last, Energie und Kühlung eines Rechenzentrums über drei "
            "Dateien. GPU- und CPU-Auslastung korrelieren (gemeinsame Ursache: "
            "aktive Jobs); Serverraum-Temperatur ↔ Kühlstrom korrelieren über die "
            "IT-Abwärme — beide brechen zusammen, wenn man die Ursache kontrolliert."
        ),
        kind="example",
        files=["server_last.csv", "energie.csv", "umgebung.csv"],
        key_hint="zeitstempel",
        top_k=22,
    ),
    Theme(
        slug="synthetic",
        title="Synthetischer Datensatz",
        emoji="🧪",
        summary=(
            "Großer Beispieldatensatz mit bekannter Kausalstruktur über alle "
            "Kategorien (kausal, umgekehrt, Confounder, Selektion, Zufall)."
        ),
        kind="dataset",
        dataset="synthetic.csv",
        top_k=12,
    ),
    Theme(
        slug="ice-cream-fixture",
        title="Eiscreme vs. Ertrinken (Mini)",
        emoji="🌡️",
        summary="Kleines Lehrbuch-Beispiel: der Temperatur-Confounder in 3 Spalten.",
        kind="dataset",
        dataset="fixtures/ice_cream_drownings.csv",
    ),
    Theme(
        slug="chocolate-nobel",
        title="Schokolade vs. Nobelpreise",
        emoji="🍫",
        summary="Berühmte Scheinkorrelation pro Land.",
        kind="dataset",
        dataset="fixtures/chocolate_nobel.csv",
    ),
    Theme(
        slug="storks-births",
        title="Störche vs. Geburten",
        emoji="🐣",
        summary="Der Lehrbuch-Klassiker zu „Korrelation ≠ Kausalität“.",
        kind="dataset",
        dataset="fixtures/storks_births.csv",
    ),
]

_BY_SLUG = {t.slug: t for t in THEMES}


def get_theme(slug: str) -> Theme | None:
    return _BY_SLUG.get(slug)


def resolve_theme(theme: Theme) -> tuple[pd.DataFrame, str, str, int | None]:
    """Return (df, dataset_label, description, top_k) ready for the pipeline."""
    if theme.kind == "dataset":
        assert theme.dataset is not None
        df, description, label = load_dataframe(theme.dataset, None, None)
        return df, label, description, theme.top_k

    # example bundle: read every listed CSV and combine (merge-on-key / align)
    base = DATA_DIR / "examples" / theme.slug
    frames: list[tuple[str, pd.DataFrame]] = []
    for name in theme.files:
        path = base / name
        if not path.exists():
            raise FileNotFoundError(f"Example file missing: {theme.slug}/{name}")
        frames.append((name, pd.read_csv(path)))
    df, combine_label, description = combine_uploaded_frames(frames)
    # Prefer the human theme title as the label; keep the "how combined" note in
    # the description so the merge/align detail isn't lost.
    label = f"{theme.emoji} {theme.title}"
    description = f"{description} [{combine_label}]"
    return df, label, description, theme.top_k
