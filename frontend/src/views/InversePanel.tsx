import { useId, useState } from "react";
import type { GpuType, SynthesizeSpec } from "../types";
import { GPU_IDLE, GPU_TDP } from "../lib/gpu";
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

const HOURS_PER_YEAR = 8760;
const DEFAULT_YEARLY_MWH = 360;

const GPU_OPTIONS: { value: GpuType; label: string }[] = [
  { value: "l40s", label: "L40S (350 W)" },
  { value: "a100", label: "A100 (400 W)" },
  { value: "h100", label: "H100 (700 W)" },
  { value: "h200", label: "H200 (700 W)" },
  { value: "b200", label: "B200 (1000 W)" },
];

interface InversePanelProps {
  spec: SynthesizeSpec;
  onApply: (spec: SynthesizeSpec) => void;
}

function inverseGpuCount(
  yearlyMwh: number,
  gpuType: GpuType,
  pue: number,
  occupancyPct: number,
  chipLoadPct: number
): number {
  const meanTotalKw = (yearlyMwh * 1000) / HOURS_PER_YEAR;
  const meanItKw = meanTotalKw / Math.max(pue, 1);
  const utilization = Math.min(1, Math.max(0.02, (occupancyPct / 100) * (chipLoadPct / 100)));
  const idleKw = GPU_IDLE[gpuType] / 1000;
  const tdpKw = GPU_TDP[gpuType] / 1000;
  const kwPerGpu = idleKw + (tdpKw - idleKw) * utilization;
  return Math.max(1, Math.round(meanItKw / kwPerGpu));
}

export function InversePanel({ spec, onApply }: InversePanelProps) {
  const ids = useId();
  const [yearlyMwh, setYearlyMwh] = useState(DEFAULT_YEARLY_MWH);
  const [gpuType, setGpuType] = useState<GpuType>(spec.gpu_type);
  const [pue, setPue] = useState(spec.pue);

  const nGpus = inverseGpuCount(
    yearlyMwh,
    gpuType,
    pue,
    spec.occupancy_pct,
    spec.chip_load_pct
  );
  const de = (v: number) => v.toLocaleString("de-DE", { maximumFractionDigits: 0 });

  return (
    <Card data-testid="inverse-panel">
      <CardHeader>
        <CardTitle>Inverse Auslegung</CardTitle>
        <CardDescription>
          Jahresstromverbrauch und GPU-Typ vorgeben: Wie viele GPUs könnte ein
          solches Rechenzentrum haben? Rechnet mit Belegung {spec.occupancy_pct} % und
          Kartenlast {spec.chip_load_pct} % aus den Specs.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-1 items-end gap-4 sm:grid-cols-2 xl:grid-cols-[1fr_1fr_1fr_auto_auto]">
        <div className="space-y-1.5">
          <Label htmlFor={`${ids}-mwh`}>Stromverbrauch pro Jahr (MWh)</Label>
          <Input
            id={`${ids}-mwh`}
            type="number"
            min={1}
            step={10}
            value={yearlyMwh}
            onChange={(e) => setYearlyMwh(Math.max(1, Number(e.target.value) || 1))}
            data-testid="inverse-mwh"
          />
        </div>
        <div className="space-y-1.5">
          <Label>GPU-Typ</Label>
          <Select value={gpuType} onValueChange={(v) => setGpuType(v as GpuType)}>
            <SelectTrigger aria-label="GPU-Typ (invers)" data-testid="inverse-gpu-type">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {GPU_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${ids}-pue`}>PUE</Label>
          <Input
            id={`${ids}-pue`}
            type="number"
            min={1}
            max={3}
            step={0.05}
            value={pue}
            onChange={(e) => setPue(Math.min(3, Math.max(1, Number(e.target.value) || 1)))}
            data-testid="inverse-pue"
          />
        </div>
        <div className="rounded-md border border-primary/25 bg-primary/5 px-4 py-2">
          <div className="text-2xl font-semibold tabular-nums text-primary" data-testid="inverse-gpus">
            {de(nGpus)}
          </div>
          <div className="text-xs text-muted-foreground">
            {GPU_OPTIONS.find((o) => o.value === gpuType)?.label.split(" (")[0]} bei{" "}
            {de((yearlyMwh * 1000) / HOURS_PER_YEAR)} kW Dauerlast
          </div>
        </div>
        <Button
          variant="outline"
          onClick={() =>
            onApply({
              ...spec,
              n_gpus: nGpus,
              gpu_type: gpuType,
              tdp_w: GPU_TDP[gpuType],
              idle_w: GPU_IDLE[gpuType],
              pue,
            })
          }
          data-testid="inverse-apply"
        >
          In Specs übernehmen
        </Button>
      </CardContent>
    </Card>
  );
}
