export type Band = "green-top" | "green" | "amber" | "orange" | "red" | "unknown";

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
  account_id?: string;
  athlete_id?: string;
  athlete: { name: string; id: string };
  time_zone: string;
  goals: Goal[];
  generated_at: string;
  today: {
    date: string;
    as_of: string | null;
    vendor: number | null;
    /** Getrennter Zustand des heutigen Planungsanteils. */
    plan_source: {
      state: PlannerSourceState;
      complete: boolean;
      count: number;
      coverage: "covered" | "uncovered" | "unknown";
    };
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

/** Zustand einer Planerquelle. „loading" entsteht nur in der Oberfläche. */
export type PlannerSourceState =
  | "loading"
  | "complete"
  | "empty"
  | "partial"
  | "error"
  | "unavailable";

export interface PlannerSource {
  source: "plans" | "activities";
  key: string;
  state: PlannerSourceState;
  loaded: boolean;
  complete: boolean;
  count: number;
  error: string | null;
  coverage: "covered" | "uncovered" | "unknown";
}

export interface PlannerQuery {
  key: string;
  plans_key: string;
  activities_key: string;
  dashboard_key: string;
  projection: "week";
}

export interface PlannerPlannedValues {
  minutes: number | null;
  km: number | null;
  estimated: "dauer" | "distanz" | "keine";
  primary: "duration" | "distance" | null;
  load: number | null;
  seconds: number | null;
  distance_metres: number | null;
  known_seconds: number | null;
  known_distance_metres: number | null;
  has_unknown: boolean;
}

export interface PlannerActualValues {
  minutes: number | null;
  km: number | null;
  load: number | null;
  intensity?: number | null;
  seconds: number;
}

export interface PlannerActivity extends Activity {
  row_id: number;
}

export interface PlannerEntry {
  kind: "planned" | "recorded" | "linked" | "completionReference";
  key: string;
  date: string;
  start: string | null;
  plan: {
    id: number;
    remote_id: string;
    local_id: string;
    reference: string;
    date: string;
    sport: string | null;
    sport_label: string;
    name: string;
  } | null;
  plan_id: number | null;
  name: string;
  sport: string | null;
  sport_label: string;
  planned: PlannerPlannedValues | null;
  actual: PlannerActualValues | null;
  /** Bei einer bestätigten Beziehung: jede Aufzeichnung bleibt erreichbar. */
  activities?: PlannerEntry[];
  activity?: PlannerActivity | null;
  activity_row_id?: number;
  activity_id?: string;
  activity_dates?: string[];
  compact_text?: string;
  status: "planned" | "recorded" | "completed" | "completionReference";
  relationship_id?: string;
}

export interface PlannerDay {
  date: string;
  weekday: string;
  weekday_short: string;
  label: string;
  is_today: boolean;
  entries: PlannerEntry[];
}

export interface PlannerSummaryEntry {
  state: PlannerSourceState;
  complete: boolean;
  seconds: number | null;
  load?: number | null;
  distance_metres?: number | null;
  count: number | null;
  has_unknown?: boolean;
}

export interface PlannerWeekResponse {
  account_id: string;
  athlete_id: string;
  week: string;
  from: string;
  to: string;
  time_zone: string;
  label: string;
  calendar_week: number;
  today: string;
  days: PlannerDay[];
  entries: PlannerEntry[];
  summary: {
    recorded: PlannerSummaryEntry;
    open_plan: PlannerSummaryEntry;
  };
  sources: {
    plans: PlannerSource;
    activities: PlannerSource;
  };
  query: PlannerQuery;
  relationship_issues: string[];
  generated_at: string;
}

export interface PlanGraphValue {
  kind: "value" | "range";
  value?: number;
  min: number;
  max: number;
}

export interface PlanGraphTarget {
  kind: "none" | "missing" | "zone" | "heartRate" | "power" | "pace";
  metric?: "heartRate" | "power" | "pace";
  unit?: string;
  text: string;
  values?: PlanGraphValue | null;
  zone_id?: string;
  zone_set_id?: string | null;
  zone_level?: number | null;
  absolute_low?: number | null;
  absolute_high?: number | null;
}

export interface PlanGraphSegment {
  kind: "execution" | "compression";
  position: number;
  node_id: string;
  group_id: string | null;
  repeat_group_ids: string[];
  repetition_index: number | null;
  repetition_path: number[];
  name: string;
  role: string;
  end_kind: "time" | "distance" | null;
  seconds: number | null;
  metres: number | null;
  extent_text: string;
  target_key: string | null;
  target_text: string;
  target: PlanGraphTarget | null;
  omitted_executions: number;
  omitted_repetitions: number;
  reason: string | null;
  start: number;
  end: number;
  start_fraction: number;
  width_fraction: number;
}

export interface PlanGraphZone {
  zone_id: string;
  label: string;
  level: number;
  absolute_low: number | null;
  absolute_high: number | null;
}

export interface PlanGraphTrack {
  key: string;
  metric: "heartRate" | "power" | "pace" | "none";
  unit: string;
  label: string;
  short: string;
  kind: "numeric" | "zone" | "none";
  segments: PlanGraphSegment[];
  domain?: { min: number; max: number; direction?: string } | null;
  ticks?: { at: number; value?: number; label: string }[];
  direction?: "faster-up" | "higher-up";
  zones?: PlanGraphZone[];
}

export interface PlanGraphAxis {
  mode: "time" | "distance" | "schematic";
  label: string;
  unit: string;
  total: number;
  total_text: string;
  ticks: { at: number; label: string }[];
}

export interface PlanGraphTotals {
  seconds: number;
  metres: number;
  executions: number;
  total_executions: number;
  has_unknown: boolean;
  first_end: string | null;
  text: string;
  compressed_executions: number;
}

export interface PlanGraph {
  axis: PlanGraphAxis;
  segments: PlanGraphSegment[];
  tracks: PlanGraphTrack[];
  totals: PlanGraphTotals;
  repetition_groups: {
    node_id: string;
    name: string;
    repetitions: number;
    skip_final_recovery: boolean;
  }[];
  compressions: {
    node_id: string;
    parent_group_id: string | null;
    first_position: number;
    omitted_executions: number;
    omitted_repetitions: number;
    reason: string;
  }[];
  text_alternative: string;
}

export interface PlanNodeEnd {
  kind: "time" | "distance" | "open";
  seconds?: number;
  metres?: number;
  text: string;
}

export interface PlanNode {
  kind: "step" | "repeat" | "unsupported";
  node_id: string;
  name?: string;
  label?: string;
  role?: string;
  end?: PlanNodeEnd;
  target?: PlanGraphTarget;
  notes?: string | null;
  source_ref?: string | null;
  repetitions?: number;
  skip_final_recovery?: boolean;
  children?: PlanNode[];
  reason?: string;
}

export interface PlanRights {
  editability: "full" | "metadataOnly" | "readOnly";
  label: string;
  reason: string | null;
  restriction_codes: string[];
  can_edit_structure: boolean;
  can_edit_metadata: boolean;
  can_write: boolean;
  writes_on_open: false;
}

export interface PlanZoneOption {
  id: string;
  label: string;
  level: number;
  low: number;
  high: number;
}

export interface PlanZoneOptions {
  sport: string;
  available: boolean;
  zone_set_id: string | null;
  max_hr: number | null;
  zones: PlanZoneOption[];
}

export interface PlanTargetCapability {
  local: boolean;
  editable: boolean;
  synchronizable: boolean;
  gate?: string;
  reason?: string;
}

export interface PlanCapabilities {
  write: { available: boolean; reason: string };
  targets: {
    heartRateZone: PlanTargetCapability;
    heartRateBpm: PlanTargetCapability;
    pace: PlanTargetCapability;
    powerWatts: PlanTargetCapability;
    powerPercentFtp: PlanTargetCapability;
    powerZone: PlanTargetCapability;
    none: PlanTargetCapability;
  };
}

export interface PlanSourceSnapshot {
  remote_id: string;
  fetched_at: string;
  relevant_content_hash: string;
  remote_updated_at: string | null;
  remote_version: string | null;
  raw_workout_text: string | null;
}

export interface DraftFieldState {
  validity: "valid" | "incomplete" | "invalid";
  message: string | null;
  parsed: unknown;
}

export interface DraftIssue {
  code: string;
  message: string;
  node_id: string | null;
  field: string | null;
}

export interface PlanDraftMeta {
  base_local_id: string | null;
  base_source_hash: string | null;
  remote_id: string | null;
  is_new: boolean;
  dirty: boolean;
  has_field_input: boolean;
  valid: boolean;
  field_states: Record<string, DraftFieldState>;
  issues: DraftIssue[];
  write: { available: boolean; reason: string };
}

export interface PlanDetail {
  kind: "planned";
  id: number | null;
  remote_id: string | null;
  local_id: string;
  reference: string;
  name: string;
  sport: string;
  sport_label: string;
  date: string;
  time: string | null;
  time_zone: string;
  notes: string | null;
  rights: PlanRights;
  known: {
    seconds: number;
    metres: number;
    executions: number;
    has_unknown: boolean;
    first_end: string | null;
    duration_text: string | null;
    distance_text: string | null;
    text: string;
  };
  nodes: PlanNode[];
  graph: PlanGraph;
  zone_options: PlanZoneOptions;
  capabilities: PlanCapabilities;
  source_snapshot: PlanSourceSnapshot | null;
  source: { name: string; remote_id: string | null; read_only: boolean };
  fetched_at: string;
}

export interface PlanDraftProjection extends PlanDetail {
  draft: PlanDraftMeta;
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

export type PlannerSaveState =
  | "clean"
  | "dirty"
  | "invalid"
  | "saving"
  | "saved"
  | "failed"
  | "conflict"
  | "unknown"
  | "savedUnverified";

export interface PlannerConflictVersion {
  remote_id: string | null;
  local_id: string;
  external_id: string | null;
  name: string;
  sport: string;
  date: string;
  local_time: string | null;
  notes: string | null;
  editability: string;
  editability_reason: string | null;
  nodes: unknown[];
}

export interface PlannerConflict {
  kind: "deleted" | "permission" | "structure" | "metadata" | "identity";
  reason: string;
  remote_id: string;
  changed_fields: string[];
  actions: string[];
  baseline: PlannerConflictVersion | null;
  remote: PlannerConflictVersion | null;
}

export interface PlannerSaveStatus {
  state: PlannerSaveState;
  message: string;
  operation_id: string | null;
  remote_id: string | null;
  external_id: string | null;
  error: string | null;
  retryable: boolean;
  reconciliation_required: boolean;
  locked: boolean;
  conflict: PlannerConflict | null;
  persistence_error: string | null;
}

export interface PlannerSaveResponse {
  status: PlannerSaveStatus;
  confirmed: unknown | null;
  event_id: string | null;
  week: string | null;
  old_week: string | null;
  time_zone: string;
  generated_at: string;
}

export interface PlannerOperation {
  operation_id: string;
  local_id: string;
  draft_id: string;
  remote_id: string | null;
  external_id: string | null;
  mode: string;
  kind: string;
  state: string;
  created_at: string;
  reconciliation_required: boolean;
}

export interface PlannerOperationsResponse {
  account_id: string;
  athlete_id: string;
  items: PlannerOperation[];
}

export interface SyncResult {
  activities: number;
  wellness: number;
  events: number;
  athlete: string;
  range: [string, string];
}
