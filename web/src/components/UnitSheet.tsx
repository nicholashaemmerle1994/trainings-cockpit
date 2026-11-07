import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtDateLong, fmtKm, fmtMinutes, fmtNumber, fmtPace } from "../format";
import { plannedMeta } from "../plannerFormat";
import type { UnitDetail, UnitPlanLinkContext } from "../types";
import { Sheet } from "./Sheet";
import { MetricRow, StatusBadge } from "./ui";
import { WorkoutChart } from "./WorkoutChart";

/** „08:05" aus dem Zeitstempel der Aufzeichnung. */
function clock(start: string): string {
  return start.slice(11, 16);
}

/** „2:15 /100 m" — die Zahl kommt in Minuten je 100 m, nicht in Sekunden. */
function pace100(minutes: number | null): string {
  if (minutes == null) return "—";
  const seconds = Math.round(minutes * 60);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")} /100 m`;
}

export function UnitSheet({
  rowId,
  onClose,
  plan,
  onOpenPlan,
  top = true,
  revision = 0,
  linkPlans = false,
  onLinkChanged,
}: {
  rowId: number;
  onClose: () => void;
  /** Nur bei einer bestätigten Beziehung: der zugehörige Plan bleibt erreichbar. */
  plan?: { id: number; name: string } | null;
  onOpenPlan?: (planId: number) => void;
  /** Liegt ein Planblatt darüber, schließt Escape nur dieses. */
  top?: boolean;
  /** Ein Sync/abgeschlossener Write lädt dieselbe Aufzeichnung neu. */
  revision?: number;
  /** Nur im Planer: Zuordnung zu einer Planung anbieten. */
  linkPlans?: boolean;
  onLinkChanged?: () => void;
}) {
  const [data, setData] = useState<UnitDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(null);
    api
      .unit(rowId)
      .then((next) => {
        if (alive) setData(next);
      })
      .catch((cause: unknown) => {
        if (alive) setError(cause instanceof Error ? cause.message : "Einheit nicht geladen.");
      });
    return () => {
      alive = false;
    };
  }, [rowId, revision]);

  return (
    <Sheet crumb="Einheit" label={data ? data.name : "Einheit"} onClose={onClose} top={top}>
      {error && <p className="sheet-error">{error}</p>}
      {!data && !error && <div className="sheet-loading" />}
      {data && (
        <Body
          data={data}
          plan={plan}
          onOpenPlan={onOpenPlan}
          linkPlans={linkPlans}
          onLinkChanged={onLinkChanged}
          revision={revision}
        />
      )}
    </Sheet>
  );
}

/** Nur, was die Aufzeichnung wirklich hergibt — leere Zeilen sagen nichts. */
function facts(data: UnitDetail): [string, string][] {
  const rows: [string, string][] = [];
  // Was der Verlauf zeigt, steht in seiner eigenen Zeile; hier bleibt der Rest.
  const charted = data.series != null;
  if (data.avg_hr && !charted) {
    const max = data.max_hr ? ` · ${fmtNumber(data.max_hr)} max` : "";
    rows.push(["Puls", `${fmtNumber(data.avg_hr)} bpm${max}`]);
  }
  if (data.pace_min_km != null && !charted) rows.push(["Tempo", fmtPace(data.pace_min_km)]);
  if (data.pace_100m != null) rows.push(["Tempo", pace100(data.pace_100m)]);
  if (data.speed_kmh != null && data.pace_min_km == null && data.pace_100m == null) {
    rows.push(["Schnitt", `${fmtNumber(data.speed_kmh, 1)} km/h`]);
  }
  if (data.total_min != null && data.total_min !== data.duration_min) {
    rows.push(["Mit Pausen", fmtMinutes(data.total_min)]);
  }
  if (data.intensity != null) rows.push(["Intensität", `${data.intensity} %`]);
  if (data.elevation_m != null) rows.push(["Höhenmeter", `${fmtNumber(data.elevation_m)} m`]);
  if (data.calories != null) rows.push(["Kalorien", `${fmtNumber(data.calories)} kcal`]);
  return rows;
}

function Body({
  data,
  plan,
  onOpenPlan,
  linkPlans,
  onLinkChanged,
  revision,
}: {
  data: UnitDetail;
  plan?: { id: number; name: string } | null;
  onOpenPlan?: (planId: number) => void;
  linkPlans: boolean;
  onLinkChanged?: () => void;
  revision: number;
}) {
  const date = fmtDateLong(data.date);
  const family = data.origin;
  return (
    <>
      <h1 className="sheet-title">{data.name || data.sport_label}</h1>
      <p className="sheet-kind">
        {data.sport_label} · {date} · {clock(data.start)}
      </p>
      <div className="sheet-state unit-state">
        <StatusBadge tone="positive">Erledigt</StatusBadge>
        {plan && onOpenPlan && (
          <button
            type="button"
            className="unit-plan-link"
            onClick={() => onOpenPlan(plan.id)}
          >
            Plan ansehen
            <span className="unit-plan-link__hint">{plan.name}</span>
          </button>
        )}
      </div>

      {data.series && <WorkoutChart series={data.series} />}

      <div className="sheet-cells">
        <div className="sheet-cell">
          <span className="n">{fmtMinutes(data.duration_min)}</span>
          <span className="l">Dauer</span>
        </div>
        <div className="sheet-cell">
          <span className="n">{data.distance_km ? fmtKm(data.distance_km) : "—"}</span>
          <span className="l">Distanz</span>
        </div>
        <div className="sheet-cell">
          <span className="n">{fmtNumber(data.load)}</span>
          <span className="l">Last</span>
        </div>
      </div>

      {data.zones.length > 0 && <ZoneBar zones={data.zones} source={data.zone_source} />}

      {facts(data).length > 0 && (
        <section className="sheet-sec">
          <h2>Zahlen</h2>
          {facts(data).map(([label, value]) => (
            <MetricRow key={label} compact label={label} value={value} />
          ))}
        </section>
      )}

      {linkPlans && (
        <PlanLinkSection
          rowId={data.row_id}
          revision={revision}
          onChanged={onLinkChanged}
        />
      )}

      <p className="sheet-src">Aufzeichnung aus {family}</p>
    </>
  );
}

/**
 * Zuordnung einer erledigten Einheit zu einer Planung.
 *
 * Die Woche zeigt eine bestätigte Paarung als einen Eintrag. Ohne eindeutige
 * Paarung bleiben beide sichtbar; hier wählt der Athlet die passende Planung
 * oder trennt eine automatische Zuordnung wieder.
 */
function PlanLinkSection({
  rowId,
  revision,
  onChanged,
}: {
  rowId: number;
  revision: number;
  onChanged?: () => void;
}) {
  const [data, setData] = useState<UnitPlanLinkContext | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(null);
    setMessage(null);
    api
      .unitPlanLink(rowId)
      .then((next) => {
        if (alive) setData(next);
      })
      .catch((cause: unknown) => {
        if (alive) {
          setError(
            cause instanceof Error ? cause.message : "Zuordnung nicht geladen.",
          );
        }
      });
    return () => {
      alive = false;
    };
  }, [rowId, revision, attempt]);

  const run = async (
    key: string,
    action: () => Promise<UnitPlanLinkContext>,
    done: string,
  ) => {
    setBusy(key);
    setError(null);
    setMessage(null);
    try {
      const next = await action();
      setData(next);
      setMessage(done);
      onChanged?.();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Verknüpfung fehlgeschlagen.",
      );
    } finally {
      setBusy(null);
    }
  };

  if (!data) {
    return (
      <section className="sheet-sec unit-link">
        <h2>Planung</h2>
        {error ? (
          <>
            <p className="sheet-error">{error}</p>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => setAttempt((current) => current + 1)}
            >
              Erneut laden
            </button>
          </>
        ) : (
          <div className="sheet-loading" />
        )}
      </section>
    );
  }

  const linked = data.linked;
  const unavailable =
    data.plans_state === "error" || data.plans_state === "unavailable";
  const unlink = async () => {
    const planId = linked?.plan_id;
    if (planId == null) return;
    await run(
      "unlink",
      () => api.unlinkUnitPlan(rowId, planId),
      "Verknüpfung getrennt.",
    );
  };
  return (
    <section className="sheet-sec unit-link" aria-labelledby={`unit-link-${rowId}`}>
      <h2 id={`unit-link-${rowId}`}>Planung</h2>

      {linked ? (
        <>
          <p className="unit-link__text">
            {linked.source === "auto" ? "Automatisch verknüpft mit" : "Verknüpft mit"}{" "}
            <strong>{linked.name}</strong>
            {linked.date && linked.date !== data.date
              ? ` · ${fmtDateLong(linked.date)}`
              : ""}
          </p>
          {linked.source === "auto" && (
            <p className="unit-link__hint">
              An diesem Tag gab es genau eine passende Planung und Aufzeichnung.
            </p>
          )}
          {linked.plan_id != null && (
            <div className="unit-link__actions">
              <button
                type="button"
                className="btn btn--ghost"
                disabled={busy !== null}
                onClick={() => void unlink()}
              >
                {busy === "unlink" ? "Wird getrennt…" : "Verknüpfung trennen"}
              </button>
            </div>
          )}
        </>
      ) : unavailable ? (
        <p className="unit-link__text">
          Planungen sind für diesen Tag nicht verfügbar.
          {data.plans_error && (
            <span className="unit-link__hint"> {data.plans_error}</span>
          )}
        </p>
      ) : data.candidates.length === 0 ? (
        <p className="unit-link__text">Keine offene Planung an diesem Tag.</p>
      ) : (
        <>
          <p className="unit-link__text">
            Keine eindeutige Zuordnung. Wähle die passende Planung – danach
            erscheint die Einheit im Planer nur einmal.
          </p>
          <ul className="unit-link__list">
            {data.candidates.map((candidate) => {
              const planId = candidate.plan_id;
              if (planId == null) return null;
              return (
                <li key={candidate.key}>
                  <button
                    type="button"
                    className="unit-link__option"
                    disabled={busy !== null}
                    onClick={() =>
                      void run(
                        `link:${planId}`,
                        () => api.linkUnitPlan(rowId, planId),
                        "Verknüpft.",
                      )
                    }
                  >
                    <span className="unit-link__option-main">
                      <span className="unit-link__option-name">
                        {candidate.name || candidate.sport_label}
                      </span>
                      <span className="unit-link__option-meta">
                        {candidate.separated ? "Getrennt · " : ""}
                        {plannedMeta(candidate)}
                      </span>
                    </span>
                    <span className="unit-link__option-action">
                      {busy === `link:${planId}`
                        ? "Verbinde…"
                        : candidate.separated
                          ? "Wieder verbinden"
                          : "Verbinden"}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {message && (
        <p className="planner-updating" role="status">
          {message}
        </p>
      )}
      {error && <p className="sheet-error">{error}</p>}
    </section>
  );
}

/** Zeit in den Zonen als ein Balken: wo die Einheit wirklich verbracht wurde. */
function ZoneBar({ zones, source }: { zones: UnitDetail["zones"]; source: string | null }) {
  const belegt = zones.filter((zone) => zone.share > 0.005);
  return (
    <div className="zones">
      <div className="zones-bar">
        {belegt.map((zone) => (
          <span
            className="zones-part"
            key={zone.zone}
            style={{ flexGrow: zone.share, opacity: 0.34 + zone.zone * 0.13 }}
            title={`Zone ${zone.zone}: ${Math.round(zone.share * 100)} %`}
          />
        ))}
      </div>
      <div className="zones-legend">
        {belegt.map((zone) => (
          <span key={zone.zone}>
            Z{zone.zone} {Math.round(zone.share * 100)} %
          </span>
        ))}
      </div>
      {source && <p className="zones-src">Zonen nach {source}</p>}
    </div>
  );
}
