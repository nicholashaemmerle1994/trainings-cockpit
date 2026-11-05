import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtDate, fmtKm, fmtLiters, fmtMinutes, fmtNumber } from "../format";
import type { SessionDetail } from "../types";
import { SessionProfile } from "./SessionProfile";
import { Sheet } from "./Sheet";
import { MetricRow, StatusBadge } from "./ui";
import { WorkoutChart } from "./WorkoutChart";

function approx(value: string, estimated: boolean): string {
  return estimated ? `≈ ${value}` : value;
}

export function SessionSheet({ id, onClose }: { id: number; onClose: () => void }) {
  const [data, setData] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(null);
    api
      .session(id)
      .then((next) => {
        if (alive) setData(next);
      })
      .catch((cause: unknown) => {
        if (alive) setError(cause instanceof Error ? cause.message : "Einheit nicht geladen.");
      });
    return () => {
      alive = false;
    };
  }, [id]);

  return (
    <Sheet crumb="Einheit" label={data ? data.name : "Einheit"} onClose={onClose}>
      {error && <p className="sheet-error">{error}</p>}
      {!data && !error && <div className="sheet-loading" />}
      {data && <Body data={data} />}
    </Sheet>
  );
}

function Body({ data }: { data: SessionDetail }) {
  const duration = approx(fmtMinutes(data.minutes), data.estimated === "dauer");
  const distance = approx(fmtKm(data.km), data.estimated === "distanz");
  const date = fmtDate(data.date, { weekday: "long", day: "numeric", month: "long" });

  return (
    <>
      <h1 className="sheet-title">{data.name || data.sport_label}</h1>
      <p className="sheet-kind">
        {data.sport_label} · {date}
      </p>
      <div className="sheet-state">
        <StatusBadge tone={data.actual ? "positive" : "neutral"}>
          {data.actual ? "Erledigt" : "Geplant"}
        </StatusBadge>
      </div>

      {data.axis && data.steps.length > 0 && <SessionProfile axis={data.axis} steps={data.steps} />}

      <div className="sheet-cells">
        <div className="sheet-cell">
          <span className="n">{duration}</span>
          <span className="l">Dauer</span>
        </div>
        <div className="sheet-cell">
          <span className="n">{distance}</span>
          <span className="l">Distanz</span>
        </div>
        <div className="sheet-cell">
          <span className="n">{fmtNumber(data.load)}</span>
          <span className="l">Last</span>
        </div>
      </div>

      {data.steps.length > 0 && (
        <section className="sheet-sec">
          <h2>Struktur</h2>
          {data.steps.map((step, index) => (
            <div className="sheet-row" key={`${step.label}-${index}`}>
              <span className="sheet-row-name">{step.label}</span>
              <span className="sheet-row-mid">{step.distance_km ? fmtKm(step.distance_km) : fmtMinutes(step.minutes)}</span>
              <span className="sheet-row-target">{step.target}</span>
            </div>
          ))}
        </section>
      )}

      <section className="sheet-sec">
        <h2>Verpflegung</h2>
        {data.fuel ? (
          <>
            <MetricRow
              compact
              label="Kohlenhydrate"
              value={`${fmtNumber(data.fuel.carbs_g)} g · ${data.fuel.rate} g/h`}
            />
            {data.fuel.gels > 0 && (
              <MetricRow compact label="Gels" value={`${data.fuel.gels} × 22 g`} />
            )}
            <MetricRow compact label="Wasser" value={fmtLiters(data.fuel.water_ml)} />
            {data.fuel.sodium_mg > 0 && (
              <MetricRow compact label="Natrium" value={`${fmtNumber(data.fuel.sodium_mg)} mg`} />
            )}
          </>
        ) : (
          <MetricRow compact label="Unter 60 Minuten" value="Wasser reicht" />
        )}
      </section>

      {data.actual && (
        <section className="sheet-sec">
          <h2>Geplant · gemacht</h2>
          <div className="sheet-row sheet-row-head">
            <span />
            <span className="sheet-row-mid">Plan</span>
            <span className="sheet-row-actual">Gemacht</span>
          </div>
          <div className="sheet-row">
            <span className="sheet-row-name">Dauer</span>
            <span className="sheet-row-mid">{duration}</span>
            <span className="sheet-row-actual">{fmtMinutes(data.actual.minutes)}</span>
          </div>
          <div className="sheet-row">
            <span className="sheet-row-name">Distanz</span>
            <span className="sheet-row-mid">{distance}</span>
            <span className="sheet-row-actual">{fmtKm(data.actual.km)}</span>
          </div>
          <div className="sheet-row">
            <span className="sheet-row-name">Last</span>
            <span className="sheet-row-mid">{fmtNumber(data.load)}</span>
            <span className="sheet-row-actual">{fmtNumber(data.actual.load)}</span>
          </div>
          <div className="sheet-row">
            <span className="sheet-row-name">Intensität</span>
            <span className="sheet-row-mid">{data.intensity ? `${data.intensity} %` : "—"}</span>
            <span className="sheet-row-actual">
              {data.actual.intensity ? `${data.actual.intensity} %` : "—"}
            </span>
          </div>
          {data.actual.series && <WorkoutChart series={data.actual.series} />}
        </section>
      )}

      <p className="sheet-src">Plan aus intervals.icu</p>
    </>
  );
}
