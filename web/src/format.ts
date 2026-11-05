import type { Band } from "./types";

export const BAND_COLORS: Record<Band, string> = {
  green: "var(--band-good)",
  amber: "var(--band-mid)",
  orange: "var(--band-low)",
  red: "var(--band-bad)",
  unknown: "var(--text-muted)",
};

export const SPORT_LABELS: Record<string, string> = {
  Run: "Laufen",
  VirtualRun: "Laufen indoor",
  Ride: "Rad",
  VirtualRide: "Rad indoor",
  Swim: "Schwimmen",
  OpenWaterSwim: "Freiwasser",
  WeightTraining: "Kraft",
  Workout: "Workout",
  Walk: "Gehen",
  Hike: "Wandern",
  HighIntensityIntervalTraining: "HIIT",
  Transition: "Wechsel",
};

export function sportLabel(sport: string): string {
  return SPORT_LABELS[sport] ?? sport;
}

export function fmtHours(hours: number | null | undefined): string {
  if (hours == null) return "—";
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  return `${h}:${String(m).padStart(2, "0")} h`;
}

export function fmtClock(hours: number | null | undefined): string {
  if (hours == null) return "—";
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  return `${h}:${String(m).padStart(2, "0")}`;
}

/** Wochenumfang als „14 h 36 min" – Minuten zählen, keine Nachkommastellen. */
export function fmtSpan(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  const total = Math.round(seconds / 60);
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h === 0) return `${m} min`;
  return `${h} h ${String(m).padStart(2, "0")} min`;
}

/** Dauer als „2 h 45 min" – so, wie sie im Plan steht. */
export function fmtMinutes(minutes: number | null | undefined): string {
  if (minutes == null) return "—";
  const total = Math.round(minutes);
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h === 0) return `${m} min`;
  if (m === 0) return `${h} h`;
  return `${h} h ${String(m).padStart(2, "0")} min`;
}

export function fmtLiters(ml: number | null | undefined): string {
  if (ml == null) return "—";
  return `${(ml / 1000).toLocaleString("de-AT", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} l`;
}

export function fmtDuration(minutes: number | null | undefined): string {
  if (minutes == null) return "—";
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return h > 0 ? `${h}:${String(m).padStart(2, "0")} h` : `${m} min`;
}

export function fmtKm(km: number | null | undefined): string {
  if (km == null) return "—";
  return `${km.toLocaleString("de-AT", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} km`;
}

export function fmtPace(minPerKm: number | null | undefined): string {
  if (minPerKm == null) return "—";
  const min = Math.floor(minPerKm);
  const sec = Math.round((minPerKm - min) * 60);
  return `${min}:${String(sec).padStart(2, "0")} /km`;
}

export function fmtNumber(value: number | null | undefined, digits = 0): string {
  if (value == null) return "—";
  return value.toLocaleString("de-AT", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtSigned(value: number | null | undefined, digits = 0): string {
  if (value == null) return "—";
  if (value === 0) return fmtNumber(0, digits);
  const sign = value > 0 ? "+" : "−";
  return `${sign}${fmtNumber(Math.abs(value), digits)}`;
}

export function fmtDate(iso: string, options?: Intl.DateTimeFormatOptions): string {
  const date = new Date(`${iso}T00:00:00`);
  return date.toLocaleDateString(
    "de-AT",
    options ?? { weekday: "short", day: "numeric", month: "short" },
  );
}

export function fmtDateLong(iso: string): string {
  return fmtDate(iso, { weekday: "long", day: "numeric", month: "long" });
}

export function fmtTick(iso: string): string {
  return fmtDate(iso, { day: "numeric", month: "short" });
}

