import { useEffect, useMemo, useState } from "react";
import { AddWorkoutSheet, type NewPlanConfig } from "../components/AddWorkoutSheet";
import { IconBack, IconForward, IconPlus } from "../components/icons";
import { PlanSheet } from "../components/PlanSheet";
import { ScreenHeader } from "../components/ScreenHeader";
import { StatusBadge } from "../components/ui";
import { UnitSheet } from "../components/UnitSheet";
import { api } from "../api";
import { WorkoutPreview } from "../components/WorkoutPreview";
import {
  clearPlannerDraft,
  latestNewPlannerDraft,
  plannerDraftScope,
  type StoredPlannerDraft,
} from "../plannerDraftStore";
import { fmtDateLong, fmtKm, fmtMinutes, fmtNumber, fmtSpan } from "../format";
import { plannedMeta } from "../plannerFormat";
import { usePlannerWeek, type PlannerSourceName } from "../plannerQuery";
import { addDays, currentPlannerWeek } from "../routing";
import type {
  PlannerDay,
  PlannerDeleteResponse,
  PlannerEntry,
  PlannerSource,
  PlannerOperation,
  PlannerSaveResponse,
  PlannerSummaryEntry,
  PlannerWeekResponse,
} from "../types";

function withStart(start: string | null, text: string): string {
  return start ? `${start} · ${text}` : text;
}

function actualMeta(entry: PlannerEntry): string {
  const actual = entry.actual;
  if (!actual) return withStart(entry.start, "Ohne Messwerte");
  const parts = [fmtMinutes(actual.minutes), fmtKm(actual.km)].filter(
    (part) => part !== "—",
  );
  return withStart(entry.start, parts.join(" · ") || "Ohne Messwerte");
}

function linkedMeta(entry: PlannerEntry, linked?: PlannerEntry) {
  const parts = [actualMeta(entry)];
  const count = linked?.activities?.length ?? 0;
  if (count > 1) parts.push(`${count} Aufzeichnungen`);
  // Der Plan hängt am übergeordneten linked-Eintrag, nicht an der einzelnen
  // Aufzeichnung. Auf schmalen Schirmen steht er als eigene, gekürzte Zeile,
  // damit die Ist-Werte nicht mitten im Planbezug umbrechen.
  return (
    <>
      {parts.join(" · ")}
      {linked?.plan?.name && (
        <span className="train-meta-plan">Plan: {linked.plan.name}</span>
      )}
    </>
  );
}

function entrySport(entry: PlannerEntry): string {
  return entry.sport ?? entry.plan?.sport ?? "Other";
}

function entryName(entry: PlannerEntry): string {
  return entry.name || entry.plan?.name || entry.sport_label;
}

const OPERATION_STATES: Record<string, string> = {
  saving: "wird gespeichert",
  unknown: "unklar",
  savedUnverified: "ungeprüft",
  failed: "fehlgeschlagen",
  conflict: "Konflikt",
  saved: "gespeichert",
};

const TERMINAL_OPERATION_STATES = new Set(["saved", "failed", "conflict"]);

function operationStateLabel(state: string): string {
  return OPERATION_STATES[state] ?? state;
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
  accountId,
  athleteId,
  online,
  onWeekChange,
  openPlan,
  openUnit,
  onOpenPlan,
  onOpenUnit,
  onClosePlan,
  onCloseUnit,
  onCloseDetails,
  onGuardNavigation,
  revision = 0,
  onDataChanged,
}: {
  week: string;
  timeZone: string;
  accountId: string;
  athleteId: string;
  online: boolean;
  onWeekChange: (week: string) => void;
  openPlan: number | null;
  openUnit: number | null;
  onOpenPlan: (planId: number) => void;
  onOpenUnit: (rowId: number) => void;
  onClosePlan: () => void;
  onCloseUnit: () => void;
  onCloseDetails: (week?: string) => void;
  onGuardNavigation: (run: () => void) => boolean;
  revision?: number;
  onDataChanged?: () => void;
}) {
  const { data, loading, stale, error, retrying, reload, invalidate } =
    usePlannerWeek(week, revision);
  const [addDay, setAddDay] = useState<string | null>(null);
  const [newPlan, setNewPlan] = useState<NewPlanConfig | null>(null);
  const [operations, setOperations] = useState<PlannerOperation[]>([]);
  const [reconciling, setReconciling] = useState<string | null>(null);
  const [reconcileNote, setReconcileNote] = useState<{
    kind: "info" | "warning" | "error";
    text: string;
  } | null>(null);
  const [recoverNew, setRecoverNew] = useState<StoredPlannerDraft | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .openOperations()
      .then((result) => {
        if (alive) setOperations(result.items);
      })
      .catch(() => {
        /* Ein nicht erreichbarer Vorgangsstatus macht die Woche nicht leer. */
      });
    return () => {
      alive = false;
    };
  }, [revision]);

  const handleSaved = (result: PlannerSaveResponse) => {
    invalidate([week, result.old_week, result.week]);
    onDataChanged?.();
    setOperations((current) =>
      current.filter(
        (item) => item.operation_id !== result.status.operation_id,
      ),
    );
    setNewPlan(null);
    // Nach bestätigtem Speichern die komplette Detailkette verlassen. Der
    // abgeschlossene Entwurf bleibt nicht als Browser-Zurück-Ziel stehen.
    onCloseDetails(result.week ?? week);
  };

  const handleDeleted = (result: PlannerDeleteResponse) => {
    invalidate([week, result.week]);
    onDataChanged?.();
    // Die Woche bleibt stehen; nur das Blatt der gelöschten Einheit schließt.
    onCloseDetails(result.week);
  };

  useEffect(() => {
    setRecoverNew(latestNewPlannerDraft(accountId, athleteId));
  }, [accountId, athleteId, revision]);

  const reconcile = async (operation: PlannerOperation) => {
    setReconciling(operation.operation_id);
    setReconcileNote(null);
    try {
      const result = await api.reconcileOperation(operation.operation_id);
      const status = result.status;
      const terminal = TERMINAL_OPERATION_STATES.has(status.state);
      invalidate([week, result.week]);
      if (terminal) {
        setOperations((current) =>
          current.filter((item) => item.operation_id !== operation.operation_id),
        );
      } else {
        setOperations((current) =>
          current.map((item) =>
            item.operation_id === operation.operation_id
              ? {
                  ...item,
                  state: status.state,
                  remote_id: status.remote_id ?? item.remote_id,
                }
              : item,
          ),
        );
      }
      setReconcileNote({
        kind:
          status.error === "not_found"
            ? "warning"
            : status.state === "failed" || status.state === "conflict"
              ? "error"
              : "info",
        text:
          status.message ||
          (terminal
            ? "Der Vorgang ist abgeschlossen."
            : "Der Vorgang ist weiterhin offen."),
      });
      onDataChanged?.();
      if (result.week && result.week !== week) onWeekChange(result.week);
      else reload();
    } catch (error) {
      // Ein stiller Fehlschlag sähe aus, als hätte der Knopf nichts getan.
      setReconcileNote({
        kind: "error",
        text:
          error instanceof Error
            ? `Statusprüfung fehlgeschlagen: ${error.message}`
            : "Die Statusprüfung ist fehlgeschlagen.",
      });
    } finally {
      setReconciling(null);
    }
  };

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

      {operations.length > 0 && (
        <section className="planner-operation" aria-label="Offene Speichervorgänge">
          <p>
            {operations.length === 1
              ? "Ein Speichervorgang ist noch offen."
              : `${operations.length} Speichervorgänge sind noch offen.`}{" "}
            Der Status wird lesend geprüft; es wird nichts automatisch erneut
            angelegt.
          </p>
          {operations.map((operation) => (
            <div key={operation.operation_id} className="planner-operation__row">
              <span>
                {operation.mode === "create" ? "Neuanlage" : "Änderung"} ·{" "}
                {operationStateLabel(operation.state)}
                {operation.remote_id ? ` · Event ${operation.remote_id}` : ""}
              </span>
              <button
                type="button"
                className="btn btn--ghost"
                disabled={reconciling !== null}
                onClick={() => void reconcile(operation)}
              >
                {reconciling === operation.operation_id
                  ? "Wird geprüft…"
                  : "Status prüfen"}
              </button>
            </div>
          ))}
        </section>
      )}

      {reconcileNote && (
        <p
          className={`planner-operation-note planner-operation-note--${reconcileNote.kind}`}
          role={reconcileNote.kind === "error" ? "alert" : "status"}
        >
          {reconcileNote.text}
        </p>
      )}

      {!resolved && loading && <PlannerSkeleton />}

      {resolved && (
        <>
          {stale && loading && (
            <p className="planner-updating" role="status">
              Woche wird aktualisiert…
            </p>
          )}

          {!online && (
            <p className="planner-offline" role="status">
              Offline · bestätigter Stand vom{" "}
              {new Date(resolved.generated_at).toLocaleString("de-AT", {
                day: "2-digit",
                month: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
              })}. Es wird nichts remote gespeichert.
            </p>
          )}

          {recoverNew && openPlan == null && (
            <section
              className="planner-recover"
              aria-labelledby="planner-recover-title"
            >
              <h2 id="planner-recover-title">Lokaler Neuentwurf gefunden</h2>
              <p>
                {recoverNew.new_plan?.name || "Neue Einheit"} ·{" "}
                {recoverNew.new_plan
                  ? fmtDateLong(recoverNew.new_plan.date)
                  : recoverNew.date}{" "}
                · gespeichert {new Date(recoverNew.saved_at).toLocaleString("de-AT")}
              </p>
              <div className="planner-recover__actions">
                <button
                  type="button"
                  className="btn btn--primary"
                  onClick={() => {
                    const config = recoverNew.new_plan;
                    if (!config) return;
                    setRecoverNew(null);
                    setNewPlan(config);
                  }}
                >
                  Entwurf öffnen
                </button>
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() => {
                    clearPlannerDraft(
                      accountId,
                      athleteId,
                      plannerDraftScope(null, recoverNew.new_plan?.draftId),
                    );
                    setRecoverNew(null);
                  }}
                >
                  Verwerfen
                </button>
              </div>
            </section>
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
          revision={revision}
          linkPlans
          onLinkChanged={onDataChanged}
        />
      )}
      {openPlan != null && (
        <PlanSheet
          eventId={openPlan}
          accountId={accountId}
          athleteId={athleteId}
          online={online}
          onClose={onClosePlan}
          onSaved={handleSaved}
          onDeleted={handleDeleted}
          onPending={onDataChanged}
          revision={revision}
        />
      )}
      {newPlan != null && (
        <PlanSheet
          newPlan={newPlan}
          accountId={accountId}
          athleteId={athleteId}
          online={online}
          onClose={() => onGuardNavigation(() => setNewPlan(null))}
          onSaved={handleSaved}
          onPending={onDataChanged}
          revision={revision}
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
  onPrevious,
  onNext,
}: {
  week: string;
  label: string;
  calendarWeek: number | null;
  currentWeek: string;
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
      {/* Ruhiger Zustandstext: bestätigt nur, dass die aktuelle Woche angezeigt
          wird. Kein Klickziel, kein Fokus-Ziel. In jeder anderen Woche bleibt
          das Feld leer: kein Text, kein Knopf, keine Lücke. */}
      {week === currentWeek && (
        <span className="planner-week-current">Diese Woche</span>
      )}
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
            meta={linkedMeta(view, entry)}
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
