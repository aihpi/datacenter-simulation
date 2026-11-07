import { useEffect, useState } from "react";
import type { AnalyzeResponse } from "../types";
import { VerdictCard } from "../VerdictCard";
import { VERDICT_TEXT, headlineIndex, verdictCounts } from "../lib/verdicts";

interface ResultsViewProps {
  data: AnalyzeResponse;
  title: string;
  source: string;
  fromHistory?: boolean;
  onNew: () => void;
}

export function ResultsView({
  data,
  title,
  source,
  fromHistory,
  onNew,
}: ResultsViewProps) {
  const counts = verdictCounts(data.pairs);
  const dropped = data.dropped_columns ?? [];
  const verified = data.pairs.filter((p) => p.verification).length;
  // Pairs that were tested but did not surface (not significant / below the cap).
  const excludedPairs = Math.max(0, data.n_tested_pairs - data.pairs.length);

  // Feature the single most interesting finding; the rest are revealed on demand.
  const headIdx = headlineIndex(data.pairs);
  const headline = headIdx >= 0 ? data.pairs[headIdx] : null;
  const rest = data.pairs.filter((_, i) => i !== headIdx);

  const [showAll, setShowAll] = useState(false);
  // Collapse again whenever a new run / history entry is shown.
  useEffect(() => setShowAll(false), [data]);

  return (
    <div className="results-view" data-testid="results-view">
      <section className="results-summary">
        <div className="results-summary-head">
          <div>
            <h2 className="results-title">
              <span className="results-title-main">{title}</span>
              {fromHistory && <span className="history-badge">aus Verlauf</span>}
            </h2>
            <p className="results-desc">{data.description}</p>
          </div>
          <button className="primary-btn" onClick={onNew}>
            + Neue Analyse
          </button>
        </div>

        <div className="results-stats">
          <span className="stat-pill">
            <strong>{data.n_tested_pairs}</strong> Paare getestet
          </span>
          <span className="stat-pill">
            <strong>{data.pairs.length}</strong> relevante Zusammenhänge
          </span>
          {verified > 0 && (
            <span className="stat-pill">
              <strong>{verified}</strong> per Partialkorrelation geprüft
            </span>
          )}
          {excludedPairs > 0 && (
            <span
              className="stat-pill stat-pill-muted"
              title="Getestet, aber als nicht signifikant ausgeschlossen"
              data-testid="excluded-pairs"
            >
              <strong>{excludedPairs}</strong> ausgeschlossen
            </span>
          )}
          <span className="stat-pill stat-pill-muted">{source}</span>
        </div>

        <div className="verdict-legend" data-testid="verdict-legend">
          {counts.map(({ label, count }) => (
            <span key={label} className={`verdict-chip verdict-${label}`}>
              <span className="verdict-chip-count">{count}</span>
              {VERDICT_TEXT[label]}
            </span>
          ))}
        </div>

        {dropped.length > 0 && (
          <p className="dropped-note">
            Nicht analysiert ({dropped.length}):{" "}
            {dropped.map((d, i) => (
              <span key={d.name} className="dropped-col">
                {d.name}
                <span className="dropped-reason"> ({d.reason})</span>
                {i < dropped.length - 1 ? ", " : ""}
              </span>
            ))}
          </p>
        )}
      </section>

      {data.pairs.length === 0 ? (
        <div className="state-msg">
          Keine signifikanten Zusammenhänge gefunden.
        </div>
      ) : (
        <>
          <section className="headline-wrap" data-testid="headline">
            <div className="headline-tag">★ Wichtigster Befund</div>
            {headline && (
              <VerdictCard key={`${headline.x}-${headline.y}`} pair={headline} />
            )}
          </section>

          {rest.length > 0 && (
            <div className="more-section">
              <button
                className="show-more-btn"
                onClick={() => setShowAll((v) => !v)}
                aria-expanded={showAll}
                data-testid="toggle-more"
              >
                {showAll
                  ? "▾ Weitere Zusammenhänge ausblenden"
                  : `▸ ${rest.length} weitere ${
                      rest.length === 1 ? "Zusammenhang" : "Zusammenhänge"
                    } anzeigen`}
              </button>

              {showAll && (
                <main className="cards-grid" data-testid="more-cards">
                  {rest.map((pair, i) => (
                    <VerdictCard key={`${pair.x}-${pair.y}-${i}`} pair={pair} />
                  ))}
                </main>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
