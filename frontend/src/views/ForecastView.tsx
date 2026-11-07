import { useEffect, useRef, useState } from "react";
import { Loader2, RotateCw } from "lucide-react";
import type {
  PredictResponse,
  SynthesizePreset,
  SynthesizeSpec,
} from "../types";
import { LineChart } from "../charts/LineChart";
import { PredictionBreakdown, type BreakdownItem } from "../charts/PredictionBreakdown";
import { columnLabel } from "../lib/labels";
import { SpecsPanel } from "./SpecsPanel";
import { InversePanel } from "./InversePanel";
import { Vergleiche } from "../components/Vergleiche";
import { cn, dez } from "@/lib/utils";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";

interface ForecastViewProps {
  data: PredictResponse | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  minCorrelation: number;
  onMinCorrelationChange: (value: number) => void;
  onToggleFeature: (name: string) => void;
  onTargetChange: (name: string) => void;
  onDownloadSynth: () => void;
  source: "seed" | "specs" | "upload";
  onSourceChange: (source: "seed" | "specs" | "upload") => void;
  spec: SynthesizeSpec;
  onSpecChange: (spec: SynthesizeSpec) => void;
  presets: SynthesizePreset[];
  onPickPreset: (slug: string) => void;
  synthLabel: string | null;
  synthLoading: boolean;
  synthError: string | null;
  onUpload: (files: File[]) => void;
  uploadLabel: string | null;
  uploadLoading: boolean;
  uploadError: string | null;
}

// Delay before a threshold-slider drag actually triggers a re-fit, so
// dragging doesn't fire a backend request per pixel.
const THRESHOLD_DEBOUNCE_MS = 400;

const DRIVER_THRESHOLD = 0.05; // std_importance above which a feature "drives"

const HOURS_PER_YEAR = 365 * 24;
const DEFAULT_PRICE_CT_PER_KWH = 30;
const DEFAULT_CO2_G_PER_KWH = 380;

// One weight row (h-8) plus the space-y-1 gap, and the two group labels around
// them — the fixed part of the influence list's height.
const WEIGHT_ROW_H = 36;
const WEIGHT_LIST_CHROME_H = 60;

function pct(v: number): string {
  return `${dez(v * 100, 1)} %`;
}
function num(v: number, digits = 2): string {
  return dez(v, digits);
}
function energy(kwh: number): string {
  const de = (v: number, d: number) =>
    v.toLocaleString("de-DE", { maximumFractionDigits: d });
  if (kwh >= 1e6) return `${de(kwh / 1e6, 2)} GWh`;
  if (kwh >= 1e3) return `${de(kwh / 1e3, 1)} MWh`;
  return `${de(kwh, 0)} kWh`;
}
function euro(v: number): string {
  return v.toLocaleString("de-DE", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  });
}
function tonnes(kg: number): string {
  return `${(kg / 1000).toLocaleString("de-DE", { maximumFractionDigits: 1 })} t CO₂e`;
}
function round1(v: number): number {
  return Math.round(v * 10) / 10;
}
function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

/** German wording for the /predict validation errors a user can actually
 *  trigger from this view; anything else is shown as the backend sent it. */
function errorText(message: string): string {
  if (message.includes("correlation threshold"))
    return "Keine Spalte erreicht diesen Schwellwert. Regler zurückziehen.";
  if (message.includes("accounting identity"))
    return "Übrig sind nur weitere Zähler derselben Größe; damit würde das Modell die Strombilanz nachrechnen statt vorhersagen.";
  if (message.includes("complete rows"))
    return "Zu wenige vollständige Zeilen, um ein Modell zu schätzen.";
  return message;
}

export function ForecastView({
  data,
  loading,
  error,
  onRetry,
  minCorrelation,
  onMinCorrelationChange,
  onToggleFeature,
  onTargetChange,
  onDownloadSynth,
  source,
  onSourceChange,
  spec,
  onSpecChange,
  presets,
  onPickPreset,
  synthLabel,
  synthLoading,
  synthError,
  onUpload,
  uploadLabel,
  uploadLoading,
  uploadError,
}: ForecastViewProps) {
  const [whatIf, setWhatIf] = useState<Record<string, number>>({});
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [priceCtPerKwh, setPriceCtPerKwh] = useState(DEFAULT_PRICE_CT_PER_KWH);
  const [co2GPerKwh, setCo2GPerKwh] = useState(DEFAULT_CO2_G_PER_KWH);
  const [thresholdDraft, setThresholdDraft] = useState(minCorrelation);
  const thresholdTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastDataKey = useRef<string | null>(null);

  useEffect(() => setThresholdDraft(minCorrelation), [minCorrelation]);

  useEffect(
    () => () => {
      if (thresholdTimer.current) clearTimeout(thresholdTimer.current);
    },
    []
  );

  const handleThresholdChange = (value: number) => {
    setThresholdDraft(value);
    if (thresholdTimer.current) clearTimeout(thresholdTimer.current);
    thresholdTimer.current = setTimeout(
      () => onMinCorrelationChange(value),
      THRESHOLD_DEBOUNCE_MS
    );
  };

  // Carry the what-if settings and the inspected hour across a re-fit of the
  // same data — they are the user's position in it, not a property of the
  // model. A different target or data source resets them to the new means.
  useEffect(() => {
    if (!data) return;
    const key = [
      data.target,
      data.n_train,
      data.n_test,
      data.candidates.map((c) => c.name).join(","),
    ].join("|");
    const sameData = lastDataKey.current === key;
    lastDataKey.current = key;

    setWhatIf((prev) =>
      Object.fromEntries(
        data.feature_stats.map((s) => [
          s.name,
          sameData
            ? clamp(prev[s.name] ?? round1(s.mean), s.min, s.max)
            : round1(s.mean),
        ])
      )
    );
    let peak = 0;
    data.series.forEach((p, i) => {
      if (p.predicted > data.series[peak].predicted) peak = i;
    });
    setSelectedIdx((prev) =>
      sameData && prev < data.series.length ? prev : peak
    );
  }, [data]);

  const specsPanel = (
    <SpecsPanel
      source={source}
      onSourceChange={onSourceChange}
      spec={spec}
      onSpecChange={onSpecChange}
      presets={presets}
      onPickPreset={onPickPreset}
      synthLabel={synthLabel}
      synthLoading={synthLoading}
      synthError={synthError}
      onUpload={onUpload}
      uploadLabel={uploadLabel}
      uploadLoading={uploadLoading}
      uploadError={uploadError}
      onDownloadSynth={onDownloadSynth}
    />
  );

  const inversePanel = (
    <InversePanel
      spec={spec}
      onApply={(next) => {
        onSpecChange(next);
        if (source !== "specs") onSourceChange("specs");
      }}
    />
  );

  const errorBanner = error && (
    <Alert variant="destructive" data-testid="forecast-error">
      <div className="flex-1">
        <AlertTitle>Vorhersage fehlgeschlagen</AlertTitle>
        <AlertDescription>
          {errorText(error)}
          {data && " Angezeigt wird der letzte erfolgreiche Fit."}
        </AlertDescription>
      </div>
      <Button variant="outline" size="sm" onClick={onRetry} className="self-center">
        <RotateCw className="h-3.5 w-3.5" />
        Erneut versuchen
      </Button>
    </Alert>
  );

  if (!data) {
    return (
      <div className="space-y-6" data-testid="forecast-view" aria-busy={loading}>
        {specsPanel}
        {inversePanel}
        {errorBanner}
        {!error && (
          <Card>
            <CardContent className="flex min-h-[9rem] items-center justify-center pt-5">
              {loading ? (
                <span
                  className="flex items-center gap-2 text-sm text-muted-foreground"
                  data-testid="forecast-loading"
                >
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Modell wird trainiert
                </span>
              ) : (
                <span className="max-w-prose text-center text-sm text-muted-foreground">
                  Noch keine Daten für eine Vorhersage. Wähle oben eine
                  Datenquelle: Seed-Datensatz, eigene CSV(s) oder ein aus Specs
                  generiertes Rechenzentrum.
                </span>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    );
  }

  const improvement = 1 - data.mae / data.baseline_mae;
  const maxImp = Math.max(...data.weights.map((w) => w.std_importance), 1e-9);
  const drivers = data.weights.filter((w) => w.std_importance >= DRIVER_THRESHOLD);
  const minor = data.weights.filter((w) => w.std_importance < DRIVER_THRESHOLD);
  const sorted = [...data.candidates].sort((a, b) => b.effect_size - a.effect_size);
  const driverCandidates = sorted.filter((c) => !c.same_measure);
  const meterCandidates = sorted.filter((c) => c.same_measure);
  const includedCount = data.candidates.filter((c) => c.included).length;

  const buildItems = (values: Record<string, number>): BreakdownItem[] => [
    { name: "Basis (Grundlast)", value: data.intercept },
    ...data.feature_stats.map((s) => ({
      name: columnLabel(s.name),
      value: s.coefficient * (values[s.name] ?? s.mean),
    })),
  ];
  const sum = (items: BreakdownItem[]) => items.reduce((a, b) => a + b.value, 0);

  const point = data.series[selectedIdx];
  const pointItems = point?.values ? buildItems(point.values) : [];
  const whatIfItems = buildItems(whatIf);
  const whatIfTotal = sum(whatIfItems);
  const baselineTotal = sum(
    buildItems(Object.fromEntries(data.feature_stats.map((s) => [s.name, s.mean])))
  );
  const priceEurPerKwh = priceCtPerKwh / 100;
  const yearlyKwh = whatIfTotal * HOURS_PER_YEAR;
  const yearlyCostEur = yearlyKwh * priceEurPerKwh;
  const yearlyCo2Kg = (yearlyKwh * co2GPerKwh) / 1000;
  const siteYearlyKwh = baselineTotal * HOURS_PER_YEAR;
  const siteYearlyCostEur = siteYearlyKwh * priceEurPerKwh;
  const siteYearlyCo2Kg = (siteYearlyKwh * co2GPerKwh) / 1000;
  // Reserve the chart height for every column the data could contribute, so a
  // re-fit with fewer features leaves the page height untouched.
  const breakdownRows = data.candidates.length + 1;

  const targets =
    data.available_targets.length > 0 ? data.available_targets : [data.target];

  return (
    <div className="space-y-6" data-testid="forecast-view" aria-busy={loading}>
      {specsPanel}
      {inversePanel}
      {errorBanner}

      <div
        className={cn(
          "space-y-6 transition-opacity duration-200",
          loading && "opacity-55"
        )}
      >
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1">
                <CardTitle>Stromverbrauchsvorhersage</CardTitle>
                <CardDescription>
                  Lineare Regression (kleinste Quadrate) sagt die Zielgröße aus den
                  übrigen numerischen Spalten voraus, bewertet auf einem zeitlich
                  getrennten Hold-out (die letzten Stunden, nicht trainiert).
                </CardDescription>
              </div>
              <div className="flex h-6 w-[8rem] shrink-0 items-center justify-end">
                {loading && (
                  <Badge variant="muted" data-testid="forecast-busy">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    rechnet
                  </Badge>
                )}
              </div>
            </div>
            <div className="flex flex-wrap gap-2 pt-2">
              <Badge variant="outline">
                Zielgröße: {columnLabel(data.target)}
              </Badge>
              <Badge variant="outline">Training: {data.n_train} h</Badge>
              <Badge variant="outline">Hold-out: {data.n_test} h</Badge>
              <Badge variant="outline">Merkmale: {data.features.length}</Badge>
            </div>
          </CardHeader>
        </Card>

        <Card data-testid="target-panel">
          <CardHeader>
            <CardTitle>Was soll vorhergesagt werden?</CardTitle>
            <CardDescription>
              Die Zielgröße des Modells. Bei eigenen CSVs wird automatisch eine
              plausible Spalte gewählt, bevorzugt der Gesamtzähler des
              Rechenzentrums. Hier lässt sie sich umstellen.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center gap-3">
              <Label htmlFor="forecast-target">Zielgröße</Label>
              <Select value={data.target} onValueChange={onTargetChange}>
                <SelectTrigger
                  id="forecast-target"
                  className="w-[22rem]"
                  data-testid="target-select"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {targets.map((name) => (
                    <SelectItem key={name} value={name}>
                      {columnLabel(name)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        <Card data-testid="features-panel">
          <CardHeader>
            <CardTitle>Welche Daten fließen ein?</CardTitle>
            <CardDescription>
              Spalten, deren Korrelation mit der Zielgröße den Schwellwert
              erreicht, werden automatisch aufgenommen. Per Checkbox lassen sich
              einzelne Spalten manuell hinzufügen oder entfernen.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="max-w-md space-y-1.5">
              <div className="flex h-4 items-baseline justify-between gap-2">
                <Label htmlFor="min-corr">Mindestkorrelation</Label>
                <span className="text-[0.7rem] tabular-nums text-muted-foreground">
                  |r| ≥ {dez(thresholdDraft, 2)}
                </span>
              </div>
              <div className="flex h-9 items-center">
                <Slider
                  id="min-corr"
                  min={0}
                  max={1}
                  step={0.05}
                  value={[thresholdDraft]}
                  onValueChange={([next]) => handleThresholdChange(next)}
                  aria-label="Mindestkorrelation"
                  data-testid="min-correlation-slider"
                />
              </div>
            </div>

            <div className="space-y-1">
              {driverCandidates.map((c) => (
                <FeatureRow
                  key={c.name}
                  name={c.name}
                  correlation={c.correlation}
                  checked={c.included}
                  lastIncluded={c.included && includedCount === 1}
                  onToggle={() => onToggleFeature(c.name)}
                />
              ))}
            </div>

            {meterCandidates.length > 0 && (
              <div className="space-y-1">
                <div className="pt-1">
                  <Label>Gleicher Zähler, nicht automatisch</Label>
                </div>
                {meterCandidates.map((c) => (
                  <FeatureRow
                    key={c.name}
                    name={c.name}
                    correlation={c.correlation}
                    checked={c.included}
                    lastIncluded={c.included && includedCount === 1}
                    muted
                    onToggle={() => onToggleFeature(c.name)}
                  />
                ))}
                <p className="max-w-prose pt-1 text-sm leading-relaxed text-muted-foreground">
                  Diese Spalten messen denselben Strom wie die Zielgröße (Gesamt =
                  IT + Kühlung). Nimmt man sie auf, rechnet das Modell diese
                  Bilanz nach (R² = 100 %, MAE = 0), statt etwas vorherzusagen,
                  und die echten Treiber bekommen Gewicht 0.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <div
          className="grid grid-cols-2 gap-4 lg:grid-cols-4"
          data-testid="forecast-metrics"
        >
          <MetricCard value={pct(data.r2)} label="R² (erklärte Varianz)" />
          <MetricCard value={num(data.mae)} label="MAE (kW)" />
          <MetricCard value={num(data.rmse)} label="RMSE (kW)" />
          <MetricCard
            value={pct(improvement)}
            label={`besser als Mittelwert-Baseline (${num(data.baseline_mae)} kW)`}
            accent
          />
        </div>

        <Card data-testid="site-yearly">
          <CardHeader>
            <CardTitle>Hochrechnung auf ein Jahr</CardTitle>
            <CardDescription>
              Durchschnittslast des Rechenzentrums ({num(baselineTotal, 1)} kW) × 365 × 24 h.
              Strompreis und Emissionsfaktor sind änderbar; die Annahmen hinter jedem
              Vergleich zeigt der Mauszeiger.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <MetricCard value={energy(siteYearlyKwh)} label="Stromverbrauch pro Jahr" />
              <MetricCard value={euro(siteYearlyCostEur)} label="Stromkosten pro Jahr" accent />
              <MetricCard value={tonnes(siteYearlyCo2Kg)} label="CO₂-Äquivalent pro Jahr" />
            </div>
            <Vergleiche yearlyKwh={siteYearlyKwh} kgCo2={siteYearlyCo2Kg} />
            <div className="grid max-w-md grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="price-ct-kwh" className="text-xs text-muted-foreground">
                  Strompreis (ct/kWh)
                </Label>
                <Input
                  id="price-ct-kwh"
                  type="number"
                  step="0.5"
                  min="0"
                  className="h-8"
                  value={priceCtPerKwh}
                  onChange={(e) => setPriceCtPerKwh(Number(e.target.value) || 0)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="co2-kwh" className="text-xs text-muted-foreground">
                  Emissionsfaktor (g CO₂e/kWh)
                </Label>
                <Input
                  id="co2-kwh"
                  type="number"
                  step="10"
                  min="0"
                  className="h-8"
                  value={co2GPerKwh}
                  onChange={(e) => setCo2GPerKwh(Number(e.target.value) || 0)}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-5">
            <div
              className="mb-2 flex flex-wrap items-center gap-4 text-xs text-muted-foreground"
              data-testid="forecast-legend"
            >
              <span className="flex items-center gap-2">
                <span className="inline-block h-0.5 w-5 bg-foreground" /> Ist
              </span>
              <span className="flex items-center gap-2">
                <span className="inline-block h-0.5 w-5 bg-primary" /> Vorhersage
              </span>
            </div>
            <LineChart points={data.series} yLabel={columnLabel(data.target)} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Wovon wird das Ergebnis beeinflusst?</CardTitle>
            <CardDescription>
              Standardisierte Einflussstärke |β·σₓ/σᵧ|, vergleichbar über Einheiten
              hinweg. Der Pfeil zeigt die Richtung, β den Effekt pro Einheit.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* Height reserved for every candidate column, so a re-fit with
                fewer features moves nothing below this card. */}
            <div
              className="space-y-1"
              style={{ minHeight: WEIGHT_ROW_H * data.candidates.length + WEIGHT_LIST_CHROME_H }}
            >
              <Label>Treibt das Ergebnis</Label>
              {drivers.map((w) => (
                <WeightRow key={w.name} {...w} maxImp={maxImp} />
              ))}
              <div className="pt-3">
                <Label>Kaum oder kein Einfluss</Label>
              </div>
              {minor.map((w) => (
                <WeightRow key={w.name} {...w} maxImp={maxImp} muted />
              ))}
            </div>
            <p
              className={cn(
                "max-w-prose pt-2 text-sm leading-relaxed text-muted-foreground",
                minor.length === 0 && "invisible"
              )}
            >
              Diese Größen bewegen die Vorhersage praktisch nicht, auch wenn sie
              (wie die Außentemperatur) mit dem Verbrauch korrelieren.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Woraus besteht eine einzelne Vorhersage?</CardTitle>
            <CardDescription>
              Jede Vorhersage ist Basis + Summe der Merkmalsbeiträge (β × Wert).
              Wähle eine Stunde aus dem Hold-out.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {point && (
              <>
                <div className="flex h-9 items-center">
                  <Slider
                    min={0}
                    max={Math.max(data.series.length - 1, 1)}
                    step={1}
                    value={[selectedIdx]}
                    onValueChange={([next]) => setSelectedIdx(next)}
                    aria-label="Stunde im Hold-out"
                    data-testid="point-slider"
                  />
                </div>
                <div className="flex h-5 flex-wrap items-center justify-between gap-3 text-sm tabular-nums text-muted-foreground">
                  <span>{point.label ?? `#${point.index}`}</span>
                  <span>
                    Ist <strong className="text-foreground">{num(point.actual, 1)}</strong>{" "}
                    kW, Vorhersage{" "}
                    <strong className="text-foreground">
                      {num(point.predicted, 1)}
                    </strong>{" "}
                    kW
                  </span>
                </div>
                <PredictionBreakdown items={pointItems} rows={breakdownRows} />
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Was-wäre-wenn</CardTitle>
            <CardDescription>
              Regler verschieben und sehen, wie die Vorhersage reagiert. Der Effekt
              eines Reglers zeigt, wie stark diese Größe den Verbrauch beeinflusst.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6 lg:grid-cols-2">
              <div className="space-y-1">
                {data.feature_stats.map((s) => {
                  const span = s.max - s.min || 1;
                  const value = whatIf[s.name] ?? s.mean;
                  return (
                    <div
                      key={s.name}
                      className="grid h-9 grid-cols-[minmax(7rem,11rem)_1fr_4.5rem] items-center gap-3"
                    >
                      <span className="truncate text-sm text-foreground">
                        {columnLabel(s.name)}
                      </span>
                      <Slider
                        min={s.min}
                        max={s.max}
                        step={span / 100}
                        value={[value]}
                        onValueChange={([next]) =>
                          setWhatIf((prev) => ({ ...prev, [s.name]: next }))
                        }
                        aria-label={columnLabel(s.name)}
                        data-testid={`whatif-${s.name}`}
                      />
                      <span className="text-right text-sm tabular-nums text-muted-foreground">
                        {num(value, 1)}
                      </span>
                    </div>
                  );
                })}
                <RowSpacer
                  rows={data.candidates.length - data.feature_stats.length}
                  height="h-9"
                />
              </div>
              <div className="rounded-lg border border-border bg-muted/40 p-4">
                <div
                  className="text-3xl font-semibold tabular-nums text-primary"
                  data-testid="whatif-pred"
                >
                  {num(whatIfTotal, 1)}{" "}
                  <span className="text-base font-medium text-muted-foreground">
                    kW
                  </span>
                </div>
                <div className="text-sm text-muted-foreground">
                  vorhergesagter Verbrauch
                </div>
                <div className="pt-1 text-sm tabular-nums text-muted-foreground">
                  {whatIfTotal >= baselineTotal ? "+" : "−"}
                  {num(Math.abs(whatIfTotal - baselineTotal), 1)} kW gegenüber
                  Durchschnitt ({num(baselineTotal, 1)} kW)
                </div>
                <div
                  className="mt-3 space-y-2 rounded-md border border-border bg-background p-3 text-sm"
                  data-testid="yearly-projection"
                >
                  <div className="font-medium text-foreground">
                    Hochrechnung auf ein Jahr (365 × 24 h)
                  </div>
                  <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 tabular-nums">
                    <dt className="text-muted-foreground">Energie</dt>
                    <dd className="text-right font-semibold text-foreground">
                      {energy(yearlyKwh)}
                    </dd>
                    <dt className="text-muted-foreground">Stromkosten</dt>
                    <dd className="text-right font-semibold text-foreground">
                      {euro(yearlyCostEur)}
                    </dd>
                    <dt className="text-muted-foreground">CO₂-Äquivalent</dt>
                    <dd className="text-right font-semibold text-foreground">
                      {tonnes(yearlyCo2Kg)}
                    </dd>
                  </dl>
                  <Vergleiche yearlyKwh={yearlyKwh} kgCo2={yearlyCo2Kg} compact />
                </div>
                <PredictionBreakdown items={whatIfItems} rows={breakdownRows} />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

/** Empty rows that hold the space of the columns currently not in the model, so
 *  toggling a feature does not shift everything below the list. */
function RowSpacer({ rows, height }: { rows: number; height: string }) {
  if (rows <= 0) return null;
  return (
    <>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className={height} aria-hidden="true" />
      ))}
    </>
  );
}

function MetricCard({
  value,
  label,
  accent,
}: {
  value: string;
  label: string;
  accent?: boolean;
}) {
  return (
    <Card
      className={cn(
        "flex h-[6.25rem] flex-col justify-center px-4",
        accent && "border-primary/25 bg-primary/5"
      )}
    >
      <div
        className={cn(
          "text-2xl font-semibold tabular-nums",
          accent ? "text-primary" : "text-foreground"
        )}
      >
        {value}
      </div>
      <div className="text-xs leading-snug text-muted-foreground">{label}</div>
    </Card>
  );
}

const FEATURE_GRID =
  "grid h-9 grid-cols-[1.25rem_minmax(8rem,13rem)_1fr_5rem] items-center gap-3";

function FeatureRow({
  name,
  correlation,
  checked,
  lastIncluded,
  muted,
  onToggle,
}: {
  name: string;
  correlation: number;
  checked: boolean;
  lastIncluded: boolean;
  muted?: boolean;
  onToggle: () => void;
}) {
  return (
    <div className={FEATURE_GRID} data-testid={`feature-${name}`}>
      <Checkbox
        checked={checked}
        disabled={lastIncluded}
        onCheckedChange={onToggle}
        id={`feature-${name}`}
        aria-label={columnLabel(name)}
      />
      <label
        htmlFor={`feature-${name}`}
        className={cn(
          "cursor-pointer truncate text-sm",
          muted ? "text-muted-foreground" : "text-foreground"
        )}
      >
        {columnLabel(name)}
      </label>
      <span className="relative h-2 w-full overflow-hidden rounded-full bg-muted">
        <span
          className={cn(
            "absolute inset-y-0 left-0 rounded-full",
            correlation >= 0 ? "bg-positive" : "bg-negative",
            muted && "opacity-45"
          )}
          style={{ width: `${Math.abs(correlation) * 100}%` }}
        />
      </span>
      <span className="text-right text-sm tabular-nums text-muted-foreground">
        r={correlation >= 0 ? "+" : ""}
        {dez(correlation, 2)}
      </span>
    </div>
  );
}

function WeightRow({
  name,
  coefficient,
  std_importance,
  maxImp,
  muted,
}: {
  name: string;
  coefficient: number;
  std_importance: number;
  maxImp: number;
  muted?: boolean;
}) {
  const width = `${(std_importance / maxImp) * 50}%`;
  return (
    <div
      className={cn(
        "grid h-8 grid-cols-[minmax(8rem,13rem)_5.5rem_1fr_4rem_5.5rem] items-center gap-3",
        muted && "opacity-70"
      )}
      data-testid={`weight-${name}`}
    >
      <span className="truncate text-sm text-foreground">{columnLabel(name)}</span>
      <span
        className={cn(
          "text-xs font-medium",
          coefficient >= 0 ? "text-positive" : "text-negative"
        )}
      >
        {coefficient >= 0 ? "↑ erhöht" : "↓ senkt"}
      </span>
      <span className="relative h-2 w-full rounded-full bg-muted">
        <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border" />
        <span
          className={cn(
            "absolute inset-y-0 rounded-full",
            coefficient >= 0 ? "bg-positive" : "bg-negative"
          )}
          style={coefficient >= 0 ? { left: "50%", width } : { right: "50%", width }}
        />
      </span>
      <span className="text-right text-sm tabular-nums text-muted-foreground">
        {dez(std_importance, 3)}
      </span>
      <span className="text-right text-xs tabular-nums text-muted-foreground">
        β={coefficient >= 0 ? "+" : ""}
        {dez(coefficient, 3)}
      </span>
    </div>
  );
}
