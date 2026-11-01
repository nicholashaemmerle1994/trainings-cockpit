import { useState } from "react";
import { api } from "../api";
import { RecoveryDial } from "../components/RecoveryDial";
import { SessionSheet } from "../components/SessionSheet";
import { WeekStrip } from "../components/WeekStrip";
import { IconBike, IconRun, IconSwim, IconWeights } from "../components/icons";
import { StatCard } from "../components/ui";
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
import type { Overview, RecoveryComponent, SessionRow } from "../types";

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

export function Today({
  data,
  onRefresh,
  onSync,
  syncing,
}: {
  data: Overview;
  onRefresh: () => void;
  onSync: () => void;
  syncing: boolean;
}) {
  const { today } = data;
  const [bevel, setBevel] = useState(today.vendor != null ? String(Math.round(today.vendor)) : "");
  const [saved, setSaved] = useState(false);
  const [openSession, setOpenSession] = useState<number | null>(null);
  const compared = data.series.recovery.filter((entry) => entry.vendor != null).slice(-7);

  const saveBevel = async () => {
    const value = Number(bevel);
    if (bevel.trim() === "" || Number.isNaN(value) || value < 0 || value > 100) return;
    await api.vendorScore(today.date, value);
    setSaved(true);
    onRefresh();
  };

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
        <button type="button" className="btn" onClick={onSync} disabled={syncing}>
          {syncing ? "Synchronisiert…" : "Aktualisieren"}
        </button>
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

      <section className="hero">
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
        </article>

        <div className="right">
          <div className="stats">
            <StatCard
              label="Schlaf"
              value={fmtClock(today.sleep.hours)}
              unit="h"
              sub={`Schlafscore ${today.sleep.score ?? "—"} · Defizit ${fmtNumber(today.sleep.debt_7d, 1)} h`}
            />
            <StatCard
              label="HRV"
              value={fmtNumber(today.hrv.value)}
              unit="ms"
              sub={`Schnitt ${fmtNumber(today.hrv.average)} · üblich ${fmtNumber(today.hrv.baseline)} ms`}
            />
            <StatCard
              label="Ruhepuls"
              value={fmtNumber(today.rhr.value)}
              unit="bpm"
              sub={`Schnitt ${fmtNumber(today.rhr.average)} · üblich ${fmtNumber(today.rhr.baseline)} bpm`}
            />
          </div>

          <section className="card bevel">
            <div className="card-head">
              <div>
                <h2>Bevel-Abgleich</h2>
                <p className="card-sub">Zweite Meinung zum selben Morgen</p>
              </div>
              <div className="bevel-field">
                <span>Bevel heute</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  inputMode="numeric"
                  enterKeyHint="done"
                  value={bevel}
                  placeholder="—"
                  onChange={(event) => {
                    setBevel(event.target.value);
                    setSaved(false);
                  }}
                  onBlur={() => void saveBevel()}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      event.currentTarget.blur();
                    }
                  }}
                />
              </div>
            </div>

            {compared.length > 0 ? (
              [...compared]
                .reverse()
                .slice(0, 3)
                .map((entry) => (
                  <div className="bevel-row" key={entry.date}>
                    <span className="d">
                      {fmtDate(entry.date, { weekday: "short", day: "numeric", month: "short" })} ·{" "}
                      {compared.length} von 7 Tagen
                    </span>
                    <span className="pair">
                      <span>wir {entry.score}</span>
                      <span>Bevel {Math.round(entry.vendor ?? 0)}</span>
                      <span style={{ color: "var(--text-3)" }}>
                        {fmtSigned(entry.score - (entry.vendor ?? 0))}
                      </span>
                    </span>
                  </div>
                ))
            ) : (
              <div className="bevel-row">
                <span className="d">
                  {saved ? "Gespeichert" : "Noch kein Tag erfasst"} · Ziel sind sieben
                </span>
              </div>
            )}
          </section>
        </div>
      </section>

      <section className="split">
        <TrainingCard sessions={data.sessions} onOpen={setOpenSession} />

        <aside className="card week">
          <div className="card-head">
            <div>
              <h2>Letzte 7 Tage</h2>
              <p className="card-sub">Umfang und Plan</p>
            </div>
          </div>

          <WeekStrip series={data.series.load} today={today.date} />

          <div className="week-row">
            <span>Umfang</span>
            <span>{fmtSpan(today.load.week_seconds)}</span>
          </div>
          <div className="week-row">
            <span>Belastung</span>
            <span>{fmtNumber(today.load.week_load)}</span>
          </div>
          <div className="week-row">
            <span>Einheiten</span>
            <span>{today.load.week_sessions}</span>
          </div>
          <div className="week-row">
            <span>Belastungsverhältnis</span>
            <span>{fmtNumber(today.load.acwr, 2)}</span>
          </div>

        </aside>
      </section>

      {openSession != null && (
        <SessionSheet id={openSession} onClose={() => setOpenSession(null)} />
      )}
    </div>
  );
}

const SPORT_ICONS: Record<string, typeof IconRun> = {
  Ride: IconBike,
  VirtualRide: IconBike,
  EBikeRide: IconBike,
  GravelRide: IconBike,
  MountainBikeRide: IconBike,
  Run: IconRun,
  VirtualRun: IconRun,
  TrailRun: IconRun,
  Swim: IconSwim,
  OpenWaterSwim: IconSwim,
  WeightTraining: IconWeights,
};

function sessionMeta(session: SessionRow): string {
  const duration = `${session.estimated === "dauer" ? "≈ " : ""}${fmtMinutes(session.minutes)}`;
  const distance = `${session.estimated === "distanz" ? "≈ " : ""}${fmtKm(session.km)}`;
  const parts = session.primary === "distance" ? [distance, duration] : [duration, distance];
  return parts.join(" · ");
}

function TrainingCard({
  sessions,
  onOpen,
}: {
  sessions: SessionRow[];
  onOpen: (id: number) => void;
}) {
  const today = sessions.filter((session) => session.day === "today");
  const tomorrow = sessions.filter((session) => session.day === "tomorrow");
  const totalMinutes = today.reduce((sum, session) => sum + (session.minutes ?? 0), 0);
  const count = today.length;
  const subtitle =
    count === 0
      ? "Nichts geplant"
      : `${count} ${count === 1 ? "Einheit" : "Einheiten"} · ${fmtMinutes(totalMinutes)}`;

  const row = (session: SessionRow) => {
    const Icon = SPORT_ICONS[session.sport] ?? IconRun;
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
