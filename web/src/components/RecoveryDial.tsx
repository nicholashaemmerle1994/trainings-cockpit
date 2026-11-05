import { BAND_COLORS } from "../format";
import type { Band } from "../types";
import { IconPulse } from "./icons";

const SIZE = 220;
const CENTER = SIZE / 2;
const RING = 92;
const STROKE = 8;
const CIRCUMFERENCE = 2 * Math.PI * RING;

function polar(radius: number, percent: number): [number, number] {
  const angle = ((percent * 3.6 - 90) * Math.PI) / 180;
  return [CENTER + Math.cos(angle) * radius, CENTER + Math.sin(angle) * radius];
}

export function RecoveryDial({
  referenceScore,
  score,
  band,
  label,
  referenceText,
  baselineProgress,
}: {
  score: number | null;
  band: Band;
  label: string;
  referenceText: string;
  referenceScore: number | null;
  /** 0–1: wie weit die Referenz aufgebaut ist, nur ohne Score. */
  baselineProgress: number | null;
}) {
  const bandColor = BAND_COLORS[band] ?? BAND_COLORS.unknown;
  const progress =
    score != null
      ? Math.max(0, Math.min(100, score))
      : baselineProgress != null
        ? Math.max(0, Math.min(1, baselineProgress)) * 100
        : null;
  const offset = CIRCUMFERENCE * (1 - (progress ?? 0) / 100);
  const [refX1, refY1] = polar(100, referenceScore ?? 0);
  const [refX2, refY2] = polar(84, referenceScore ?? 0);

  return (
    <div className="dial">
      <svg
        width={SIZE}
        height={SIZE}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        role="img"
        aria-label={score == null ? label : `Erholung ${Math.round(score)} von 100`}
      >
        <circle
          cx={CENTER}
          cy={CENTER}
          r={RING}
          fill="none"
          stroke="var(--raised)"
          strokeWidth={STROKE}
        />

        {progress != null && (
          <circle
            cx={CENTER}
            cy={CENTER}
            r={RING}
            fill="none"
            stroke={score == null ? "var(--chart-neutral-strong)" : "var(--accent)"}
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={offset}
            transform={`rotate(-90 ${CENTER} ${CENTER})`}
            style={{
              transition: "stroke-dashoffset 700ms cubic-bezier(0.22, 1, 0.36, 1)",
              // Dezenter innerer Schein nur am Score-Ring (D-63); der
              // Referenzaufbau bleibt neutral.
              filter: score == null ? undefined : "drop-shadow(0 0 7px var(--recovery-ring-glow))",
            }}
          />
        )}

        {score != null && referenceScore != null && (
          <line
            x1={refX1}
            y1={refY1}
            x2={refX2}
            y2={refY2}
            stroke="var(--text-muted)"
            strokeWidth="2"
          />
        )}
      </svg>

      <div className="dial-center">
        <span className={`dial-score${score == null ? " blank" : ""}`}>
          {score == null ? "—" : Math.round(score)}
        </span>
        <span className="dial-band" style={score == null ? undefined : { color: bandColor }}>
          {label}
        </span>
        <span className="dial-ref">{referenceText}</span>
      </div>

      {score != null && (
        <div className="dial-center dial-center--pulse" aria-hidden="true">
          <IconPulse size={24} />
        </div>
      )}
    </div>
  );
}
