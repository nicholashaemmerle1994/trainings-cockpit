import { useEffect, useId, useRef, useState } from "react";
import { fmtNumber } from "../format";
import type { SeriesPoint, UnitSeries } from "../types";

/**
 * Der Verlauf einer erledigten Einheit: Zeit auf der Waagerechten, der
 * aufgezeichnete Wert auf der Senkrechten.
 *
 * Die Hauptlinie trägt den Akzent — die Leistung beim Rad, das Tempo beim Lauf.
 * Der Puls läuft als zweite, ruhigere Linie mit; beim Rad fehlt er, weil zwei
 * Skalen (Watt und Schläge) im selben Bild nur verwirren. Beim Tempo ist die
 * Achse umgedreht: schneller ist oben.
 */
export function WorkoutChart({ series }: { series: UnitSeries }) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(348);
  const clip = useId();

  useEffect(() => {
    const element = box.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      const next = entries[0]?.contentRect.width;
      if (next) setWidth(next);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const kind = series.kind;
  const height = width < 520 ? 152 : 176;
  const left = kind === "pace" ? 40 : 34;
  const right = 8;
  const top = 14;
  const bottom = 18;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;

  const main = domain(kind, values(series.points, (point) => point.v), series.reference);
  const pulse = domain("hr", values(series.points, (point) => point.hr), null);
  const total = Math.max(series.duration_s, 1);

  const x = (seconds: number) => left + Math.min(seconds / total, 1) * plotWidth;
  const yMain = (value: number) =>
    kind === "pace"
      ? top + ((value - main[0]) / (main[1] - main[0])) * plotHeight
      : top + (1 - (value - main[0]) / (main[1] - main[0])) * plotHeight;
  const yPulse = (value: number) =>
    top + (1 - (value - pulse[0]) / (pulse[1] - pulse[0])) * plotHeight;

  const reference = kind === "power" ? series.reference : null;
  const showPulse = kind !== "power";

  return (
    <div className="workout" ref={box}>
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={`Aufgezeichneter Verlauf: ${legend(series)}`}
      >
        <defs>
          <clipPath id={clip}>
            <rect x={left} y={top - 1} width={plotWidth} height={plotHeight + 2} />
          </clipPath>
        </defs>

        {ticks(kind, main).map((tick) => (
          <g key={tick}>
            <line x1={left} x2={width - right} y1={yMain(tick)} y2={yMain(tick)} className="workout-grid" />
            <text x={left - 6} y={yMain(tick) + 3} textAnchor="end" className="workout-tick">
              {label(tick, kind)}
            </text>
          </g>
        ))}

        {reference != null && reference > main[0] && reference < main[1] && (
          <>
            <line
              x1={left}
              x2={width - right}
              y1={yMain(reference)}
              y2={yMain(reference)}
              className="workout-ref"
            />
            <text x={left + 2} y={yMain(reference) - 4} className="workout-ref-label">
              Schwelle {fmtNumber(reference)} W
            </text>
          </>
        )}

        <g clipPath={`url(#${clip})`}>
          {segments(series.points, (point) => point.v, x, yMain).map((points, index) => (
            <polyline key={`main-${index}`} points={points} className="workout-line" />
          ))}

          {showPulse &&
            segments(series.points, (point) => point.hr, x, yPulse).map((points, index) => (
              <polyline key={`puls-${index}`} points={points} className="workout-pulse" />
            ))}
        </g>

        <line x1={left} x2={width - right} y1={top + plotHeight} y2={top + plotHeight} className="workout-base" />

        {clockLabels(total).map((text, index) => (
          <text
            key={text}
            x={x((total * (index + 1)) / 4)}
            y={height - 4}
            textAnchor={index === 3 ? "end" : "middle"}
            className="workout-tick"
          >
            {text}
          </text>
        ))}
      </svg>
      <p className="workout-legend">{legend(series)}</p>
    </div>
  );
}

/** Was über dem Bild steht: worum es geht und was der Schnitt sagt. */
function legend(series: UnitSeries): string {
  if (series.kind === "pace") {
    const pulse = series.pulse != null ? ` · Puls ø ${fmtNumber(series.pulse)}` : "";
    return `Tempo ø ${pace(series.mean)} /km${pulse}`;
  }
  if (series.kind === "power") {
    return `Leistung ø ${fmtNumber(series.mean)} W · höchste ${fmtNumber(series.peak)} W`;
  }
  return `Puls ø ${fmtNumber(series.mean)} · höchste ${fmtNumber(series.peak)}`;
}

function pace(minPerKm: number | null): string {
  if (minPerKm == null) return "—";
  const seconds = Math.round(minPerKm * 60);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function label(value: number, kind: UnitSeries["kind"]): string {
  return kind === "pace" ? pace(value) : fmtNumber(value);
}

/** Die vier Zeitmarken unter dem Bild — gleiche Form, damit sie sich lesen lassen. */
function clockLabels(total: number): string[] {
  const long = total >= 90 * 60;
  return [0.25, 0.5, 0.75, 1].map((share, index) => {
    const minutes = Math.round((total * share) / 60);
    const text = long
      ? `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, "0")}`
      : String(minutes);
    return index === 3 ? `${text} ${long ? "h" : "min"}` : text;
  });
}

function values(points: SeriesPoint[], pick: (point: SeriesPoint) => number | null): number[] {
  return points.map(pick).filter((value): value is number => value != null);
}

/**
 * Der Bereich der Achse. Leistung beginnt bei null — sonst sieht jede Fahrt aus
 * wie ein Sägeblatt. Der Puls bekommt seinen vollen Bereich, weil er keine
 * Ausreißer kennt. Beim Tempo zählt der Bereich, in dem wirklich gelaufen
 * wurde: ein GPS-Sprung auf 3:00 min/km würde sonst alles platt drücken — was
 * darüber hinausgeht, schneidet der Rahmen ab.
 */
function domain(
  kind: UnitSeries["kind"],
  values: number[],
  reference: number | null,
): [number, number] {
  if (values.length === 0) return [0, 1];
  if (kind === "power") {
    const peak = Math.max(...values, reference ?? 0);
    return [0, Math.max(Math.ceil((peak * 1.05) / 25) * 25, 25)];
  }
  if (kind === "hr") {
    return [Math.min(...values) - 4, Math.max(...values) + 4];
  }
  const sorted = [...values].sort((left, right) => left - right);
  const low = sorted[Math.floor((sorted.length - 1) * 0.05)];
  const high = sorted[Math.floor((sorted.length - 1) * 0.95)];
  const pad = Math.max((high - low) * 0.15, 0.1);
  return [low - pad, high + pad];
}

/** Runde Marken statt krummer Zahlen: 0 · 75 · 150 · 225, 5:30 · 6:30 · 7:30. */
function ticks(kind: UnitSeries["kind"], [low, high]: [number, number]): number[] {
  const steps =
    kind === "pace"
      ? [0.25, 0.5, 1, 2, 5]
      : kind === "hr"
        ? [2, 5, 10, 20, 25]
        : [10, 25, 50, 75, 100, 150];
  // Beim Rad vier Linien, damit die Schwelle nicht in der obersten verschwindet.
  const limit = kind === "power" ? 4 : 5;
  const span = high - low;
  const step = steps.find((size) => span / size <= limit) ?? steps[steps.length - 1];
  const out: number[] = [];
  for (let value = Math.ceil(low / step) * step; value <= high + 1e-9; value += step) {
    out.push(Math.round(value * 1000) / 1000);
  }
  return out;
}

/** Eine Linie zerfällt in Stücke, wo die Aufzeichnung eine Lücke hat. */
function segments(
  points: SeriesPoint[],
  pick: (point: SeriesPoint) => number | null,
  x: (seconds: number) => number,
  y: (value: number) => number,
): string[] {
  const out: string[] = [];
  let current: string[] = [];
  for (const point of points) {
    const value = pick(point);
    if (value == null) {
      if (current.length > 1) out.push(current.join(" "));
      current = [];
      continue;
    }
    current.push(`${x(point.t).toFixed(1)},${y(value).toFixed(1)}`);
  }
  if (current.length > 1) out.push(current.join(" "));
  return out;
}
