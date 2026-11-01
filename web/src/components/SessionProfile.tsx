import { useEffect, useRef, useState } from "react";
import type { SessionAxis, SessionStep } from "../types";

/**
 * Der geplante Verlauf einer Einheit: Zeit auf der Waagerechten, das Ziel
 * (Watt, Prozent der Schwelle oder der Herzfrequenz) auf der Senkrechten.
 *
 * Arbeit trägt den Akzent, alles andere bleibt neutral. Die Fläche unter dem
 * Band zeigt, dass es hier um Blöcke geht und nicht um eine Kurve — der Plan
 * kennt keine Zwischenwerte.
 */
export function SessionProfile({ axis, steps }: { axis: SessionAxis; steps: SessionStep[] }) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(350);

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

  const narrow = width < 520;
  const height = narrow ? 164 : 196;
  const left = axis.unit.length > 2 ? 50 : 36;
  const right = 8;
  const top = 10;
  const bottom = 18;
  const total = steps.reduce((sum, step) => sum + step.minutes, 0) || 1;

  const y = (value: number) => top + (1 - (value - axis.from) / (axis.to - axis.from)) * (height - top - bottom);
  const x = (minutes: number) => left + (minutes / total) * (width - left - right);

  let walked = 0;
  const blocks = steps.map((step, index) => {
    const x0 = x(walked);
    const x1 = x(walked + step.minutes);
    walked += step.minutes;
    const colour = step.work ? "var(--accent)" : "var(--text-3)";
    const block = { key: index, colour, x0, x1, step, band: null as null | { top: number; height: number } };
    if (step.lo != null && step.hi != null) {
      const high = y(step.hi);
      const low = y(step.lo);
      block.band = { top: high, height: Math.max(2, low - high) };
    }
    return block;
  });

  return (
    <div className="profile" ref={box}>
      <svg width={width} height={height} role="img" aria-label={`Geplanter Verlauf in ${axis.unit}`}>
        {axis.ticks.map((tick) => (
          <g key={tick}>
            <line x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} className="profile-grid" />
            <text x={left - 6} y={y(tick) + 3} textAnchor="end" className="profile-tick">
              {tick} {axis.unit}
            </text>
          </g>
        ))}

        {blocks.map(({ key, colour, x0, x1, band }) => {
          const boxWidth = Math.max(1, x1 - x0 - 1);
          return (
            <g key={key}>
              {band && (
                <>
                  <rect
                    x={x0 + 0.5}
                    y={band.top}
                    width={boxWidth}
                    height={height - bottom - band.top}
                    rx={1.5}
                    fill={colour}
                    fillOpacity={0.12}
                  />
                  <rect
                    x={x0 + 0.5}
                    y={band.top}
                    width={boxWidth}
                    height={band.height}
                    rx={1.5}
                    fill={colour}
                    fillOpacity={0.3}
                  />
                  <line x1={x0 + 0.5} x2={x1 - 0.5} y1={band.top} y2={band.top} stroke={colour} strokeWidth={2} />
                </>
              )}
            </g>
          );
        })}

        <line x1={left} x2={width - right} y1={height - bottom} y2={height - bottom} className="profile-base" />
        <text x={width - right} y={height - 4} textAnchor="end" className="profile-tick">
          {total >= 60 ? `${fmtSpan(total)}` : `${Math.round(total)} min`}
        </text>
      </svg>
    </div>
  );
}

function fmtSpan(minutes: number): string {
  const total = Math.round(minutes);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return `${h} h ${String(m).padStart(2, "0")} min`;
}
