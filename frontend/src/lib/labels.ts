/** Human-readable German labels for the datacenter dataset columns.
 * Falls back to the raw name (underscores -> spaces) for unknown columns. */
const COLUMN_LABELS: Record<string, string> = {
  zeitstempel: "Zeitstempel",
  stunde: "Stunde (0 bis 23)",
  wochentag: "Wochentag (0 = Mo)",
  aktive_jobs: "Aktive Jobs",
  gpu_auslastung_pct: "GPU-Auslastung (%)",
  cpu_auslastung_pct: "CPU-Auslastung (%)",
  aussentemperatur_c: "Außentemperatur (°C)",
  it_stromverbrauch_kw: "IT-Stromverbrauch (kW)",
  kuehlung_stromverbrauch_kw: "Kühlungs-Stromverbrauch (kW)",
  gesamt_stromverbrauch_kw: "Gesamt-Stromverbrauch (kW)",
  serverraum_temp_c: "Serverraum-Temperatur (°C)",
  luefterdrehzahl_rpm: "Lüfterdrehzahl (U/min)",
  netzwerk_latenz_ms: "Netzwerk-Latenz (ms)",
};

export function columnLabel(name: string): string {
  return COLUMN_LABELS[name] ?? name.replace(/_/g, " ");
}

/** Short labels for tight spots (heatmap axes). Falls back to columnLabel. */
const COLUMN_SHORT: Record<string, string> = {
  stunde: "Stunde",
  wochentag: "Wochentag",
  aktive_jobs: "Jobs",
  gpu_auslastung_pct: "GPU %",
  cpu_auslastung_pct: "CPU %",
  aussentemperatur_c: "Außen °C",
  it_stromverbrauch_kw: "IT kW",
  kuehlung_stromverbrauch_kw: "Kühlung kW",
  gesamt_stromverbrauch_kw: "Gesamt kW",
  serverraum_temp_c: "Raum °C",
  luefterdrehzahl_rpm: "Lüfter",
  netzwerk_latenz_ms: "Latenz",
};

export function columnShort(name: string): string {
  return COLUMN_SHORT[name] ?? columnLabel(name);
}
