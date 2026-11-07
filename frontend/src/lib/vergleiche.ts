const HOURS_PER_YEAR = 8760;

export interface Erzeuger {
  key: string;
  label: string;
  annahme: string;
  mittlereLeistungKw: number;
}

export const ERZEUGER: Erzeuger[] = [
  {
    key: "dach-pv",
    label: "eine Dach-Solaranlage (10 m²)",
    annahme: "2 kWp, 950 kWh je kWp und Jahr",
    mittlereLeistungKw: (2 * 950) / HOURS_PER_YEAR,
  },
  {
    key: "windturbine",
    label: "eine Onshore-Windturbine",
    annahme: "4 MW, 2.200 Volllaststunden je Jahr",
    mittlereLeistungKw: (4000 * 2200) / HOURS_PER_YEAR,
  },
  {
    key: "solarpark",
    label: "ein Solarpark",
    annahme: "10 MWp, 1.000 kWh je kWp und Jahr",
    mittlereLeistungKw: (10000 * 1000) / HOURS_PER_YEAR,
  },
  {
    key: "gaskraftwerk",
    label: "ein Gaskraftwerksblock",
    annahme: "400 MW unter Volllast",
    mittlereLeistungKw: 400000,
  },
];

export interface Co2Referenz {
  key: string;
  label: string;
  annahme: string;
  kgJeEinheit: number;
  einheit: string;
}

export const CO2_REFERENZEN: Co2Referenz[] = [
  {
    key: "golf-km",
    label: "Autokilometer (VW Golf Diesel)",
    annahme: "120 g CO₂ je km",
    kgJeEinheit: 0.12,
    einheit: "km",
  },
  {
    key: "a320-km",
    label: "Flugkilometer eines A320",
    annahme: "2,5 t Kerosin je Flugstunde bei 830 km/h, also etwa 9,5 kg CO₂ je km, ganzes Flugzeug",
    kgJeEinheit: 9.5,
    einheit: "km",
  },
  {
    key: "fluege-ber-pmi",
    label: "Flüge Berlin nach Palma (A320)",
    annahme: "1.600 km je Flug, ganzes Flugzeug etwa 15,2 t CO₂",
    kgJeEinheit: 15200,
    einheit: "Flüge",
  },
  {
    key: "emails",
    label: "gesendete E-Mails",
    annahme: "4 g CO₂e je E-Mail",
    kgJeEinheit: 0.004,
    einheit: "E-Mails",
  },
];

export const EINFAMILIENHAUS_KWH_JE_JAHR = 4000;
export const EINFAMILIENHAUS_ANNAHME =
  "Haushaltsstrom eines Einfamilienhauses mit 150 m², 4.000 kWh je Jahr";

export function erzeugerLaufzeit(yearlyKwh: number, erzeuger: Erzeuger): string {
  return dauer(yearlyKwh / erzeuger.mittlereLeistungKw);
}

export function haushalte(yearlyKwh: number): string {
  return anzahl(yearlyKwh / EINFAMILIENHAUS_KWH_JE_JAHR);
}

export function co2Menge(kgCo2: number, referenz: Co2Referenz): string {
  return `${anzahl(kgCo2 / referenz.kgJeEinheit)} ${referenz.einheit}`;
}

export function anzahl(v: number): string {
  const de = (x: number, d: number) =>
    x.toLocaleString("de-DE", { maximumFractionDigits: d });
  if (v >= 1e9) return `${de(v / 1e9, 2)} Mrd.`;
  if (v >= 1e6) return `${de(v / 1e6, 2)} Mio.`;
  if (v >= 10) return de(v, 0);
  return de(v, 2);
}

export function dauer(stunden: number): string {
  const de = (x: number, d: number) =>
    x.toLocaleString("de-DE", { maximumFractionDigits: d });
  if (stunden < 1) return `${de(stunden * 60, 0)} Minuten`;
  if (stunden < 48) return `${de(stunden, 1)} Stunden`;
  if (stunden < 24 * 60) return `${de(stunden / 24, 1)} Tage`;
  if (stunden < HOURS_PER_YEAR * 2) return `${de(stunden / (HOURS_PER_YEAR / 12), 1)} Monate`;
  return `${de(stunden / HOURS_PER_YEAR, 1)} Jahre`;
}
