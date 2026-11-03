export type Band = "green" | "amber" | "orange" | "red" | "unknown";

export interface RecoveryComponent {
  key: string;
  label: string;
  score: number;
  today: number;
  average: number;
  baseline: number;
  unit: string;
  weight: number;
  date?: string | null;
  z?: number | null;
  vendor?: number | null;
}

export interface RecoveryReference {
  nights: number;
  minimum: number;
  target: number;
  average: number | null;
}

export interface Recovery {
  score: number | null;
  band: Band;
  label: string;
  confidence: number;
  components: RecoveryComponent[];
  missing?: string[];
  reference?: RecoveryReference | null;
  explanation: string;
  /** Solange das Vergleichsfenster läuft: Feld für den Bevel-Wert (D-52). */
  vendor_prompt?: boolean;
}

export interface Activity {
  id: string;
  date: string;
  start: string;
  sport: string;
  sport_label: string;
  name: string;
  duration_min: number | null;
  distance_km: number | null;
  avg_hr: number | null;
  max_hr: number | null;
  load: number | null;
  intensity: number | null;
  pace_min_km: number | null;
  speed_kmh: number | null;
}

export interface Week {
  week: number;
  year: number;
  label: string;
  hours: number;
  load: number;
  sessions: number;
  by_sport: Record<string, number>;
}

export interface Upcoming {
  date: string;
  sport: string;
  sport_label: string;
  name: string;
  load: number | null;
  duration_min: number | null;
}

export interface Goal {
  name: string;
  date: string;
  days: number;
  priority: string;
}

export interface Overview {
  athlete: { name: string; id: string };
  goals: Goal[];
  generated_at: string;
  today: {
    date: string;
    as_of: string | null;
    vendor: number | null;
    recovery: Recovery;
    sleep: { hours: number | null; score: number | null; debt_7d: number; baseline_hours: number };
    load: {
      ctl: number | null;
      atl: number | null;
      tsb: number | null;
      acwr: number | null;
      week_seconds: number;
      week_hours: number;
      week_load: number;
      week_sessions: number;
    };
    hrv: { value: number | null; average: number | null; baseline: number | null; status: string };
    rhr: { value: number | null; average: number | null; baseline: number | null };
  };
  series: {
    load: { date: string; load: number; ctl: number | null; atl: number | null; tsb: number | null }[];
    hrv: { date: string; hrv: number | null; rhr: number | null; baseline: number | null }[];
    sleep: { date: string; hours: number | null; score: number | null }[];
    recovery: { date: string; score: number; vendor: number | null }[];
  };
  sessions: SessionRow[];
  unplanned: UnplannedUnit[];
  weeks: Week[];
  activities: Activity[];
  upcoming: Upcoming[];
}

/** Eine heute erledigte Einheit, die in keinem Plan stand. */
export interface UnplannedUnit {
  row_id: number;
  sport: string;
  sport_label: string;
  name: string;
  minutes: number | null;
  km: number | null;
  load: number | null;
}

export interface SessionStep {
  label: string;
  minutes: number;
  distance_km: number | null;
  target: string;
  work: boolean;
  lo: number | null;
  hi: number | null;
}

export interface SessionAxis {
  from: number;
  to: number;
  ticks: number[];
  unit: string;
}

export interface SessionFuel {
  carbs_g: number;
  rate: number;
  gels: number;
  water_ml: number;
  sodium_mg: number;
}

export interface SessionActual {
  row_id: number;
  activity_id: string;
  name: string;
  minutes: number | null;
  km: number | null;
  load: number | null;
  intensity: number | null;
  hr: number | null;
  /** Der aufgezeichnete Verlauf, sofern die Quelle Sekundenwerte hat (D-53). */
  series?: UnitSeries | null;
}

export interface SessionRow {
  day: "today" | "tomorrow";
  id: number;
  date: string;
  sport: string;
  sport_label: string;
  name: string;
  minutes: number | null;
  km: number | null;
  estimated: "dauer" | "distanz" | "keine";
  primary: "duration" | "distance" | null;
  load: number | null;
  done: boolean;
}

export interface SessionDetail {
  id: number;
  date: string;
  sport: string;
  sport_label: string;
  name: string;
  load: number | null;
  intensity: number | null;
  minutes: number | null;
  km: number | null;
  estimated: "dauer" | "distanz" | "keine";
  primary: "duration" | "distance" | null;
  axis: SessionAxis | null;
  steps: SessionStep[];
  total_minutes: number | null;
  fuel: SessionFuel | null;
  actual: SessionActual | null;
}

export interface ActivitiesResponse {
  items: Activity[];
  sports: { sport: string; count: number }[];
  total: number;
}

/** Eine erledigte Einheit in der Liste der letzten sieben Tage. */
export interface WeekUnit extends Activity {
  row_id: number;
  total_min: number | null;
}

export interface WeekResponse {
  from: string;
  to: string;
  seconds: number;
  load: number;
  units: WeekUnit[];
}

export interface ZoneShare {
  zone: number;
  seconds: number;
  share: number;
}

/** Ein Punkt des aufgezeichneten Verlaufs: Sekunde, Wert, Puls (D-53). */
export interface SeriesPoint {
  t: number;
  v: number | null;
  hr: number | null;
}

/**
 * Der Verlauf einer erledigten Einheit, so wie die Aufzeichnung ihn hergibt.
 * `kind` sagt, was die Hauptlinie zeigt: Leistung, Tempo oder Puls.
 */
export interface UnitSeries {
  kind: "power" | "pace" | "hr";
  unit: string;
  points: SeriesPoint[];
  mean: number | null;
  peak: number | null;
  pulse: number | null;
  duration_s: number;
  reference: number | null;
}

export interface UnitDetail extends WeekUnit {
  elevation_m: number | null;
  calories: number | null;
  pace_100m: number | null;
  origin: string;
  zones: ZoneShare[];
  zone_source: string | null;
  series: UnitSeries | null;
}

export interface FuelEntry {
  minute: number;
  kind: "trinken" | "essen";
  label: string;
  detail: string;
  carbs: number;
}

export interface FuelPlan {
  input: {
    minutes: number;
    hours: number;
    mode: string;
    mode_label: string;
    source: string;
    source_label: string;
    shot_unit: string;
    weight_kg: number;
    temp_c: number;
  };
  per_hour: { carbs: number; from: number; to: number; water_ml: number };
  total: { carbs: number; from: number; to: number; water_ml: number; sodium_mg: number };
  drink: {
    carbs_per_hour: number;
    carbs_per_bottle: number;
    bottle_ml: number;
    concentration_pct: number;
    bottles: number;
  };
  gels: { per_hour: number; count: number; carbs_each: number; carbs_total: number; caffeine: number };
  syrup: {
    shot_ml: number;
    shot_g: number;
    unit: string;
    amount: number;
    grams_per_shot: number;
    carbs_per_shot: number;
    carbs_total: number;
    shots_per_hour: number;
    minutes_between: number | null;
    shots: number;
    ml_per_hour: number;
    ml_total: number;
    grams_total: number;
    salt_g_per_hour: number;
    salt_g_total: number;
    salt_g_per_shot: number;
    sodium_mg_per_shot: number;
    suggestion: {
      shot_ml: number;
      shots: number;
      carbs_per_shot: number;
      text: string;
    } | null;
  } | null;
  water: { ml_per_hour: number; ml_total: number; note: string };
  sodium: {
    mg_per_hour: number;
    mg_total: number;
    salt_g_per_hour: number;
    salt_g_total: number;
    note: string;
  };
  schedule: FuelEntry[];
  surrounding: { key: string; label: string; carbs: number; text: string }[];
  notes: { tone: string; text: string }[];
  modes: { key: string; label: string; hint: string }[];
  sources: { key: string; label: string; hint: string }[];
}

export interface SyncResult {
  activities: number;
  wellness: number;
  events: number;
  athlete: string;
  range: [string, string];
}
