import { useEffect, useRef, useState } from "react";

type Point = { date: string; load: number; ctl: number | null; atl: number | null };

const MAX = 100;

function monthLabel(iso: string): string {
  const date = new Date(`${iso}T00:00:00`);
  return date
    .toLocaleDateString("de-AT", { month: "short" })
    .replace(/\.$/, "");
}

export function LoadChart({ series }: { series: Point[] }) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(680);

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

  const narrow = width < 620;
  const height = narrow ? 190 : 260;
  const left = narrow ? 26 : 34;
  const right = 12;
  const top = 12;
  const bottom = narrow ? 24 : 28;

  const points = series.filter((point) => point.ctl != null || point.atl != null);
  const count = Math.max(points.length - 1, 1);
  const x = (index: number) => left + (index / count) * (width - left - right);
  const y = (value: number) => top + (1 - value / MAX) * (height - top - bottom);

  const line = (pick: (point: Point) => number | null) => {
    let path = "";
    let open = false;
    points.forEach((point, index) => {
      const value = pick(point);
      if (value == null) {
        open = false;
        return;
      }
      path += `${open ? "L" : "M"}${x(index).toFixed(1)},${y(value).toFixed(1)}`;
      open = true;
    });
    return path;
  };

  const months: { index: number; label: string }[] = [];
  points.forEach((point, index) => {
    const day = point.date.slice(8, 10);
    if (index === 0 || day === "01") {
      const label = monthLabel(point.date);
      const previous = months[months.length - 1];
      if (!previous || previous.label !== label) months.push({ index, label });
    }
  });

  const last = points[points.length - 1];
  const lastIndex = points.length - 1;

  return (
    <div ref={box}>
      <svg
        className="chart-svg"
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Fitness und Müdigkeit der letzten Wochen"
      >
        {[0, 25, 50, 75, 100].map((level) => (
          <g key={level}>
            <line
              x1={left}
              x2={width - right}
              y1={y(level)}
              y2={y(level)}
              stroke="var(--line)"
              strokeWidth="1"
            />
            <text
              x={left - 6}
              y={y(level) + 3.5}
              textAnchor="end"
              fill="var(--text-3)"
              fontSize={narrow ? 9 : 10}
              fontFamily="var(--mono)"
            >
              {level}
            </text>
          </g>
        ))}

        {points.map((point, index) => (
          <line
            key={`tick-${point.date}`}
            x1={x(index)}
            x2={x(index)}
            y1={height - bottom}
            y2={height - bottom + 5}
            stroke="var(--line-strong)"
            strokeWidth="1"
          />
        ))}

        <path
          d={line((point) => point.atl)}
          fill="none"
          stroke="var(--text-3)"
          strokeWidth="1.25"
          strokeDasharray="2 3"
          strokeLinecap="round"
        />
        <path d={line((point) => point.ctl)} fill="none" stroke="var(--text-2)" strokeWidth="1.5" />

        {last && (
          <>
            <line
              x1={x(lastIndex)}
              x2={x(lastIndex)}
              y1={top}
              y2={height - bottom}
              stroke="var(--accent)"
              strokeWidth="1"
            />
            {last.ctl != null && (
              <circle cx={x(lastIndex)} cy={y(last.ctl)} r="3" fill="var(--text)" />
            )}
          </>
        )}

        {months.map((month) => (
          <g key={`${month.label}-${month.index}`}>
            <line
              x1={x(month.index)}
              x2={x(month.index)}
              y1={height - bottom}
              y2={height - bottom + 4}
              stroke="var(--line-strong)"
              strokeWidth="1"
            />
            <text
              x={x(month.index)}
              y={height - 8}
              fill="var(--text-3)"
              fontSize={narrow ? 9 : 10}
              fontFamily="var(--mono)"
            >
              {month.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
