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
  weeks: Week[];
  activities: Activity[];
  upcoming: Upcoming[];
}

export interface ActivitiesResponse {
  items: Activity[];
  sports: { sport: string; count: number }[];
  total: number;
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
