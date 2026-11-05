import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtDateLong, fmtKm, fmtMinutes, fmtNumber, fmtPace } from "../format";
import type { UnitDetail } from "../types";
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

export function UnitSheet({ rowId, onClose }: { rowId: number; onClose: () => void }) {
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
  }, [rowId]);

  return (
    <Sheet crumb="Einheit" label={data ? data.name : "Einheit"} onClose={onClose}>
      {error && <p className="sheet-error">{error}</p>}
      {!data && !error && <div className="sheet-loading" />}
      {data && <Body data={data} />}
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

function Body({ data }: { data: UnitDetail }) {
  const date = fmtDateLong(data.date);
  const family = data.origin;
  return (
    <>
      <h1 className="sheet-title">{data.name || data.sport_label}</h1>
      <p className="sheet-kind">
        {data.sport_label} · {date} · {clock(data.start)}
      </p>
      <div className="sheet-state">
        <StatusBadge tone="positive">Erledigt</StatusBadge>
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

      <p className="sheet-src">Aufzeichnung aus {family}</p>
    </>
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
