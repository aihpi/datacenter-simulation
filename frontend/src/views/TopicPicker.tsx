import { useRef } from "react";
import type { Theme } from "../types";

interface TopicPickerProps {
  themes: Theme[];
  loading: boolean;
  error: string | null;
  onPickTheme: (theme: Theme) => void;
  onUpload: (files: File[]) => void;
  onRetry: () => void;
}

export function TopicPicker({
  themes,
  loading,
  error,
  onPickTheme,
  onUpload,
  onRetry,
}: TopicPickerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    e.target.value = ""; // allow re-selecting the same files
    if (files.length) onUpload(files);
  };

  return (
    <div className="topic-picker">
      <section className="picker-intro">
        <h2 className="section-title">Thema wählen</h2>
        <p className="section-sub">
          Wähle einen Beispiel-Datensatz, oder lade eigene CSV-Dateien hoch. Die
          Analyse läuft Schritt für Schritt und du siehst live, was im Hintergrund
          passiert.
        </p>
      </section>

      {loading && (
        <div className="state-msg" data-testid="themes-loading">
          Themen werden geladen…
        </div>
      )}

      {error && (
        <div className="state-msg state-error" data-testid="themes-error">
          Themen konnten nicht geladen werden. {error}
          <button className="retry-btn" onClick={onRetry}>
            Erneut versuchen
          </button>
        </div>
      )}

      {!loading && !error && (
        <div className="theme-grid" data-testid="theme-grid">
          {themes.map((t) => (
            <button
              key={t.slug}
              className="theme-card"
              onClick={() => onPickTheme(t)}
              data-testid={`theme-${t.slug}`}
            >
              <div className="theme-emoji" aria-hidden>
                {t.emoji}
              </div>
              <div className="theme-body">
                <h3 className="theme-title">{t.title}</h3>
                <p className="theme-summary">{t.summary}</p>
                <div className="theme-meta">
                  {t.kind === "example" ? (
                    <span className="theme-tag">
                      {t.files.length} Dateien
                      {t.key_hint ? ` · Schlüssel: ${t.key_hint}` : ""}
                    </span>
                  ) : (
                    <span className="theme-tag">Einzeldatensatz</span>
                  )}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      <section className="upload-panel">
        <div className="upload-panel-text">
          <h3 className="section-title">Eigene Daten hochladen</h3>
          <p className="section-sub">
            Eine oder mehrere CSV-Dateien. Mehrere Dateien werden über eine
            gemeinsame Schlüsselspalte zusammengeführt, sonst zeilenweise
            ausgerichtet, dann wird datei­übergreifend nach Korrelationen gesucht.
          </p>
        </div>
        <div className="upload-panel-action">
          <input
            ref={fileInputRef}
            className="upload-input"
            type="file"
            accept=".csv,text/csv"
            multiple
            onChange={handleFiles}
            data-testid="upload-input"
          />
          <button
            type="button"
            className="upload-btn"
            onClick={() => fileInputRef.current?.click()}
            data-testid="upload-btn"
          >
            ⬆ CSV(s) hochladen &amp; analysieren
          </button>
        </div>
      </section>
    </div>
  );
}
