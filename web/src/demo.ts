/**
 * Der Demo-Zustand ist eine reine Vorschau-Hilfe: Er ersetzt die
 * Darstellungsdaten, nicht die Datenlogik. Er existiert nur im Vorschau-Bau
 * (`VITE_APP_VARIANT=preview`) und nur unter `?demo=recovery`; im stabilen
 * Bau wird der Zweig wegoptimiert.
 */
import type { Overview, Recovery } from "./types";
import { isPreview } from "./variant";

export const isDemoRecovery =
  isPreview && new URLSearchParams(window.location.search).get("demo") === "recovery";

/**
 * Die Beispielwerte entsprechen dem Score-Zustand der Referenz:
 * 62 ms HRV gegen 57,4 ms üblich sind +8 %, 46 bpm Ruhepuls gegen 49 bpm
 * üblich sind −3 bpm. Nur Anzeige, keine Rechnung und keine API.
 */
const DEMO_RECOVERY: Recovery = {
  score: 82,
  band: "green",
  label: "Gut",
  confidence: 1,
  components: [
    {
      key: "hrv",
      label: "HRV",
      score: 88,
      today: 62,
      average: 58,
      baseline: 57.4,
      unit: "ms",
      weight: 35,
      z: 0.83,
    },
    {
      key: "rhr",
      label: "Ruhepuls",
      score: 84,
      today: 46,
      average: 47,
      baseline: 49,
      unit: "bpm",
      weight: 20,
      z: -0.72,
    },
    {
      key: "sleep",
      label: "Schlaf",
      score: 71,
      today: 6.83,
      average: 6.6,
      baseline: 7,
      unit: "h",
      weight: 30,
      z: -0.35,
    },
    {
      key: "resp",
      label: "Atmung",
      score: 79,
      today: 13.8,
      average: 14,
      baseline: 14.2,
      unit: "1/min",
      weight: 5,
      z: 0.2,
    },
  ],
  missing: [],
  reference: { nights: 21, minimum: 21, target: 21, average: 76 },
  explanation:
    "HRV und Ruhepuls liegen über dem Üblichen, die Nacht war mit 6:50 h etwas kurz. Insgesamt eine gute Erholung.",
  vendor_prompt: false,
};

/** Ersetzt im Demo-Modus nur die Anzeigedaten der Erholung. */
export function withDemoRecovery(overview: Overview): Overview {
  if (!isDemoRecovery) return overview;
  return {
    ...overview,
    today: {
      ...overview.today,
      as_of: overview.today.date,
      recovery: DEMO_RECOVERY,
      hrv: { ...overview.today.hrv, value: 62, average: 58, baseline: 57.4 },
      rhr: { ...overview.today.rhr, value: 46, average: 47, baseline: 49 },
      sleep: { ...overview.today.sleep, hours: 6.83 },
    },
  };
}
