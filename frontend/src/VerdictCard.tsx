import type { AnalysisPair } from "./types";
import { ScatterChart } from "./charts/ScatterChart";
import { GroupedBarChart } from "./charts/GroupedBarChart";
import { VERDICT_TEXT } from "./lib/verdicts";

function formatP(p: number): string {
  if (p === 0) return "0";
  if (p < 0.001) return p.toExponential(0);
  return p.toFixed(3);
}

function formatCoeff(c: number): string {
  return c.toFixed(2);
}

interface VerdictCardProps {
  pair: AnalysisPair;
}

export function VerdictCard({ pair }: VerdictCardProps) {
  const { x, y, stat, verdict, verification, plot, plain } = pair;
  const v = verdict.verdict;
  const confidencePct = Math.round(
    Math.max(0, Math.min(1, verdict.confidence)) * 100
  );
  const strengthPct = plain
    ? Math.max(0, Math.min(100, plain.strength_pct))
    : 0;

  return (
    <article className="verdict-card" data-testid="verdict-card" data-verdict={v}>
      {/* 1. Header: pair title + verdict badge */}
      <header className="card-header">
        <div className="card-header-top">
          <h2 className="pair-title">
            <span className="var-x">{x}</span>
            <span className="vs">vs</span>
            <span className="var-y">{y}</span>
          </h2>
          <div
            className={`verdict-badge verdict-${v}`}
            data-testid="verdict-badge"
          >
            {VERDICT_TEXT[v]}
            <span className="verdict-word" data-verdict-word>
              {v}
            </span>
          </div>
        </div>

        {/* 2. Everyday-language readout */}
        {plain && (
          <div className="plain-block" data-testid="plain-summary">
            <p className="plain-summary">{plain.summary}</p>

            <div className="plain-strength">
              <span className="plain-strength-label">Stärke</span>
              <div
                className="plain-strength-track"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={strengthPct}
                aria-label={`Stärke: ${plain.strength_label}`}
              >
                <div
                  className={`plain-strength-fill verdict-${v}`}
                  style={{ width: `${strengthPct}%` }}
                />
              </div>
              <span className="plain-strength-word">{plain.strength_label}</span>
            </div>

            {plain.explained_pct != null && (
              <div className="plain-explained">
                <div className="plain-explained-head">
                  <span className="plain-explained-label">Erklärter Anteil</span>
                  <span className="plain-explained-pct">
                    {plain.explained_pct} %
                  </span>
                </div>
                <div
                  className="plain-explained-track"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={plain.explained_pct}
                  aria-label={`Erklärter Anteil: ${plain.explained_pct} Prozent gemeinsame Schwankung`}
                >
                  <div
                    className={`plain-explained-fill verdict-${v}`}
                    style={{
                      width: `${Math.max(0, Math.min(100, plain.explained_pct))}%`,
                    }}
                  />
                </div>
                <p className="plain-explained-caption">gemeinsame Schwankung</p>
              </div>
            )}

            {plain.rule_of_thumb && (
              <p className="plain-rule">
                <span className="plain-rule-label">Faustregel</span>
                {plain.rule_of_thumb}
              </p>
            )}
          </div>
        )}

        {/* 3. Raw statistics - tucked away for the curious */}
        <details className="stat-details" open={!plain}>
          <summary className="stat-details-summary">
            Details (r, p, n, Methode)
          </summary>
          <p className="stat-line">
            <strong>r = {formatCoeff(stat.coefficient)}</strong>
            <span className="dot-sep">•</span>
            Methode: {stat.method}
            <span className="dot-sep">•</span>
            n = {stat.n}
            <span className="dot-sep">•</span>
            p = {formatP(stat.p_value)}
            {!stat.significant && (
              <span className="not-sig-tag">nicht signifikant</span>
            )}
          </p>
        </details>
      </header>

      {/* 4. Chart */}
      <div className="card-chart">
        {plot.kind === "scatter" ? (
          <ScatterChart
            points={plot.points}
            xLabel={plot.x_label}
            yLabel={plot.y_label}
          />
        ) : (
          <GroupedBarChart
            bars={plot.bars}
            xLabel={plot.x_label}
            yLabel={plot.y_label}
            valueLabel={plot.value_label}
          />
        )}
      </div>

      {/* 5. Confidence bar */}
      <div className="confidence-block">
        <div className="confidence-row">
          <span className="confidence-label">Konfidenz</span>
          <span className="confidence-num" data-testid="confidence-value">
            {verdict.confidence.toFixed(2)}
          </span>
        </div>
        <div
          className="confidence-track"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={1}
          aria-valuenow={verdict.confidence}
        >
          <div
            className={`confidence-fill verdict-${v}`}
            style={{ width: `${confidencePct}%` }}
          />
        </div>
      </div>

      {/* 6. Confounder + verification */}
      {verdict.confounder && (
        <div className="confounder-block">
          <div className="confounder-head">
            <span className="confounder-label">Wahrscheinlicher Confounder</span>
            <span className="confounder-name">{verdict.confounder}</span>
            <span
              className={`data-tag ${
                verdict.confounder_in_data ? "in-data" : "not-in-data"
              }`}
            >
              {verdict.confounder_in_data ? "in Daten" : "nicht in Daten"}
            </span>
          </div>

          {verification && (
            <div className="verification">
              <div className="verification-row">
                <span className="partial-label">Partialkorrelation:</span>
                <span className="r-before">
                  r = {formatCoeff(verification.r_before)}
                </span>
                <span className="arrow">→</span>
                <span className="r-after">
                  r = {formatCoeff(verification.r_after)}
                </span>
                <span
                  className={`confirm-tag ${
                    verification.collapsed ? "confirms" : "does-not-confirm"
                  }`}
                >
                  {verification.collapsed
                    ? "Confounder bestätigt"
                    : "nicht bestätigt"}
                </span>
              </div>
              <p className="verification-note">{verification.note}</p>
            </div>
          )}
        </div>
      )}

      {/* 7. Needed data */}
      <p className="needed-data">
        <span className="needed-data-label">Um sicher zu sein, bräuchte ich:</span>{" "}
        {verdict.needed_data}
      </p>

      {/* 8. Reasoning */}
      <p className="reasoning">{verdict.reasoning}</p>

      {/* 9. Ruled-out alternatives - what the model excluded and why */}
      {verdict.ruled_out && verdict.ruled_out.length > 0 && (
        <div className="ruled-out" data-testid="ruled-out">
          <span className="ruled-out-title">Andere Erklärungen ausgeschlossen</span>
          <ul className="ruled-out-list">
            {verdict.ruled_out.map((r) => (
              <li key={r.label} className="ruled-out-item">
                <span className={`ruled-out-label verdict-${r.label}`}>
                  {VERDICT_TEXT[r.label]}
                </span>
                <span className="ruled-out-why">{r.why}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
