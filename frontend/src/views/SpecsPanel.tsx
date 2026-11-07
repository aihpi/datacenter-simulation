import { dez } from "@/lib/utils";
import { useId, type ReactNode } from "react";
import { Download, Loader2 } from "lucide-react";
import type {
  CoolingType,
  GpuType,
  InferencePhase,
  ModelArch,
  ModelClass,
  SynthesizePreset,
  SynthesizeSpec,
} from "../types";
import { GPU_IDLE, GPU_TDP } from "../lib/gpu";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface SpecsPanelProps {
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
  onDownloadSynth: () => void;
}

const COOLING_PUE: Record<CoolingType, number> = {
  luft: 1.5,
  warmwasser: 1.3,
  direktchip: 1.15,
  immersion: 1.08,
};

function defaultOccupancyChip(
  workload: SynthesizeSpec["workload"],
  modelClass: ModelClass,
  arch: ModelArch,
  phase: InferencePhase,
  moeAnteilPct: number,
  batchSize: number,
): { occupancy_pct: number; chip_load_pct: number } {
  const modelOcc = { klein: -12, "70b": 0, "120b": 10 }[modelClass];
  const modelChip = { klein: -3, "70b": 0, "120b": 3 }[modelClass];
  const anteil = Math.min(1, Math.max(0.01, moeAnteilPct / 100));
  const moe = arch === "moe" ? 8 * (1 - anteil) : 0;
  const batch = Math.max(batchSize, 1);
  const log2 = (n: number) => Math.log(n) / Math.log(2);
  if (workload === "training") {
    return {
      occupancy_pct: 100,
      chip_load_pct: Math.min(100, Math.max(20, 75 + modelChip + 2 * log2(batch / 64) - moe)),
    };
  }
  if (phase === "prefill") {
    return {
      occupancy_pct: Math.min(100, Math.max(20, 85 + modelOcc * 0.5)),
      chip_load_pct: Math.min(100, Math.max(20, 95 - moe + 2.5 * log2(batch / 8))),
    };
  }
  const sat = 1 - Math.exp(-batch / 16);
  return {
    occupancy_pct: Math.min(95, Math.max(15, 40 + modelOcc + 25 * sat)),
    chip_load_pct: Math.min(100, Math.max(20, 38 + 52 * sat - moe + modelChip)),
  };
}

/** One spec control. The fixed height keeps the grid from reflowing when a
 *  field switches between enabled and disabled. */
function SpecsField({
  label,
  hint,
  htmlFor,
  children,
}: {
  label: string;
  hint?: string;
  htmlFor?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex h-[3.75rem] flex-col justify-start gap-1.5">
      <div className="flex h-4 items-baseline justify-between gap-2">
        <Label htmlFor={htmlFor} className="truncate">
          {label}
        </Label>
        {hint && (
          <span className="shrink-0 text-[0.7rem] tabular-nums text-muted-foreground">
            {hint}
          </span>
        )}
      </div>
      <div className="flex h-9 items-center">{children}</div>
    </div>
  );
}

function SliderField({
  label,
  value,
  min,
  max,
  step,
  format,
  testId,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format: (n: number) => string;
  testId: string;
  disabled?: boolean;
  onChange: (n: number) => void;
}) {
  return (
    <SpecsField label={label} hint={format(value)}>
      <Slider
        min={min}
        max={max}
        step={step}
        value={[value]}
        disabled={disabled}
        onValueChange={([next]) => onChange(next)}
        aria-label={label}
        data-testid={testId}
      />
    </SpecsField>
  );
}

export function SpecsPanel({
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
  onDownloadSynth,
}: SpecsPanelProps) {
  const ids = useId();

  const applyProfile = (
    next: Partial<SynthesizeSpec> &
      Pick<
        SynthesizeSpec,
        | "workload"
        | "model_class"
        | "arch"
        | "inference_phase"
        | "moe_anteil_pct"
        | "batch_size"
      >,
  ) => {
    onSpecChange({
      ...spec,
      ...next,
      ...defaultOccupancyChip(
        next.workload,
        next.model_class,
        next.arch,
        next.inference_phase,
        next.moe_anteil_pct,
        next.batch_size,
      ),
    });
  };

  const profileBase = {
    workload: spec.workload,
    model_class: spec.model_class,
    arch: spec.arch,
    inference_phase: spec.inference_phase,
    moe_anteil_pct: spec.moe_anteil_pct,
    batch_size: spec.batch_size,
  };

  return (
    <Card data-testid="specs-panel">
      <CardHeader>
        <CardTitle>Datenquelle</CardTitle>
        <CardDescription>
          Seed-Datensatz nutzen, eigene CSV(s) mit echten Messwerten hochladen oder ein
          Rechenzentrum aus wenigen Specs synthetisieren, wenn keine echten Daten
          vorliegen.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Tabs
          value={source}
          onValueChange={(value) =>
            onSourceChange(value as "seed" | "specs" | "upload")
          }
        >
          <TabsList aria-label="Datenquelle">
            <TabsTrigger value="seed" data-testid="source-seed">
              Seed-Datensatz
            </TabsTrigger>
            <TabsTrigger value="upload" data-testid="source-upload">
              Eigene CSV(s) hochladen
            </TabsTrigger>
            <TabsTrigger value="specs" data-testid="source-specs">
              Aus Specs generieren
            </TabsTrigger>
          </TabsList>
        </Tabs>

        {source === "upload" && (
          <div className="space-y-3">
            <Input
              type="file"
              accept=".csv"
              multiple
              data-testid="specs-upload-input"
              className={
                "h-auto cursor-pointer py-1.5 file:mr-3 file:cursor-pointer " +
                "file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-1.5 " +
                "file:text-sm file:font-medium file:text-secondary-foreground"
              }
              onChange={(e) => {
                const files = Array.from(e.target.files ?? []);
                if (files.length > 0) onUpload(files);
              }}
            />
            <p className="text-sm leading-relaxed text-muted-foreground">
              Eine oder mehrere CSVs mit numerischen Spalten (z.&nbsp;B.
              Stromverbrauch, GPU-/CPU-Auslastung). Mehrere Dateien werden über
              eine gemeinsame Schlüsselspalte zusammengeführt, sonst zeilenweise
              ausgerichtet.
            </p>
            <StatusSlot
              loading={uploadLoading}
              loadingText="lädt"
              error={uploadError}
              errorPrefix="Upload fehlgeschlagen."
              errorTestId="upload-error"
              label={uploadLabel}
              labelTestId="upload-summary"
            />
          </div>
        )}

        {source === "specs" && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
              {presets.map((p) => (
                <Button
                  key={p.slug}
                  variant="outline"
                  className="h-auto flex-col items-start gap-0.5 px-3 py-2 text-left"
                  onClick={() => onPickPreset(p.slug)}
                  data-testid={`preset-${p.slug}`}
                  title={p.label}
                >
                  <span className="text-sm font-semibold">{p.name}</span>
                  <span className="w-full truncate text-xs font-normal text-muted-foreground">
                    {p.label}
                  </span>
                </Button>
              ))}
            </div>

            <div className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2 xl:grid-cols-3">
              <SpecsField label="Anzahl GPUs" htmlFor={`${ids}-gpus`}>
                <Input
                  id={`${ids}-gpus`}
                  type="number"
                  min={1}
                  step={1000}
                  value={spec.n_gpus}
                  onChange={(e) =>
                    onSpecChange({
                      ...spec,
                      n_gpus: Math.max(1, Number(e.target.value) || 1),
                    })
                  }
                  className="tabular-nums"
                  data-testid="spec-n-gpus"
                />
              </SpecsField>

              <SpecsField label="GPU-Typ">
                <Select
                  value={spec.gpu_type}
                  onValueChange={(value) => {
                    const gpu_type = value as GpuType;
                    onSpecChange({
                      ...spec,
                      gpu_type,
                      tdp_w: GPU_TDP[gpu_type],
                      idle_w: GPU_IDLE[gpu_type],
                    });
                  }}
                >
                  <SelectTrigger aria-label="GPU-Typ" data-testid="spec-gpu-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="l40s">L40S (350 W)</SelectItem>
                    <SelectItem value="a100">A100 (400 W)</SelectItem>
                    <SelectItem value="h100">H100 (700 W)</SelectItem>
                    <SelectItem value="h200">H200 (700 W)</SelectItem>
                    <SelectItem value="b200">B200 (1000 W)</SelectItem>
                  </SelectContent>
                </Select>
              </SpecsField>

              <SliderField
                label="TDP pro GPU"
                value={spec.tdp_w}
                min={200}
                max={1500}
                step={25}
                format={(n) => `${n.toFixed(0)} W`}
                testId="spec-tdp-w"
                onChange={(tdp_w) => onSpecChange({ ...spec, tdp_w })}
              />

              <SliderField
                label="Leerlauf pro GPU"
                value={spec.idle_w}
                min={20}
                max={250}
                step={5}
                format={(n) => `${n.toFixed(0)} W`}
                testId="spec-idle-w"
                onChange={(idle_w) => onSpecChange({ ...spec, idle_w })}
              />

              <SpecsField label="Workload">
                <Select
                  value={spec.workload}
                  onValueChange={(value) =>
                    applyProfile({
                      ...profileBase,
                      workload: value as SynthesizeSpec["workload"],
                    })
                  }
                >
                  <SelectTrigger aria-label="Workload" data-testid="spec-workload">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="training">Training</SelectItem>
                    <SelectItem value="inference">Inference</SelectItem>
                  </SelectContent>
                </Select>
              </SpecsField>

              <SpecsField label="Modellklasse">
                <Select
                  value={spec.model_class}
                  onValueChange={(value) =>
                    applyProfile({ ...profileBase, model_class: value as ModelClass })
                  }
                >
                  <SelectTrigger
                    aria-label="Modellklasse"
                    data-testid="spec-model-class"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="klein">klein (7B-Klasse)</SelectItem>
                    <SelectItem value="70b">70B</SelectItem>
                    <SelectItem value="120b">120B</SelectItem>
                  </SelectContent>
                </Select>
              </SpecsField>

              <SpecsField label="Architektur">
                <Select
                  value={spec.arch}
                  onValueChange={(value) =>
                    applyProfile({ ...profileBase, arch: value as ModelArch })
                  }
                >
                  <SelectTrigger aria-label="Architektur" data-testid="spec-arch">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="dense">dicht</SelectItem>
                    <SelectItem value="moe">MoE</SelectItem>
                  </SelectContent>
                </Select>
              </SpecsField>

              <SpecsField
                label="Inference-Phase"
                hint={spec.workload === "training" ? "nur bei Inference" : undefined}
              >
                <Select
                  value={spec.inference_phase}
                  disabled={spec.workload === "training"}
                  onValueChange={(value) =>
                    applyProfile({
                      ...profileBase,
                      inference_phase: value as InferencePhase,
                    })
                  }
                >
                  <SelectTrigger
                    aria-label="Inference-Phase"
                    data-testid="spec-phase"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="decode">Chat (Decode)</SelectItem>
                    <SelectItem value="prefill">Langer Prefill</SelectItem>
                  </SelectContent>
                </Select>
              </SpecsField>

              <SliderField
                label="MoE-Anteil aktiv"
                value={spec.moe_anteil_pct}
                min={1}
                max={50}
                step={0.5}
                format={(n) =>
                  spec.arch === "moe" ? `${dez(n, 1)} %` : "nur bei MoE"
                }
                testId="spec-moe-anteil"
                disabled={spec.arch !== "moe"}
                onChange={(moe_anteil_pct) =>
                  applyProfile({ ...profileBase, moe_anteil_pct })
                }
              />

              <SpecsField label="Batchgröße" htmlFor={`${ids}-batch`}>
                <Input
                  id={`${ids}-batch`}
                  type="number"
                  min={1}
                  max={65536}
                  step={1}
                  value={spec.batch_size}
                  onChange={(e) =>
                    applyProfile({
                      ...profileBase,
                      batch_size: Math.max(1, Number(e.target.value) || 1),
                    })
                  }
                  className="tabular-nums"
                  data-testid="spec-batch-size"
                />
              </SpecsField>

              <SliderField
                label="Belegung"
                value={spec.occupancy_pct}
                min={5}
                max={100}
                step={1}
                format={(n) => `${n.toFixed(0)} %`}
                testId="spec-occupancy"
                onChange={(occupancy_pct) => onSpecChange({ ...spec, occupancy_pct })}
              />

              <SliderField
                label="Kartenlast"
                value={spec.chip_load_pct}
                min={20}
                max={100}
                step={1}
                format={(n) => `${n.toFixed(0)} % TDP`}
                testId="spec-chip-load"
                onChange={(chip_load_pct) => onSpecChange({ ...spec, chip_load_pct })}
              />

              <SpecsField label="Kühlung">
                <Select
                  value={spec.cooling}
                  onValueChange={(value) => {
                    const cooling = value as CoolingType;
                    onSpecChange({ ...spec, cooling, pue: COOLING_PUE[cooling] });
                  }}
                >
                  <SelectTrigger aria-label="Kühlung" data-testid="spec-cooling">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="luft">Luft</SelectItem>
                    <SelectItem value="warmwasser">Warmwasser</SelectItem>
                    <SelectItem value="direktchip">Direktchip</SelectItem>
                    <SelectItem value="immersion">Immersion</SelectItem>
                  </SelectContent>
                </Select>
              </SpecsField>

              <SliderField
                label="PUE"
                value={spec.pue}
                min={1}
                max={2}
                step={0.05}
                format={(n) => dez(n, 2)}
                testId="spec-pue"
                onChange={(pue) => onSpecChange({ ...spec, pue })}
              />

              <SpecsField label="Klima">
                <Select
                  value={spec.climate}
                  onValueChange={(value) =>
                    onSpecChange({
                      ...spec,
                      climate: value as SynthesizeSpec["climate"],
                    })
                  }
                >
                  <SelectTrigger aria-label="Klima" data-testid="spec-climate">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="kalt">kalt</SelectItem>
                    <SelectItem value="gemaessigt">gemäßigt</SelectItem>
                    <SelectItem value="warm">warm</SelectItem>
                  </SelectContent>
                </Select>
              </SpecsField>
            </div>

            <p className="text-sm leading-relaxed text-muted-foreground">
              IT = n × (Leerlauf + (TDP − Leerlauf) × Belegung × Kartenlast).
              Belegung = Anteil beschäftigter Karten, Kartenlast = Anteil der TDP,
              den eine beschäftigte Karte zieht. Workload, Phase, Architektur, MoE-Anteil, Batch und
              Modell setzen nur die Startwerte. MoE-Anteil = aktive Experten /
              Experten gesamt (z.&nbsp;B. 8/64 = 12,5&nbsp;%). Batch = Samples
              je GPU (Training) bzw. parallele Sequenzen (Inference).
            </p>

            <StatusSlot
              loading={synthLoading}
              loadingText="generiert"
              error={synthError}
              errorPrefix="Synthese fehlgeschlagen."
              errorTestId="specs-error"
              label={synthLabel}
              labelTestId="specs-summary"
              action={
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onDownloadSynth}
                  data-testid="specs-download"
                >
                  <Download className="h-3.5 w-3.5" />
                  Als CSV speichern
                </Button>
              }
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** Fixed-height slot for the "generating / failed / ready" line, so the panel
 *  below it never moves while a request is in flight. */
function StatusSlot({
  loading,
  loadingText,
  error,
  errorPrefix,
  errorTestId,
  label,
  labelTestId,
  action,
}: {
  loading: boolean;
  loadingText: string;
  error: string | null;
  errorPrefix: string;
  errorTestId: string;
  label: string | null;
  labelTestId: string;
  action?: ReactNode;
}) {
  if (error && !loading) {
    return (
      <Alert variant="destructive" className="min-h-9 items-center">
        <AlertDescription data-testid={errorTestId}>
          {errorPrefix} {error}
        </AlertDescription>
      </Alert>
    );
  }
  return (
    <div className="flex min-h-9 flex-wrap items-center gap-3">
      {label && (
        <span
          className="text-sm font-medium tabular-nums text-foreground"
          data-testid={labelTestId}
        >
          {label}
        </span>
      )}
      {loading ? (
        <span className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          {loadingText}
        </span>
      ) : (
        label && action
      )}
    </div>
  );
}
