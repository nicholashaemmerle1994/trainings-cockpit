import { fmtKm, fmtMinutes } from "./format";
import type { PlannerEntry } from "./types";

function approx(value: string, estimated: boolean): string {
  return estimated ? `≈ ${value}` : value;
}

function withStart(start: string | null, text: string): string {
  return start ? `${start} · ${text}` : text;
}

/** Geplante Vorgabe eines Listeneintrags — dieselbe Form in Woche und Blatt. */
export function plannedMeta(entry: PlannerEntry): string {
  const planned = entry.planned;
  if (!planned) return "Ohne Vorgabe";
  // In der Wochenliste zählt die belegte Teilmenge, nicht die vom
  // bestehenden Parser geschätzte Gesamtdauer. Sonst sähe F04 wie eine
  // exakte 51-Minuten-Einheit aus, obwohl nur 28 min + 4 km belegt sind.
  const duration =
    planned.known_seconds != null
      ? fmtMinutes(planned.known_seconds / 60)
      : approx(fmtMinutes(planned.minutes), planned.estimated === "dauer");
  const distance =
    planned.known_distance_metres != null
      ? fmtKm(planned.known_distance_metres / 1000)
      : approx(fmtKm(planned.km), planned.estimated === "distanz");
  const mixed =
    planned.known_seconds != null && planned.known_distance_metres != null;
  const parts = mixed
    ? [duration, distance]
    : planned.primary === "distance"
      ? [distance, duration]
      : [duration, distance];
  const visible = parts.filter((part) => part !== "—" && part !== "≈ —");
  let text = mixed ? visible.join(" + ") : visible.join(" · ");
  if (planned.has_unknown) text = text ? `${text} · unvollständig` : "Angaben unvollständig";
  return withStart(entry.start, text || "Ohne Vorgabe");
}
