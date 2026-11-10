import { useState } from "react";
import { RecoveryDial } from "../components/RecoveryDial";
import { ScreenHeader } from "../components/ScreenHeader";
import { SessionSheet } from "../components/SessionSheet";
import { WeekStrip } from "../components/WeekStrip";
import { UnitSheet } from "../components/UnitSheet";
import { VendorScore } from "../components/VendorScore";
import { WorkoutPreview } from "../components/WorkoutPreview";
import { DashboardCard, MetricRow, StatusBadge, type BadgeTone } from "../components/ui";
import {
  fmtClock,
  fmtDate,
  fmtDateLong,
  fmtKm,
  fmtMinutes,
  fmtNumber,
  fmtSigned,
  fmtSpan,
} from "../format";
import type { Band, Overview, RecoveryComponent, SessionRow, UnplannedUnit } from "../types";

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/** Die Erholungsfarbe kommt aus der Band-Skala, nicht aus dem Akzent (D-66). */
const BAND_TONES: Record<Band, BadgeTone> = {
  "green-top": "band-top",
  green: "band-good",
  amber: "band-mid",
  orange: "band-low",
  red: "band-bad",
  unknown: "neutral",
};

function driverPosition(component: RecoveryComponent): number {
  if (!component.baseline || component.today == null) return 50;
  const higherIsBetter = component.key !== "rhr";
  const relative = (component.today / component.baseline - 1) * (higherIsBetter ? 1 : -1);
  return clamp(50 + (relative / 0.2) * 40, 6, 94);
}

function valueWithUnit(value: number | null | undefined, unit: string): string {
  if (value == null) return "—";
  return unit === "h" ? `${fmtClock(value)} h` : `${fmtNumber(value)} ${unit}`;
}

function driverToday(component: RecoveryComponent): string {
  return valueWithUnit(component.today, component.unit);
}

function driverPlain(value: number | null | undefined, unit: string): string {
  if (value == null) return "—";
  return unit === "h" ? fmtClock(value) : fmtNumber(value);
}

type Delta = { text: string; tone: "good" | "bad" | "flat" };

/** Delta zur eigenen Referenz — gerechnet aus den vorhandenen Feldern, nichts erfunden. */
function deltaPercent(
  value: number | null | undefined,
  baseline: number | null | undefined,
  average: number | null | undefined,
): Delta | null {
  const reference = baseline ?? average;
  if (value == null || reference == null || reference === 0) return null;
  return deltaTone(Math.round((value / reference - 1) * 100), true, " %");
}

function deltaNumber(
  value: number | null | undefined,
  baseline: number | null | undefined,
  average: number | null | undefined,
  unit: string,
  higherIsBetter: boolean,
  scale = 1,
): Delta | null {
  const reference = baseline ?? average;
  if (value == null || reference == null) return null;
  return deltaTone(Math.round((value - reference) * scale), higherIsBetter, ` ${unit}`);
}

function deltaTone(delta: number, higherIsBetter: boolean, suffix: string): Delta {
  const higher = delta > 0;
  const tone = delta === 0 ? "flat" : higher === higherIsBetter ? "good" : "bad";
  return { text: `${fmtSigned(delta)}${suffix}`, tone };
}

export function Today({ data }: { data: Overview }) {
  const { today } = data;
  const [openSession, setOpenSession] = useState<number | null>(null);
  const [openUnit, setOpenUnit] = useState<number | null>(null);

  const recovery = today.recovery;
  const hasScore = recovery.score != null;
  const drivers = recovery.components.filter((component) => component.key !== "resp");
  // Mit Score treten die Nachtwerte mobil an die Stelle der Treiberzeile;
  // ohne Score bleiben sie sichtbar (D-58).
  const componentFor = (key: string) => recovery.components.find((entry) => entry.key === key);
  const hrv = componentFor("hrv");
  const rhr = componentFor("rhr");
  const sleep = componentFor("sleep");
  // Mit Score zeigen die Nachtwerte dieselbe Nacht wie der Score (recovery.date).
  // Ohne Score bleiben die Werte der letzten Nacht sichtbar (D-58); die dürfen
  // nicht mit einer älteren Score-Nacht gemischt werden.
  const hrvValue = hasScore ? (hrv?.today ?? null) : today.hrv.value;
  const rhrValue = hasScore ? (rhr?.today ?? null) : today.rhr.value;
  const sleepValue = hasScore ? (sleep?.today ?? null) : today.sleep.hours;
  const nightly = [
    {
      key: "hrv",
      label: "HRV",
      value: hrvValue,
      unit: "ms",
      delta: deltaPercent(hrvValue, hrv?.baseline, hrv?.average),
    },
    {
      key: "rhr",
      label: "Ruhepuls",
      value: rhrValue,
      unit: "bpm",
      delta: deltaNumber(rhrValue, rhr?.baseline, rhr?.average, "bpm", false),
    },
    {
      key: "sleep",
      label: "Schlaf",
      value: sleepValue,
      unit: "h",
      delta: deltaNumber(sleepValue, sleep?.baseline, sleep?.average, "min", true, 60),
    },
  ];
  const showNightly =
    nightly.some((row) => row.value != null) && (hasScore || drivers.length === 0);
  const nightDate = recovery.date ?? today.as_of ?? today.date;
  const nightText = `Nacht vom ${fmtDate(nightDate, {
    day: "numeric",
    month: "long",
  })}`;
  const cardSubtitle =
    recovery.label === "Referenz wird aufgebaut"
      ? "Neuer Sensor"
      : recovery.score == null
        ? "Wartet auf die Nacht"
        : nightText;
  const reference = recovery.reference ?? null;
  const referenceTarget = reference?.target ?? 60;
  const recentScores = data.series.recovery.slice(-referenceTarget);
  const seriesAverage =
    recentScores.length > 0
      ? Math.round(recentScores.reduce((sum, entry) => sum + entry.score, 0) / recentScores.length)
      : null;
  const referenceScore = reference?.average ?? seriesAverage;
  const baselineProgress =
    reference && reference.minimum > 0 ? Math.min(1, reference.nights / reference.minimum) : null;
  const referenceText = reference
    ? reference.nights < reference.minimum
      ? `${reference.nights} von ${reference.minimum} Nächten`
      : referenceScore == null
        ? `Referenz ${reference.nights} von ${reference.target} Nächten`
        : `${reference.nights} von ${reference.target} Nächten · Schnitt ${referenceScore}`
    : referenceScore == null
      ? "60-Tage-Schnitt —"
      : `60-Tage-Schnitt ${referenceScore}`;
  const warnings = recovery.triggeredRules ?? [];
  const syncTime = new Date(data.generated_at).toLocaleTimeString("de-AT", {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="page">
      <ScreenHeader date={fmtDateLong(today.date)} meta={`Zuletzt synchronisiert ${syncTime}`} />

      {data.goals.length > 0 && (
        <section className="countdowns">
          {data.goals.map((goal) => (
            <div className="countdown" key={`${goal.name}-${goal.date}`}>
              <div className="cd-top">
                <span className="cd-n">{goal.days}</span>
                <span className="cd-u">Tage</span>
              </div>
              <span className="cd-name">{goal.name}</span>
            </div>
          ))}
        </section>
      )}

      <DashboardCard
        as="article"
        className={hasScore ? "recovery has-score" : "recovery"}
        title="Erholung"
        subtitle={cardSubtitle}
      >
        <div className="recovery-hero">
          {recovery.score != null && (
            <div className="recovery-summary">
              <p className="recovery-score">
                <span className="recovery-score__value">{Math.round(recovery.score)}</span>
                <span className="recovery-score__unit">/ 100</span>
              </p>
              <StatusBadge tone={BAND_TONES[recovery.band]}>{recovery.label}</StatusBadge>
              <p className="recovery-night">{nightText}</p>
              <p className="recovery-ref">{referenceText}</p>
            </div>
          )}

          <RecoveryDial
            score={recovery.score}
            band={recovery.band}
            label={recovery.label}
            referenceText={referenceText}
            referenceScore={referenceScore}
            baselineProgress={baselineProgress}
          />
        </div>

        <div className="recovery-side">
          {drivers.length > 0 && (
          <table className="drivers">
            <thead>
              <tr>
                <th />
                <th>heute</th>
                <th>Schnitt</th>
                <th>üblich</th>
              </tr>
            </thead>
            <tbody>
              {drivers.map((component) => (
                <tr key={component.key}>
                  <td>
                    {component.label}
                    <i className="track">
                      <u />
                      <b style={{ left: `${driverPosition(component)}%` }} />
                    </i>
                  </td>
                  <td className="today">{driverToday(component)}</td>
                  <td className="avg">{driverPlain(component.average, component.unit)}</td>
                  <td className="base">{driverPlain(component.baseline, component.unit)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          )}

          {showNightly && (
            <div className="night">
              <p className="night-head">Letzte Nacht</p>
              <dl className="night-grid">
                {nightly.map((row) => {
                  const text =
                    row.value == null
                      ? "—"
                      : row.unit === "h"
                        ? fmtClock(row.value)
                        : fmtNumber(row.value);
                  const unit = row.value == null ? "" : row.unit;
                  return (
                    <div className="night-metric" key={row.key}>
                      <dt>{row.label}</dt>
                      <dd>
                        {text}
                        {unit && <span className="night-unit">{unit}</span>}
                        {hasScore && row.delta && (
                          <span
                            className={`night-delta${
                              row.delta.tone === "good"
                                ? " night-delta--good"
                                : row.delta.tone === "bad"
                                  ? " night-delta--bad"
                                  : ""
                            }`}
                          >
                            {row.delta.text}
                          </span>
                        )}
                      </dd>
                    </div>
                  );
                })}
              </dl>
            </div>
          )}

          <p className="note">{recovery.explanation}</p>

          {warnings.length > 0 && (
            <div className="recovery-warnings">
              <p className="recovery-warnings-head">Warnregeln</p>
              <ul className="recovery-warnings-list">
                {warnings.map((rule) => (
                  <li key={rule.id}>
                    <span>{rule.label}</span>
                    <span className="recovery-warnings-penalty">{fmtSigned(rule.adjustment)}</span>
                  </li>
                ))}
              </ul>
              {recovery.adjustment != null && recovery.adjustment < 0 && (
                <p className="recovery-warnings-total">
                  Abzug {fmtSigned(recovery.adjustment)} Punkte
                </p>
              )}
            </div>
          )}

          {recovery.vendor_prompt && (
            <VendorScore day={today.date} initial={today.vendor} score={recovery.score} />
          )}
          </div>
      </DashboardCard>

      <section className="split">
        <TrainingCard
          sessions={data.sessions}
          unplanned={data.unplanned}
          planSource={data.today.plan_source}
          onOpen={setOpenSession}
          onOpenUnit={setOpenUnit}
        />

        <DashboardCard as="aside" className="week" title="Letzte 7 Tage" subtitle="Umfang und Plan">
          <WeekStrip series={data.series.load} today={today.date} />

          <MetricRow label="Umfang" value={fmtSpan(today.load.week_seconds)} />
          <MetricRow label="Belastung" value={fmtNumber(today.load.week_load)} />
          <MetricRow label="Einheiten" value={today.load.week_sessions} />
          <MetricRow label="Belastungsverhältnis" value={fmtNumber(today.load.acwr, 2)} />
        </DashboardCard>
      </section>

      {openSession != null && (
        <SessionSheet id={openSession} onClose={() => setOpenSession(null)} />
      )}
      {openUnit != null && (
        <UnitSheet rowId={openUnit} onClose={() => setOpenUnit(null)} />
      )}
    </div>
  );
}

function sessionMeta(session: SessionRow): string {
  const duration = `${session.estimated === "dauer" ? "≈ " : ""}${fmtMinutes(session.minutes)}`;
  const distance = `${session.estimated === "distanz" ? "≈ " : ""}${fmtKm(session.km)}`;
  const parts = session.primary === "distance" ? [distance, duration] : [duration, distance];
  return parts.join(" · ");
}

function TrainingCard({
  sessions,
  unplanned,
  planSource,
  onOpen,
  onOpenUnit,
}: {
  sessions: SessionRow[];
  unplanned: UnplannedUnit[];
  planSource: Overview["today"]["plan_source"];
  onOpen: (id: number) => void;
  onOpenUnit: (rowId: number) => void;
}) {
  const today = sessions.filter((session) => session.day === "today");
  const tomorrow = sessions.filter((session) => session.day === "tomorrow");
  const totalMinutes =
    today.reduce((sum, session) => sum + (session.minutes ?? 0), 0) +
    unplanned.reduce((sum, unit) => sum + (unit.minutes ?? 0), 0);
  const count = today.length + unplanned.length;
  // „Nichts geplant“ ist eine Aussage über den Planungsanteil, nicht über
  // eine fehlende oder noch nicht geladene Quelle.
  const planKnownEmpty = planSource.complete && today.length === 0;
  const subtitle =
    count > 0
      ? `${count} ${count === 1 ? "Einheit" : "Einheiten"} · ${fmtMinutes(totalMinutes)}`
      : planKnownEmpty
        ? "Nichts geplant"
        : planSource.state === "error"
          ? "Planungen nicht verfügbar"
          : planSource.state === "unavailable"
            ? "Planungen für heute nicht verfügbar"
            : planSource.state === "partial"
              ? "Planungen nur teilweise geladen"
              : "Planungen werden geladen";

  const sessionRow = (session: SessionRow) => (
    <WorkoutPreview
      key={session.id}
      sport={session.sport}
      name={session.name || session.sport_label}
      meta={sessionMeta(session)}
      onClick={() => onOpen(session.id)}
      trailing={
        <StatusBadge tone={session.done ? "positive" : "neutral"}>
          {session.done ? "Erledigt" : "Geplant"}
        </StatusBadge>
      }
    />
  );

  // Dazugekommen, ohne im Plan zu stehen: gleiche Zeile, andere Herkunft.
  const extraRow = (unit: UnplannedUnit) => {
    const parts = [fmtMinutes(unit.minutes)];
    if (unit.km) parts.push(fmtKm(unit.km));
    return (
      <WorkoutPreview
        key={`extra-${unit.row_id}`}
        sport={unit.sport}
        name={unit.name || unit.sport_label}
        meta={parts.join(" · ")}
        onClick={() => onOpenUnit(unit.row_id)}
        trailing={<StatusBadge>Zusätzlich</StatusBadge>}
      />
    );
  };

  return (
    <DashboardCard as="article" className="train" title="Training" subtitle={subtitle}>
      {count > 0 && today.map(sessionRow)}
      {count === 0 && (
        <p className="train-empty">
          {planKnownEmpty
            ? "Für heute steht nichts im Plan."
            : "Der Planungsanteil für heute ist nicht vollständig bekannt."}
        </p>
      )}
      {unplanned.map(extraRow)}

      {tomorrow.length > 0 && (
        <>
          <p className="train-lab">
            Morgen · {fmtDate(tomorrow[0].date, { weekday: "long", day: "numeric", month: "long" })}
          </p>
          {tomorrow.map(sessionRow)}
        </>
      )}
    </DashboardCard>
  );
}
