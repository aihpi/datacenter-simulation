import type { RunRecord } from "../types";
import { VERDICT_TEXT, verdictCounts } from "../lib/verdicts";

interface HistoryViewProps {
  runs: RunRecord[];
  onOpen: (run: RunRecord) => void;
  onDelete: (id: string) => void;
  onClear: () => void;
  onNew: () => void;
}

function formatTime(ts: number): string {
  try {
    return new Date(ts).toLocaleString("de-DE", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return new Date(ts).toISOString();
  }
}

export function HistoryView({
  runs,
  onOpen,
  onDelete,
  onClear,
  onNew,
}: HistoryViewProps) {
  return (
    <div className="history-view" data-testid="history-view">
      <div className="history-head">
        <div>
          <h2 className="section-title">Verlauf</h2>
          <p className="section-sub">
            {runs.length === 0
              ? "Noch keine Analysen gespeichert."
              : `${runs.length} gespeicherte ${
                  runs.length === 1 ? "Analyse" : "Analysen"
                } (lokal in diesem Browser).`}
          </p>
        </div>
        {runs.length > 0 && (
          <button className="ghost-btn" onClick={onClear} data-testid="clear-history">
            Alle löschen
          </button>
        )}
      </div>

      {runs.length === 0 ? (
        <div className="history-empty">
          <button className="primary-btn" onClick={onNew}>
            Erste Analyse starten
          </button>
        </div>
      ) : (
        <ul className="history-list">
          {runs.map((run) => {
            const counts = verdictCounts(run.response.pairs);
            return (
              <li key={run.id} className="history-item" data-testid="history-item">
                <button
                  className="history-open"
                  onClick={() => onOpen(run)}
                  data-testid="history-open"
                >
                  <div className="history-item-head">
                    <span className="history-item-title">{run.title}</span>
                    <span className="history-item-time">{formatTime(run.ts)}</span>
                  </div>
                  <div className="history-item-meta">
                    {run.response.pairs.length} Zusammenhänge ·{" "}
                    {run.response.n_tested_pairs} Paare getestet
                  </div>
                  <div className="history-item-chips">
                    {counts.map(({ label, count }) => (
                      <span
                        key={label}
                        className={`verdict-chip verdict-chip-sm verdict-${label}`}
                      >
                        <span className="verdict-chip-count">{count}</span>
                        {VERDICT_TEXT[label]}
                      </span>
                    ))}
                  </div>
                </button>
                <button
                  className="history-delete"
                  onClick={() => onDelete(run.id)}
                  aria-label="Diesen Eintrag löschen"
                  data-testid="history-delete"
                >
                  ✕
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
