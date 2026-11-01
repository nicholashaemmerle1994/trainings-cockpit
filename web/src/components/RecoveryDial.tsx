import { BAND_COLORS } from "../format";
import type { Band } from "../types";

const SIZE = 252;
const CENTER = SIZE / 2;
const RING = 96;
const ZONE_RING = 104;
const CIRCUMFERENCE = 2 * Math.PI * RING;

const ZONES: { from: number; to: number; color: string }[] = [
  { from: 0, to: 35, color: "var(--bad)" },
  { from: 35, to: 50, color: "var(--low)" },
  { from: 50, to: 70, color: "var(--mid)" },
  { from: 70, to: 100, color: "var(--good)" },
];

function polar(radius: number, percent: number): [number, number] {
  const angle = ((percent * 3.6 - 90) * Math.PI) / 180;
  return [CENTER + Math.cos(angle) * radius, CENTER + Math.sin(angle) * radius];
}

function zoneArc(from: number, to: number): { length: number; gap: number; rotate: number } {
  const length = ((to - from) / 100) * 2 * Math.PI * ZONE_RING;
  const gap = 2 * Math.PI * ZONE_RING - length;
  return { length, gap, rotate: -90 + from * 3.6 };
}

export function RecoveryDial({
  referenceScore,
  score,
  band,
  label,
  referenceText,
}: {
  score: number | null;
  band: Band;
  label: string;
  referenceText: string;
  referenceScore: number | null;
}) {
  const color = BAND_COLORS[band] ?? BAND_COLORS.unknown;
  const value = score ?? 0;
  const offset = CIRCUMFERENCE * (1 - value / 100);
  const [refX1, refY1] = polar(98, referenceScore ?? 0);
  const [refX2, refY2] = polar(90, referenceScore ?? 0);

  return (
    <div className="dial">
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} role="img"
        aria-label={score == null ? "Keine Daten" : `Erholung ${Math.round(score)} von 100`}>
        <g stroke="var(--line-strong)" strokeWidth="1">
          {Array.from({ length: 60 }, (_, index) => {
            const long = index % 5 === 0;
            const [x1, y1] = polar(long ? 108 : 113, (index / 60) * 100);
            const [x2, y2] = polar(119, (index / 60) * 100);
            return <line key={index} x1={x1} y1={y1} x2={x2} y2={y2} opacity={long ? 1 : 0.5} />;
          })}
        </g>

        <g fill="none" strokeWidth="3" opacity="0.3">
          {ZONES.map((zone) => {
            const arc = zoneArc(zone.from, zone.to);
            return (
              <circle
                key={zone.color + zone.from}
                cx={CENTER}
                cy={CENTER}
                r={ZONE_RING}
                stroke={zone.color}
                strokeDasharray={`${arc.length.toFixed(1)} ${arc.gap.toFixed(1)}`}
                transform={`rotate(${arc.rotate} ${CENTER} ${CENTER})`}
              />
            );
          })}
        </g>

        <circle cx={CENTER} cy={CENTER} r={RING} fill="none" stroke="var(--raised)" strokeWidth="6" />

        {score != null && (
          <circle
            cx={CENTER}
            cy={CENTER}
            r={RING}
            fill="none"
            stroke={color}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={offset}
            transform={`rotate(-90 ${CENTER} ${CENTER})`}
            style={{ transition: "stroke-dashoffset 700ms cubic-bezier(0.22, 1, 0.36, 1)" }}
          />
        )}

        {referenceScore != null && (
          <line x1={refX1} y1={refY1} x2={refX2} y2={refY2} stroke="var(--text-2)" strokeWidth="2" />
        )}
      </svg>

      <div className="dial-center">
        <span className={`dial-score${score == null ? " blank" : ""}`}>{score == null ? "—" : Math.round(score)}</span>
        <span className="dial-band" style={score == null ? undefined : { color }}>
          {label}
        </span>
        <span className="dial-ref">{referenceText}</span>
      </div>
    </div>
  );
}
