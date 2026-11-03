import { useState } from "react";
import { RecoveryDial } from "../components/RecoveryDial";
import { SessionSheet } from "../components/SessionSheet";
import { WeekStrip } from "../components/WeekStrip";
import { UnitSheet } from "../components/UnitSheet";
import { VendorScore } from "../components/VendorScore";
import { WeekSheet } from "../components/WeekSheet";
import { sportIcon } from "../components/sportIcon";
import { fmtClock, fmtDate, fmtDateLong, fmtKm, fmtMinutes, fmtNumber, fmtSpan } from "../format";
import type { Overview, RecoveryComponent, SessionRow, UnplannedUnit } from "../types";

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function driverPosition(component: RecoveryComponent): number {
  if (!component.baseline || component.today == null) return 50;
  const higherIsBetter = component.key !== "rhr";
  const relative = (component.today / component.baseline - 1) * (higherIsBetter ? 1 : -1);
  return clamp(50 + (relative / 0.2) * 40, 6, 94);
}

function driverToday(component: RecoveryComponent): string {
  if (component.today == null) return "—";
  if (component.unit === "h") return `${fmtClock(component.today)} h`;
  return `${fmtNumber(component.today)} ${component.unit}`;
}

function driverPlain(value: number | null | undefined, unit: string): string {
  if (value == null) return "—";
  return unit === "h" ? fmtClock(value) : fmtNumber(value);
}

export function Today({ data }: { data: Overview }) {
  const { today } = data;
  const [openSession, setOpenSession] = useState<number | null>(null);
  const [weekOpen, setWeekOpen] = useState(false);
  const [openUnit, setOpenUnit] = useState<number | null>(null);

  const recovery = today.recovery;
  const drivers = recovery.components.filter((component) => component.key !== "resp");
  const reference = recovery.reference ?? null;
  const recentScores = data.series.recovery.slice(-21);
  const seriesAverage =
    recentScores.length > 0
      ? Math.round(recentScores.reduce((sum, entry) => sum + entry.score, 0) / recentScores.length)
      : null;
  const referenceScore = reference?.average ?? seriesAverage;
  const referenceText = reference
    ? reference.nights < reference.minimum
      ? `Referenz ${reference.nights} von ${reference.minimum} Nächten`
      : referenceScore == null
        ? `Referenz ${reference.nights} von ${reference.target} Nächten`
        : `${reference.nights} von ${reference.target} Nächten · Schnitt ${referenceScore}`
    : referenceScore == null
      ? "21-Tage-Schnitt —"
      : `21-Tage-Schnitt ${referenceScore}`;
  const syncTime = new Date(data.generated_at).toLocaleTimeString("de-AT", {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>{fmtDateLong(today.date)}</h1>
          <p className="meta">Zuletzt synchronisiert {syncTime}</p>
        </div>
      </header>

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

      <article className="card recovery">
          <div className="card-head">
          <div>
            <h2>Erholung</h2>
            <p className="card-sub">
              {recovery.label === "Referenz wird aufgebaut"
                ? `Neuer Sensor · ${reference?.nights ?? 0} von ${reference?.minimum ?? 7} Nächten`
                : recovery.score == null
                  ? "Wartet auf die Nacht"
                  : `Nacht vom ${fmtDate(today.as_of ?? today.date, {
                      day: "numeric",
                      month: "long",
                    })}`}
            </p>
          </div>
          </div>

          <RecoveryDial
          score={recovery.score}
          band={recovery.band}
          label={recovery.label}
          referenceText={referenceText}
          referenceScore={referenceScore}
          />

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

          <p className="note">{recovery.explanation}</p>

          {recovery.vendor_prompt && (
            <VendorScore day={today.date} initial={today.vendor} score={recovery.score} />
          )}
          </div>
      </article>

      <section className="split">
        <TrainingCard
          sessions={data.sessions}
          unplanned={data.unplanned}
          onOpen={setOpenSession}
          onOpenUnit={setOpenUnit}
        />

        <aside className="card week">
          <div className="card-head">
            <div>
              <h2>Letzte 7 Tage</h2>
              <p className="card-sub">Umfang und Plan</p>
            </div>
          </div>

          <WeekStrip series={data.series.load} today={today.date} />

          <button type="button" className="week-row week-row-link" onClick={() => setWeekOpen(true)}>
            <span>Umfang</span>
            <span>
              {fmtSpan(today.load.week_seconds)}
              <span className="week-caret" aria-hidden="true">
                ›
              </span>
            </span>
          </button>
          <div className="week-row">
            <span>Belastung</span>
            <span>{fmtNumber(today.load.week_load)}</span>
          </div>
          <button type="button" className="week-row week-row-link" onClick={() => setWeekOpen(true)}>
            <span>Einheiten</span>
            <span>
              {today.load.week_sessions}
              <span className="week-caret" aria-hidden="true">
                ›
              </span>
            </span>
          </button>
          <div className="week-row">
            <span>Belastungsverhältnis</span>
            <span>{fmtNumber(today.load.acwr, 2)}</span>
          </div>
      </aside>
      </section>

      {openSession != null && (
        <SessionSheet id={openSession} onClose={() => setOpenSession(null)} />
      )}
      {weekOpen && (
        <WeekSheet
          onOpen={setOpenUnit}
          onClose={() => setWeekOpen(false)}
          top={openUnit == null}
        />
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
  onOpen,
  onOpenUnit,
}: {
  sessions: SessionRow[];
  unplanned: UnplannedUnit[];
  onOpen: (id: number) => void;
  onOpenUnit: (rowId: number) => void;
}) {
  const today = sessions.filter((session) => session.day === "today");
  const tomorrow = sessions.filter((session) => session.day === "tomorrow");
  const totalMinutes =
    today.reduce((sum, session) => sum + (session.minutes ?? 0), 0) +
    unplanned.reduce((sum, unit) => sum + (unit.minutes ?? 0), 0);
  const count = today.length + unplanned.length;
  const subtitle =
    count === 0
      ? "Nichts geplant"
      : `${count} ${count === 1 ? "Einheit" : "Einheiten"} · ${fmtMinutes(totalMinutes)}`;

  const row = (session: SessionRow) => {
    const Icon = sportIcon(session.sport);
    return (
      <button
        type="button"
        className="train-row"
        key={session.id}
        onClick={() => onOpen(session.id)}
      >
        <span className="train-ico">
          <Icon size={18} />
        </span>
        <span className="train-main">
          <span className="train-name">{session.name || session.sport_label}</span>
          <span className="train-meta">{sessionMeta(session)}</span>
        </span>
        <span className="train-state">{session.done ? "Erledigt" : "Geplant"}</span>
      </button>
    );
  };

  // Dazugekommen, ohne im Plan zu stehen: gleiche Zeile, andere Herkunft.
  const extraRow = (unit: UnplannedUnit) => {
    const Icon = sportIcon(unit.sport);
    const parts = [fmtMinutes(unit.minutes)];
    if (unit.km) parts.push(fmtKm(unit.km));
    return (
      <button
        type="button"
        className="train-row"
        key={`extra-${unit.row_id}`}
        onClick={() => onOpenUnit(unit.row_id)}
      >
        <span className="train-ico">
          <Icon size={18} />
        </span>
        <span className="train-main">
          <span className="train-name">{unit.name || unit.sport_label}</span>
          <span className="train-meta">{parts.join(" · ")}</span>
        </span>
        <span className="train-state">Zusätzlich</span>
      </button>
    );
  };

  return (
    <article className="card train">
      <div className="card-head">
        <div>
          <h2>Training</h2>
          <p className="card-sub">{subtitle}</p>
        </div>
      </div>

      {count > 0 && today.map(row)}
      {count === 0 && <p className="train-empty">Für heute steht nichts im Plan.</p>}
      {unplanned.map(extraRow)}

      {tomorrow.length > 0 && (
        <>
          <p className="train-lab">
            Morgen · {fmtDate(tomorrow[0].date, { weekday: "long", day: "numeric", month: "long" })}
          </p>
          {tomorrow.map(row)}
        </>
      )}
    </article>
  );
}
