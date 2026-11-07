import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export const PROJEKTSEITE_URL = "https://hpi.de/kisz/";
export const IMPRESSUM_URL = "https://aisc.hpi.de/portal/cfp/pages/imprint/";
export const FOERDERHINWEIS =
  "Ein Angebot des KI-Servicezentrums Berlin-Brandenburg am Hasso-Plattner-Institut, gefördert vom Bundesministerium für Forschung, Technologie und Raumfahrt (BMFTR), Förderkennzeichen 16IS22092.";

interface LegalViewProps {
  onBack: () => void;
}

export function LegalView({ onBack }: LegalViewProps) {
  return (
    <div className="space-y-4" data-testid="legal-datenschutz">
      <Button variant="outline" size="sm" onClick={onBack} data-testid="legal-back">
        ← Zurück zum Tool
      </Button>
      <Card>
        <CardHeader>
          <CardTitle>Datenschutzerklärung</CardTitle>
          <CardDescription>Stand: November 2026</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm leading-relaxed">
          <section>
            <h3 className="font-semibold">Verantwortlicher</h3>
            <p>
              Hasso-Plattner-Institut für Digital Engineering gGmbH
              <br />
              Prof.-Dr.-Helmert-Str. 2-3, 14482 Potsdam
              <br />
              Telefon: +49 (0)331 5509-0<br />
              E-Mail: hpi-info@hpi.de
              <br />
              Dienstspezifischer Kontakt: ki-servicezentrum@hpi.de
              <br />
              Vertretung und Registereintrag: siehe{" "}
              <a href={IMPRESSUM_URL} target="_blank" rel="noopener noreferrer">
                Impressum
              </a>
              .
            </p>
          </section>
          <section>
            <h3 className="font-semibold">Datenschutzbeauftragter</h3>
            <p>
              TÜV SÜD Akademie GmbH, Westendstr. 199, 80686 München
              <br />
              E-Mail: datenschutz@hpi.de
            </p>
          </section>
          <section>
            <h3 className="font-semibold">Keine Erhebung personenbezogener Daten</h3>
            <p>
              Dieses Werkzeug erhebt, speichert und verarbeitet keine personenbezogenen
              Daten. Es gibt kein Konto und keine Anmeldung. Es werden keine Cookies
              gesetzt, keine Tracking- oder Analysewerkzeuge eingebunden und keine
              Nutzungsprofile erstellt. Schriften und Grafiken werden vom eigenen Server
              geladen.
            </p>
          </section>
          <section>
            <h3 className="font-semibold">Eingaben und hochgeladene Dateien</h3>
            <p>
              Eingegebene Specs und hochgeladene CSV-Dateien werden ausschließlich auf
              dem Server dieses Werkzeugs für die Berechnung im laufenden Aufruf
              verarbeitet, nicht an Dritte übermittelt und nicht dauerhaft gespeichert.
              Laden Sie bitte keine Dateien mit personenbezogenen Daten hoch.
            </p>
          </section>
          <section>
            <h3 className="font-semibold">Server-Logdateien</h3>
            <p>
              Beim Aufruf protokolliert der Webserver technisch bedingt Zeitpunkt,
              aufgerufene Adresse, Browsertyp und IP-Adresse. Rechtsgrundlage ist Art. 6
              Abs. 1 lit. f DSGVO; das berechtigte Interesse liegt im sicheren Betrieb
              und in der Fehleranalyse. Die Daten werden nicht mit anderen Quellen
              zusammengeführt und nach Ablauf der Aufbewahrungsfrist des HPI-Rechenzentrums
              gelöscht.
            </p>
          </section>
          <section>
            <h3 className="font-semibold">Ihre Rechte</h3>
            <p>
              Sie haben das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der
              Verarbeitung und Widerspruch (Art. 15 bis 21 DSGVO) sowie das Recht auf
              Beschwerde bei einer Datenschutzaufsichtsbehörde, etwa der
              Landesbeauftragten für den Datenschutz und für das Recht auf
              Akteneinsicht Brandenburg.
            </p>
          </section>
        </CardContent>
      </Card>
    </div>
  );
}
