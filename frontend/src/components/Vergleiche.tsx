import {
  CO2_REFERENZEN,
  EINFAMILIENHAUS_ANNAHME,
  ERZEUGER,
  co2Menge,
  erzeugerLaufzeit,
  haushalte,
} from "../lib/vergleiche";
import { cn } from "@/lib/utils";

interface VergleicheProps {
  yearlyKwh: number;
  kgCo2: number;
  compact?: boolean;
}

export function Vergleiche({ yearlyKwh, kgCo2, compact }: VergleicheProps) {
  const erzeugung = [
    ...ERZEUGER.map((e) => ({
      key: e.key,
      value: erzeugerLaufzeit(yearlyKwh, e),
      label: `müsste ${e.label} laufen`,
      annahme: e.annahme,
    })),
    {
      key: "haushalte",
      value: haushalte(yearlyKwh),
      label: "Einfamilienhäuser ein Jahr lang versorgt",
      annahme: EINFAMILIENHAUS_ANNAHME,
    },
  ];
  const co2 = CO2_REFERENZEN.map((r) => ({
    key: r.key,
    value: co2Menge(kgCo2, r),
    label: r.label,
    annahme: r.annahme,
  }));

  return (
    <div className={cn("grid gap-4", compact ? "grid-cols-1" : "lg:grid-cols-2")}>
      <VergleichGruppe
        titel="Um diesen Strom zu erzeugen"
        items={erzeugung}
        compact={compact}
        testId="vergleich-erzeugung"
      />
      <VergleichGruppe
        titel="Das CO₂-Äquivalent entspricht"
        items={co2}
        compact={compact}
        testId="vergleich-co2"
      />
    </div>
  );
}

function VergleichGruppe({
  titel,
  items,
  compact,
  testId,
}: {
  titel: string;
  items: { key: string; value: string; label: string; annahme: string }[];
  compact?: boolean;
  testId: string;
}) {
  return (
    <div
      className={cn(
        "rounded-md border border-border bg-background",
        compact ? "p-3" : "p-4"
      )}
      data-testid={testId}
    >
      <div className="mb-2 text-sm font-medium text-foreground">{titel}</div>
      <dl
        className={cn(
          "grid grid-cols-[auto_1fr] gap-x-4 tabular-nums",
          compact ? "gap-y-1 text-sm" : "gap-y-1.5"
        )}
      >
        {items.map((item) => (
          <div key={item.key} className="contents">
            <dt
              className={cn(
                "text-right font-semibold text-foreground",
                compact ? "" : "text-base"
              )}
              title={item.annahme}
            >
              {item.value}
            </dt>
            <dd className="text-muted-foreground" title={item.annahme}>
              {item.label}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
