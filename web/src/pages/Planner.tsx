import { useMemo, useState } from "react";
import { AddWorkoutSheet, type NewPlanConfig } from "../components/AddWorkoutSheet";
import { IconBack, IconForward, IconPlus } from "../components/icons";
import { PlanSheet } from "../components/PlanSheet";
import { ScreenHeader } from "../components/ScreenHeader";
import { StatusBadge } from "../components/ui";
import { UnitSheet } from "../components/UnitSheet";
import { WorkoutPreview } from "../components/WorkoutPreview";
import { fmtDateLong, fmtKm, fmtMinutes, fmtNumber, fmtSpan } from "../format";
import { usePlannerWeek, type PlannerSourceName } from "../plannerQuery";
import { addDays, currentPlannerWeek } from "../routing";
import type {
  PlannerDay,
  PlannerEntry,
  PlannerSource,
  PlannerSummaryEntry,
  PlannerWeekResponse,
} from "../types";

function approx(value: string, estimated: boolean): string {
  return estimated ? `≈ ${value}` : value;
}

function withStart(start: string | null, text: string): string {
  return start ? `${start} · ${text}` : text;
}

function plannedMeta(entry: PlannerEntry): string {
  const planned = entry.planned;
  if (!planned) return "Ohne Vorgabe";
  const duration = approx(
    fmtMinutes(planned.minutes),
    planned.estimated === "dauer" && planned.known_seconds == null,
  );
  const distance = approx(
    fmtKm(planned.km),
    planned.estimated === "distanz" && planned.known_distance_metres == null,
  );
  const parts = planned.primary === "distance" ? [distance, duration] : [duration, distance];
  const text = parts.filter((part) => part !== "—" && part !== "≈ —").join(" · ") || "Ohne Vorgabe";
  return withStart(entry.start, text);
}

function actualMeta(entry: PlannerEntry): string {
  const actual = entry.actual;
  if (!actual) return withStart(entry.start, "Ohne Messwerte");
  const parts = [fmtMinutes(actual.minutes), fmtKm(actual.km)].filter(
    (part) => part !== "—",
  );
  return withStart(entry.start, parts.join(" · ") || "Ohne Messwerte");
}

function linkedMeta(entry: PlannerEntry): string {
  const parts = [actualMeta(entry)];
  if ((entry.activities?.length ?? 0) > 1) {
    parts.push(`${entry.activities?.length} Aufzeichnungen`);
  }
  if (entry.plan?.name) parts.push(`Plan: ${entry.plan.name}`);
  return parts.join(" · ");
}

function entrySport(entry: PlannerEntry): string {
  return entry.sport ?? entry.plan?.sport ?? "Other";
}

function entryName(entry: PlannerEntry): string {
  return entry.name || entry.plan?.name || entry.sport_label;
}

function openPlannedText(open: PlannerSummaryEntry): string {
  if (open.seconds == null && open.count == null) {
    return "Offene Planung: Daten nicht verfügbar";
  }
  if (open.count === 0) {
    return open.complete ? "Keine offenen Planungen" : "Offene Planung: noch nicht vollständig geladen";
  }
  const units = open.count == null ? "—" : `${open.count} ${open.count === 1 ? "Einheit" : "Einheiten"}`;
  const parts = [units];
  if (open.seconds != null && open.seconds > 0) parts.push(fmtSpan(open.seconds));
  if (open.distance_metres != null && open.distance_metres > 0) {
    parts.push(fmtKm(open.distance_metres / 1000));
  }
  if (open.has_unknown) parts.push("Angaben unvollständig");
  if (!open.complete) parts.push("vorläufig");
  return `Noch geplant: ${parts.join(" · ")}`;
}

function emptyDayText(data: PlannerWeekResponse): string {
  const plans = data.sources.plans;
  const activities = data.sources.activities;
  if (plans.complete && activities.complete) return "Keine Einheiten";
  if (!plans.complete && !activities.complete) {
    return "Daten für diesen Tag sind noch nicht verfügbar.";
  }
  if (!plans.complete) {
    return "Aufzeichnungen: keine · Planungen für diesen Zeitraum nicht verfügbar.";
  }
  return "Planungen: keine · Aufzeichnungen für diesen Zeitraum nicht verfügbar.";
}

export function Planner({
  week,
  timeZone,
  onWeekChange,
  openPlan,
  openUnit,
  onOpenPlan,
  onOpenUnit,
  onClosePlan,
  onCloseUnit,
}: {
  week: string;
  timeZone: string;
  onWeekChange: (week: string) => void;
  openPlan: number | null;
  openUnit: number | null;
  onOpenPlan: (planId: number) => void;
  onOpenUnit: (rowId: number) => void;
  onClosePlan: () => void;
  onCloseUnit: () => void;
}) {
  const { data, loading, stale, error, retrying, reload } = usePlannerWeek(week);
  const [addDay, setAddDay] = useState<string | null>(null);
  const [newPlan, setNewPlan] = useState<NewPlanConfig | null>(null);

  const currentWeek = useMemo(
    () => currentPlannerWeek(new Date(), timeZone),
    [timeZone],
  );
  const resolved = data?.week === week ? data : null;

  const unitPlan = useMemo(() => {
    if (openUnit == null || !resolved) return null;
    for (const entry of resolved.entries) {
      if (entry.kind !== "linked") continue;
      const carries =
        entry.activity_row_id === openUnit ||
        entry.activity?.row_id === openUnit ||
        (entry.activities ?? []).some(
          (activity) => activity.activity_row_id === openUnit,
        );
      if (carries && entry.plan_id != null) {
        return { id: entry.plan_id, name: entry.plan?.name ?? entry.name };
      }
    }
    return null;
  }, [openUnit, resolved]);

  const previous = addDays(week, -7);
  const next = addDays(week, 7);

  return (
    <div className="page planner-page">
      <ScreenHeader
        title="Trainingsplaner"
        meta="Deine geplanten und absolvierten Einheiten"
      />

      <WeekNavigator
        week={week}
        label={resolved?.label ?? "Woche wird geladen"}
        calendarWeek={resolved?.calendar_week ?? null}
        currentWeek={currentWeek}
        onChange={onWeekChange}
        onPrevious={() => onWeekChange(previous)}
        onNext={() => onWeekChange(next)}
      />

      {error && (
        <div className="planner-state" role="alert">
          <p>{error}</p>
          <button type="button" className="btn" onClick={() => reload()}>
            Erneut laden
          </button>
        </div>
      )}

      {!resolved && loading && <PlannerSkeleton />}

      {resolved && (
        <>
          {stale && loading && (
            <p className="planner-updating" role="status">
              Woche wird aktualisiert…
            </p>
          )}

          <SourceNotice
            source={resolved.sources.plans}
            label="Planungen"
            retrying={retrying}
            onRetry={() => reload("plans")}
          />
          <SourceNotice
            source={resolved.sources.activities}
            label="Aufzeichnungen"
            retrying={retrying}
            onRetry={() => reload("activities")}
          />

          <PlannerSummary data={resolved} />

          <div className="planner-days">
            {resolved.days.map((day) => (
              <PlannerDaySection
                key={day.date}
                day={day}
                data={resolved}
                onOpenPlan={onOpenPlan}
                onOpenUnit={onOpenUnit}
                onAdd={setAddDay}
              />))}
          </div>

          <p className="sheet-src planner-src">
            Planungen aus intervals.icu · Aufzeichnungen aus Garmin und intervals.icu
          </p>
        </>
      )}

      {openUnit != null && (
        <UnitSheet
          rowId={openUnit}
          onClose={onCloseUnit}
          plan={unitPlan}
          onOpenPlan={onOpenPlan}
          top={openPlan == null}
        />
      )}
      {openPlan != null && (
        <PlanSheet eventId={openPlan} onClose={onClosePlan} />
      )}
      {newPlan != null && (
        <PlanSheet
          newPlan={newPlan}
          onClose={() => setNewPlan(null)}
        />
      )}
      {addDay != null && (
        <AddWorkoutSheet
          day={addDay}
          onClose={() => setAddDay(null)}
          onContinue={(config) => {
            setAddDay(null);
            setNewPlan(config);
          }}
        />
      )}
    </div>
  );
}

function WeekNavigator({
  week,
  label,
  calendarWeek,
  currentWeek,
  onChange,
  onPrevious,
  onNext,
}: {
  week: string;
  label: string;
  calendarWeek: number | null;
  currentWeek: string;
  onChange: (week: string) => void;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <div className="planner-weeknav-wrap">
      <div className="planner-weeknav">
        <button
          type="button"
          className="planner-nav-btn"
          onClick={onPrevious}
          aria-label="Vorige Woche"
        >
          <IconBack size={18} />
        </button>
        <div className="planner-weeknav__label">
          <strong>{label}</strong>
          {calendarWeek != null && (
            <span>Kalenderwoche {calendarWeek} · Montag–Sonntag</span>
          )}
        </div>
        <button
          type="button"
          className="planner-nav-btn"
          onClick={onNext}
          aria-label="Nächste Woche"
        >
          <IconForward size={18} />
        </button>
      </div>
      <button
        type="button"
        className="planner-week-current"
        onClick={() => onChange(currentWeek)}
        disabled={week === currentWeek}
      >
        Diese Woche
      </button>
    </div>
  );
}

function PlannerSummary({ data }: { data: PlannerWeekResponse }) {
  const recorded = data.summary.recorded;
  const open = data.summary.open_plan;
  const recordedValue =
    recorded.seconds == null ? "—" : `${!recorded.complete ? "ca. " : ""}${fmtSpan(recorded.seconds)}`;
  const loadValue = recorded.load == null ? "—" : fmtNumber(recorded.load);
  const countValue = recorded.count == null ? "—" : String(recorded.count);
  return (
    <section className="planner-summary" aria-label="Zusammenfassung der Woche">
      <div className="sheet-cells">
        <div className="sheet-cell">
          <span className="n">{recordedValue}</span>
          <span className="l">Absolviert</span>
        </div>
        <div className="sheet-cell">
          <span className="n">{loadValue}</span>
          <span className="l">Belastung</span>
        </div>
        <div className="sheet-cell">
          <span className="n">{countValue}</span>
          <span className="l">Einheiten</span>
        </div>
      </div>
      <p className={`planner-open${open.complete ? "" : " planner-open--partial"}`}>
        {openPlannedText(open)}
      </p>
    </section>
  );
}

function PlannerDaySection({
  day,
  data,
  onOpenPlan,
  onOpenUnit,
  onAdd,
}: {
  day: PlannerDay;
  data: PlannerWeekResponse;
  onOpenPlan: (planId: number) => void;
  onOpenUnit: (rowId: number) => void;
  onAdd: (day: string) => void;
}) {
  const headingId = `planner-day-${day.date}`;
  return (
    <section className="planner-day" aria-labelledby={headingId}>
      <div className="planner-day__head">
        <h2 id={headingId} className={day.is_today ? "planner-day__today" : ""}>
          {day.weekday}, {day.label}
        </h2>
        {day.is_today && <span className="planner-today-badge">Heute</span>}
        <button
          type="button"
          className="planner-add"
          onClick={() => onAdd(day.date)}
          aria-label={`Einheit am ${fmtDateLong(day.date)} hinzufügen`}
        >
          <IconPlus size={18} />
        </button>
      </div>

      {day.entries.length === 0 && (
        <p className="planner-empty">{emptyDayText(data)}</p>
      )}

      {day.entries.map((entry) => (
        <EntryRows
          key={entry.key}
          entry={entry}
          onOpenPlan={onOpenPlan}
          onOpenUnit={onOpenUnit}
        />
      ))}
    </section>
  );
}

function EntryRows({
  entry,
  onOpenPlan,
  onOpenUnit,
}: {
  entry: PlannerEntry;
  onOpenPlan: (planId: number) => void;
  onOpenUnit: (rowId: number) => void;
}) {
  if (entry.kind === "completionReference") {
    return (
      <WorkoutPreview
        sport={entrySport(entry)}
        name={entryName(entry)}
        meta={`${entry.compact_text ?? "Erledigt"} · Planung bleibt erhalten`}
        onClick={() => {
          if (entry.plan_id != null) onOpenPlan(entry.plan_id);
        }}
        trailing={<StatusBadge tone="positive">Erledigt</StatusBadge>}
      />
    );
  }

  if (entry.kind === "linked") {
    const views =
      entry.activities && entry.activities.length > 0
        ? entry.activities
        : entry.activity
          ? [entry]
          : [];
    return (
      <>
        {views.map((view) => (
          <WorkoutPreview
            key={view.key}
            sport={entrySport(view)}
            name={view.name || entryName(view)}
            meta={linkedMeta(view)}
            onClick={() => {
              const rowId = view.activity?.row_id ?? view.activity_row_id;
              if (rowId != null) onOpenUnit(rowId);
            }}
            trailing={<StatusBadge tone="positive">Erledigt</StatusBadge>}
          />
        ))}
      </>
    );
  }

  if (entry.kind === "planned") {
    return (
      <WorkoutPreview
        sport={entrySport(entry)}
        name={entryName(entry)}
        meta={plannedMeta(entry)}
        onClick={() => {
          if (entry.plan_id != null) onOpenPlan(entry.plan_id);
        }}
        trailing={<StatusBadge>Geplant</StatusBadge>}
      />
    );
  }

  return (
    <WorkoutPreview
      sport={entrySport(entry)}
      name={entryName(entry)}
      meta={actualMeta(entry)}
      onClick={() => {
        const rowId = entry.activity?.row_id ?? entry.activity_row_id;
        if (rowId != null) onOpenUnit(rowId);
      }}
      trailing={<StatusBadge tone="positive">Erledigt</StatusBadge>}
    />
  );
}

function SourceNotice({
  source,
  label,
  retrying,
  onRetry,
}: {
  source: PlannerSource;
  label: string;
  retrying: PlannerSourceName | null;
  onRetry: () => void;
}) {
  if (source.state === "complete" || source.state === "empty") return null;
  const message =
    source.state === "error"
      ? `${label} konnten nicht geladen werden.`
      : source.state === "unavailable"
        ? `${label} für diesen Zeitraum sind noch nicht verfügbar.`
        : `${label} sind nur teilweise geladen.`;
  return (
    <div className="planner-source-notice" role="status">
      <p>
        {message}
        {source.error && <span className="planner-source-detail"> {source.error}</span>}
      </p>
      <button
        type="button"
        className="planner-retry"
        onClick={onRetry}
        disabled={retrying === source.source}
      >
        {retrying === source.source ? "Wird geladen…" : `${label} erneut laden`}
      </button>
    </div>
  );
}

function PlannerSkeleton() {
  return (
    <div className="planner-skeleton" aria-hidden="true">
      <div className="skeleton" style={{ height: 92 }} />
      <div className="skeleton" style={{ height: 84 }} />
      {[0, 1, 2, 3, 4, 5, 6].map((index) => (
        <div className="planner-skeleton-day" key={index}>
          <div className="skeleton" style={{ height: 18, width: "42%" }} />
          <div className="skeleton" style={{ height: 56 }} />
        </div>
      ))}
    </div>
  );
}
