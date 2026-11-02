import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtDateLong, fmtKm, fmtMinutes, fmtNumber, fmtSpan } from "../format";
import type { WeekResponse, WeekUnit } from "../types";
import { Sheet } from "./Sheet";
import { sportIcon } from "./sportIcon";

function meta(unit: WeekUnit): string {
  const parts = [fmtMinutes(unit.duration_min)];
  if (unit.distance_km) parts.push(fmtKm(unit.distance_km));
  return parts.join(" · ");
}

/** „Heute", „Gestern" oder der Wochentag — die Liste ist kurz genug dafür. */
function dayLabel(iso: string, today: string): string {
  const day = new Date(`${iso}T00:00:00`).getTime();
  const now = new Date(`${today}T00:00:00`).getTime();
  const ago = Math.round((now - day) / 86_400_000);
  if (ago === 0) return "Heute";
  if (ago === 1) return "Gestern";
  return fmtDateLong(iso);
}

export function WeekSheet({
  onOpen,
  onClose,
  top,
}: {
  onOpen: (rowId: number) => void;
  onClose: () => void;
  top: boolean;
}) {
  const [data, setData] = useState<WeekResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .week()
      .then((next) => {
        if (alive) setData(next);
      })
      .catch((cause: unknown) => {
        if (alive) setError(cause instanceof Error ? cause.message : "Woche nicht geladen.");
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <Sheet crumb="Letzte 7 Tage" label="Letzte 7 Tage" onClose={onClose} top={top}>
      {error && <p className="sheet-error">{error}</p>}
      {!data && !error && <div className="sheet-loading" />}
      {data && <Body data={data} onOpen={onOpen} />}
    </Sheet>
  );
}

function Body({ data, onOpen }: { data: WeekResponse; onOpen: (rowId: number) => void }) {
  // Nach Tag gruppiert, neuester Tag zuerst — die Einheit von heute steht oben.
  const days: { day: string; units: WeekUnit[] }[] = [];
  for (const unit of data.units) {
    const last = days[days.length - 1];
    if (last && last.day === unit.date) last.units.push(unit);
    else days.push({ day: unit.date, units: [unit] });
  }
  days.reverse();

  return (
    <>
      <h1 className="sheet-title">Letzte 7 Tage</h1>
      <p className="sheet-kind">
        {fmtDateLong(data.from)} bis {fmtDateLong(data.to)}
      </p>

      <div className="sheet-cells">
        <div className="sheet-cell">
          <span className="n">{fmtSpan(data.seconds)}</span>
          <span className="l">Umfang</span>
        </div>
        <div className="sheet-cell">
          <span className="n">{fmtNumber(data.load)}</span>
          <span className="l">Belastung</span>
        </div>
        <div className="sheet-cell">
          <span className="n">{data.units.length}</span>
          <span className="l">Einheiten</span>
        </div>
      </div>

      {days.length === 0 && <p className="train-empty">Keine Einheit in diesen sieben Tagen.</p>}

      {days.map(({ day, units }) => (
        <section className="sheet-sec" key={day}>
          <h2>{dayLabel(day, data.to)}</h2>
          {units.map((unit) => {
            const Icon = sportIcon(unit.sport);
            return (
              <button
                type="button"
                className="train-row"
                key={unit.row_id}
                onClick={() => onOpen(unit.row_id)}
              >
                <span className="train-ico">
                  <Icon size={18} />
                </span>
                <span className="train-main">
                  <span className="train-name">{unit.name || unit.sport_label}</span>
                  <span className="train-meta">{meta(unit)}</span>
                </span>
                <span className="train-state">{fmtNumber(unit.load)}</span>
              </button>
            );
          })}
        </section>
      ))}

      <p className="sheet-src">Aufzeichnungen aus Garmin und intervals.icu</p>
    </>
  );
}
