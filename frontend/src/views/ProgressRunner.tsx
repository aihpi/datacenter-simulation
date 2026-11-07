import type { ProgressEvent } from "../types";

interface ProgressRunnerProps {
  title: string;
  events: ProgressEvent[];
  error: string | null;
  onCancel: () => void;
  onRetry: () => void;
}

// Canonical pipeline stages, in order, with friendly German labels.
const STAGES: { id: string; label: string }[] = [
  { id: "profiling", label: "Spalten profilieren" },
  { id: "correlation", label: "Korrelationen berechnen" },
  { id: "fdr", label: "Multiples Testen korrigieren" },
  { id: "ranking", label: "Signifikante Paare wählen" },
  { id: "classify", label: "Ursachen einordnen" },
  { id: "done", label: "Fertig" },
];

export function ProgressRunner({
  title,
  events,
  error,
  onCancel,
  onRetry,
}: ProgressRunnerProps) {
  const last = events[events.length - 1];
  const percent = Math.round((last?.progress ?? 0) * 100);
  const activeStage = last?.stage ?? "profiling";
  const seen = new Set(events.map((e) => e.stage));
  const activeIdx = STAGES.findIndex((s) => s.id === activeStage);

  const stageStatus = (idx: number): "done" | "active" | "todo" => {
    if (error) return idx < activeIdx ? "done" : idx === activeIdx ? "active" : "todo";
    if (percent >= 100) return "done";
    if (idx < activeIdx) return "done";
    if (idx === activeIdx) return "active";
    // a later stage we've technically already passed events for
    return seen.has(STAGES[idx].id) ? "done" : "todo";
  };

  // last few log lines (most recent first)
  const log = events.slice(-6).reverse();

  return (
    <div className="progress-runner" data-testid="progress-runner">
      <div className="runner-head">
        <h2 className="section-title">{title}</h2>
        <p className="section-sub">
          {error
            ? "Die Analyse wurde abgebrochen."
            : percent >= 100
              ? "Ergebnisse werden geöffnet…"
              : "Analyse läuft, das passiert gerade im Hintergrund:"}
        </p>
      </div>

      <div className="progress-bar-wrap" data-testid="progress-bar">
        <div
          className={`progress-bar-fill ${error ? "is-error" : ""}`}
          style={{ width: `${error ? 100 : percent}%` }}
        />
        <span className="progress-bar-pct">{error ? "Fehler" : `${percent}%`}</span>
      </div>

      <ol className="stepper">
        {STAGES.map((s, idx) => {
          const status = stageStatus(idx);
          // show the live detail (e.g. "3/15", the current pair) on the active row
          const detail =
            status === "active" && last
              ? [last.detail, last.pair ? `${last.pair.x} ↔ ${last.pair.y}` : null]
                  .filter(Boolean)
                  .join(" · ")
              : null;
          return (
            <li key={s.id} className={`step step-${status}`} data-step={s.id}>
              <span className="step-marker" aria-hidden>
                {status === "done" ? "✓" : status === "active" ? "●" : "○"}
              </span>
              <span className="step-label">{s.label}</span>
              {detail && <span className="step-detail">{detail}</span>}
            </li>
          );
        })}
      </ol>

      {!error && (
        <ul className="runner-log" aria-live="polite">
          {log.map((e, i) => (
            <li key={`${e.stage}-${events.length - i}`} className="runner-log-line">
              {e.label}
              {e.detail ? `: ${e.detail}` : ""}
            </li>
          ))}
        </ul>
      )}

      {error && (
        <div className="state-msg state-error" data-testid="runner-error">
          {error}
          <button className="retry-btn" onClick={onRetry}>
            Erneut versuchen
          </button>
        </div>
      )}

      <div className="runner-actions">
        <button className="ghost-btn" onClick={onCancel}>
          ← Zurück zur Auswahl
        </button>
      </div>
    </div>
  );
}
