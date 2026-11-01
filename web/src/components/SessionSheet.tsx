import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import { fmtDate, fmtKm, fmtLiters, fmtMinutes, fmtNumber } from "../format";
import type { SessionDetail } from "../types";
import { IconBack, IconClose } from "./icons";
import { SessionProfile } from "./SessionProfile";

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

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose]);

  // Ein Portal ans Ende des Dokuments: `.page` trägt eine Eintritts-Animation
  // und damit einen eigenen Stapelkontext — darin läge das Blatt unter der
  // Tableiste und wäre an die Seite statt an das Fenster gebunden.
  return createPortal(
    <div className="sheet-backdrop" onClick={onClose} role="presentation">
      <div
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-label={data ? data.name : "Einheit"}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sheet-top">
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Zurück">
            <IconBack size={18} />
          </button>
          <span className="sheet-crumb">Einheit</span>
          <button type="button" className="icon-btn sheet-close" onClick={onClose} aria-label="Schließen">
            <IconClose size={18} />
          </button>
        </div>

        {error && <p className="sheet-error">{error}</p>}
        {!data && !error && <div className="sheet-loading" />}
        {data && <Body data={data} />}
      </div>
    </div>,
    document.body,
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
        <span className="chip">{data.actual ? "Erledigt" : "Geplant"}</span>
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
            <div className="sheet-kv">
              <span>Kohlenhydrate</span>
              <span>
                {fmtNumber(data.fuel.carbs_g)} g · {data.fuel.rate} g/h
              </span>
            </div>
            {data.fuel.gels > 0 && (
              <div className="sheet-kv">
                <span>Gels</span>
                <span>{data.fuel.gels} × 22 g</span>
              </div>
            )}
            <div className="sheet-kv">
              <span>Wasser</span>
              <span>{fmtLiters(data.fuel.water_ml)}</span>
            </div>
            {data.fuel.sodium_mg > 0 && (
              <div className="sheet-kv">
                <span>Natrium</span>
                <span>{fmtNumber(data.fuel.sodium_mg)} mg</span>
              </div>
            )}
          </>
        ) : (
          <div className="sheet-kv">
            <span>Unter 60 Minuten</span>
            <span>Wasser reicht</span>
          </div>
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
        </section>
      )}

      <p className="sheet-src">Plan aus intervals.icu</p>
    </>
  );
}
