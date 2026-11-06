import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { fmtDateLong } from "../format";
import type {
  PlanDetail,
  PlanGraph,
  PlanGraphSegment,
  PlanGraphTrack,
  PlanNode,
} from "../types";
import { Sheet } from "./Sheet";
import { StatusBadge } from "./ui";

export function PlanSheet({
  eventId,
  onClose,
}: {
  eventId: number;
  onClose: () => void;
}) {
  const [data, setData] = useState<PlanDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(null);
    setSelected(null);
    api
      .planDetail(eventId)
      .then((next) => {
        if (alive) setData(next);
      })
      .catch((cause: unknown) => {
        if (alive) setError(cause instanceof Error ? cause.message : "Planung nicht geladen.");
      });
    return () => {
      alive = false;
    };
  }, [eventId]);

  return (
    <Sheet
      crumb="Geplante Einheit"
      label={data ? data.name || data.sport_label : "Geplante Einheit"}
      onClose={onClose}
    >
      {error && <p className="sheet-error">{error}</p>}
      {!data && !error && <div className="sheet-loading" />}
      {data && (
        <PlanBody
          data={data}
          selected={selected}
          onSelect={(nodeId) =>
            setSelected((current) => (current === nodeId ? null : nodeId))
          }
        />
      )}
    </Sheet>
  );
}

function PlanBody({
  data,
  selected,
  onSelect,
}: {
  data: PlanDetail;
  selected: string | null;
  onSelect: (nodeId: string) => void;
}) {
  const date = fmtDateLong(data.date);
  const repetitions = data.graph.repetition_groups.reduce(
    (sum, group) => sum + group.repetitions,
    0,
  );
  const targetCount = data.graph.tracks.filter((track) => track.kind !== "none").length;

  return (
    <>
      <h1 className="sheet-title">{data.name || data.sport_label}</h1>
      <p className="sheet-kind">
        {data.sport_label} · {date}
        {data.time ? ` · ${data.time}` : ""}
      </p>
      <div className="plan-state">
        <StatusBadge>Geplant</StatusBadge>
        <span
          className={`plan-rights plan-rights--${data.rights.editability}`}
          title={data.rights.reason ?? undefined}
        >
          {data.rights.label}
        </span>
      </div>

      <div className="plan-hero">
        <div>
          <strong>{data.known.text}</strong>
          {data.known.has_unknown && (
            <span className="plan-hero__hint">Offene Abschnitte sind nicht enthalten.</span>
          )}
        </div>
        <span className="plan-hero__side">
          {repetitions > 0
            ? `${repetitions} ${repetitions === 1 ? "Wiederholung" : "Wiederholungen"}`
            : `${data.known.executions} ${data.known.executions === 1 ? "Abschnitt" : "Abschnitte"}`}
          {targetCount > 1 ? ` · ${targetCount} Zielarten` : ""}
        </span>
      </div>

      <WorkoutProfile graph={data.graph} selected={selected} onSelect={onSelect} />

      <section className="sheet-sec plan-structure" aria-label="Aufbau der Planung">
        <h2>Aufbau</h2>
        {data.nodes.length === 0 && (
          <p className="plan-note">Für diese Planung liegt kein Aufbau vor.</p>
        )}
        <PlanNodeList nodes={data.nodes} selected={selected} onSelect={onSelect} />
      </section>

      <section className="sheet-sec">
        <h2>Planungsnotiz</h2>
        {data.notes ? (
          <p className="plan-note plan-note--text">{data.notes}</p>
        ) : (
          <p className="plan-note">Keine Planungsnotiz hinterlegt.</p>
        )}
      </section>

      <section className="sheet-sec">
        <h2>Berechtigungen</h2>
        <p className="plan-note">
          Leseansicht. {data.rights.reason ?? "Die Quelle meldet keine Einschränkung."}
        </p>
        {data.rights.restriction_codes.length > 0 && (
          <p className="plan-note plan-note--muted">
            Erhaltungsgrenzen: {data.rights.restriction_codes.join(", ")}.
          </p>
        )}
        <p className="plan-note plan-note--muted">
          Öffnen und Auswählen speichern nichts. Messwerte und Zonen einer Aufzeichnung
          bleiben in der bestehenden Aktivitätsansicht.
        </p>
      </section>

      <p className="sheet-src">
        Plan aus {data.source.name}
        {data.source.remote_id ? ` · Event ${data.source.remote_id}` : ""} · nur lesend
      </p>
    </>
  );
}

function PlanNodeList({
  nodes,
  selected,
  onSelect,
}: {
  nodes: PlanNode[];
  selected: string | null;
  onSelect: (nodeId: string) => void;
}) {
  return (
    <ol className="plan-nodes">
      {nodes.map((node, index) => (
        <PlanNodeItem
          key={node.node_id}
          node={node}
          index={index + 1}
          selected={selected}
          onSelect={onSelect}
        />
      ))}
    </ol>
  );
}

function PlanNodeItem({
  node,
  index,
  selected,
  onSelect,
}: {
  node: PlanNode;
  index: number;
  selected: string | null;
  onSelect: (nodeId: string) => void;
}) {
  if (node.kind === "repeat") {
    const active = selected === node.node_id;
    return (
      <li className="plan-node-item plan-node-item--group">
        <button
          type="button"
          className={`plan-node${active ? " plan-node--selected" : ""}`}
          aria-pressed={active}
          onClick={() => onSelect(node.node_id)}
        >
          <span className="plan-node__index">{index}</span>
          <span className="plan-node__main">
            <span className="plan-node__name">{repeatTitle(node)}</span>
            <span className="plan-node__meta">
              {node.children?.length
                ? node.children.map((child) => child.name || child.label).filter(Boolean).join(" / ")
                : "Keine Kindabschnitte"}
              {node.skip_final_recovery ? " · letzte Erholung entfällt" : ""}
            </span>
          </span>
          <span className="plan-node__caret" aria-hidden="true">
            ›
          </span>
        </button>
        {node.children && node.children.length > 0 && (
          <ol className="plan-node__children">
            {node.children.map((child, childIndex) => (
              <PlanNodeItem
                key={child.node_id}
                node={child}
                index={childIndex + 1}
                selected={selected}
                onSelect={onSelect}
              />
            ))}
          </ol>
        )}
      </li>
    );
  }

  if (node.kind === "unsupported") {
    return (
      <li className="plan-node-item">
        <div className="plan-node plan-node--unsupported">
          <span className="plan-node__index">{index}</span>
          <span className="plan-node__main">
            <span className="plan-node__name">{node.label || "Nicht unterstützter Abschnitt"}</span>
            <span className="plan-node__meta">{node.reason}</span>
          </span>
          <span className="plan-node__badge">Nicht bearbeitbar</span>
        </div>
      </li>
    );
  }

  const active = selected === node.node_id;
  const meta = [node.end?.text, node.target?.text].filter(Boolean).join(" · ");
  return (
    <li className="plan-node-item">
      <button
        type="button"
        className={`plan-node${active ? " plan-node--selected" : ""}`}
        aria-pressed={active}
        onClick={() => onSelect(node.node_id)}
      >
        <span className="plan-node__index">{index}</span>
        <span className="plan-node__main">
          <span className="plan-node__name">{node.name || "Abschnitt"}</span>
          <span className="plan-node__meta">{meta || "Ohne Vorgabe"}</span>
        </span>
        <span className="plan-node__caret" aria-hidden="true">
          ›
        </span>
      </button>
    </li>
  );
}

function repeatTitle(node: PlanNode): string {
  const repetitions = node.repetitions ?? 1;
  const name = (node.name || "Wiederholung").trim();
  const cleaned = name.replace(/\s*\d+\s*[x×]\s*$/i, "").trim();
  if (cleaned && cleaned !== name) return `${repetitions} × ${cleaned}`;
  if (new RegExp(`^${repetitions}\\s*[x×]`).test(name)) return name;
  return `${repetitions} × ${name}`;
}

function unitLabel(unit: string | undefined): string {
  if (!unit) return "";
  if (unit === "secondsPerKm") return "min/km";
  if (unit === "secondsPer100m") return "/100 m";
  if (unit === "percentFtp") return "% FTP";
  if (unit === "watts") return "W";
  if (unit === "zone") return "Zone";
  if (unit === "none") return "";
  return unit;
}

const TRACK_LABELS: Record<string, string> = {
  heartRate: "HF",
  pace: "Pace",
  power: "Leistung",
  none: "Ohne Ziel",
};

function WorkoutProfile({
  graph,
  selected,
  onSelect,
}: {
  graph: PlanGraph;
  selected: string | null;
  onSelect: (nodeId: string) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(350);

  useEffect(() => {
    const element = box.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      const next = entries[0]?.contentRect.width;
      if (next) setWidth(Math.max(240, next));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const compact = width < 520;
  const left = compact ? 44 : 72;
  const right = 10;
  const top = 4;
  const trackHeight = compact ? 38 : 46;
  const gap = 10;
  const axisHeight = 26;
  const tracks = graph.tracks.length > 0 ? graph.tracks : [emptyTrack()];
  const height = top + tracks.length * (trackHeight + gap) + axisHeight;
  const laneWidth = Math.max(60, width - left - right);
  const axis = graph.axis;
  const subline =
    tracks.length > 1
      ? "Getrennte Spuren, gemeinsame Achse. Jede Spur hat ihre eigene Skala."
      : graph.segments.length > 1
        ? "Geplante Abschnitte; Breite und Position folgen dem Umfang."
        : "Geplanter Abschnitt.";

  return (
    <figure className="wprofile" ref={box}>
      <figcaption className="wprofile__head">
        <span className="wprofile__title">Trainingsverlauf</span>
        <span className="wprofile__axis-title">
          {axis.mode === "schematic"
            ? "Abschnitte · schematisch"
            : `${axis.label} (${axis.unit})`}
        </span>
      </figcaption>
      <p className="wprofile__sub">{subline}</p>
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={graph.text_alternative}
        className="wprofile__svg"
      >
        {tracks.map((track, trackIndex) => {
          const laneTop = top + trackIndex * (trackHeight + gap);
          return (
            <g key={track.key}>
              <text
                x={left - 8}
                y={laneTop + trackHeight / 2 + 1}
                textAnchor="end"
                className="wprofile__track-label"
              >
                {compact ? track.short : TRACK_LABELS[track.metric] ?? track.short}
              </text>
              <text
                x={left - 8}
                y={laneTop + trackHeight / 2 + 14}
                textAnchor="end"
                className="wprofile__track-unit"
              >
                {unitLabel(track.unit)}
              </text>
              <rect
                x={left}
                y={laneTop}
                width={laneWidth}
                height={trackHeight}
                rx={5}
                className="wprofile__lane"
              />
              {track.kind === "numeric" && track.domain && (
                <NumericTicks
                  track={track}
                  laneTop={laneTop}
                  trackHeight={trackHeight}
                  left={left}
                  width={laneWidth}
                />
              )}
              {track.segments.map((segment) => (
                <Segment
                  key={`${track.key}-${segment.position}`}
                  segment={segment}
                  track={track}
                  laneTop={laneTop}
                  trackHeight={trackHeight}
                  left={left}
                  laneWidth={laneWidth}
                  selected={isSelected(segment, selected)}
                  onSelect={onSelect}
                />
              ))}
              {track.segments.length === 0 && (
                <text
                  x={left + laneWidth / 2}
                  y={laneTop + trackHeight / 2 + 4}
                  textAnchor="middle"
                  className="wprofile__empty"
                >
                  Kein Ziel in dieser Spur
                </text>
              )}
            </g>
          );
        })}

        {graph.segments.map((segment) => {
          if (segment.kind !== "compression") return null;
          const x = left + segment.start_fraction * laneWidth;
          const segmentWidth = Math.max(10, segment.width_fraction * laneWidth);
          return (
            <g key={`compression-${segment.position}`}>
              <rect
                x={x + 1}
                y={top}
                width={Math.max(4, segmentWidth - 2)}
                height={tracks.length * (trackHeight + gap) - gap}
                rx={4}
                className="wprofile__compression"
              />
              <text
                x={x + segmentWidth / 2}
                y={top + 13}
                textAnchor="middle"
                className="wprofile__compression-label"
              >
                +{segment.omitted_executions}
              </text>
            </g>
          );
        })}

        <Axis
          axis={graph.axis}
          left={left}
          width={laneWidth}
          y={top + tracks.length * (trackHeight + gap) + 6}
        />
      </svg>
      <p className="wprofile__note">
        {graph.tracks.some((track) => track.direction === "faster-up")
          ? "Pace: schnellere Vorgaben liegen höher. "
          : ""}
        {graph.tracks.length > 1
          ? `${joinGerman([...new Set(graph.tracks.map((track) => track.short))])} teilen keine gemeinsame Skala.`
          : graph.tracks[0]?.kind === "zone"
            ? "Zonen bleiben ihre eigene Einheit; bpm erscheinen nur als aufgelöste Beschriftung."
            : "Die Höhe gilt nur innerhalb dieser Spur."}
        {graph.totals.compressed_executions > 0
          ? ` ${graph.totals.compressed_executions} Ausführungen sind als Block zusammengefasst; die Summe bleibt ${graph.totals.text}`
          : ""}
      </p>
      <p className="sr-only">{graph.text_alternative}</p>
    </figure>
  );
}

function NumericTicks({
  track,
  laneTop,
  trackHeight,
  left,
  width,
}: {
  track: PlanGraphTrack;
  laneTop: number;
  trackHeight: number;
  left: number;
  width: number;
}) {
  const ticks = track.ticks ?? [];
  if (ticks.length === 0) return null;
  const first = ticks[0];
  const last = ticks[ticks.length - 1];
  return (
    <>
      <text
        x={left + width - 4}
        y={laneTop + (track.direction === "faster-up" ? 11 : trackHeight - 4)}
        textAnchor="end"
        className="wprofile__value-label"
      >
        {first.label}
      </text>
      <text
        x={left + width - 4}
        y={laneTop + (track.direction === "faster-up" ? trackHeight - 4 : 11)}
        textAnchor="end"
        className="wprofile__value-label"
      >
        {last.label}
      </text>
    </>
  );
}

function Segment({
  segment,
  track,
  laneTop,
  trackHeight,
  left,
  laneWidth,
  selected,
  onSelect,
}: {
  segment: PlanGraphSegment;
  track: PlanGraphTrack;
  laneTop: number;
  trackHeight: number;
  left: number;
  laneWidth: number;
  selected: boolean;
  onSelect: (nodeId: string) => void;
}) {
  const x = left + segment.start_fraction * laneWidth;
  const width = Math.max(2, segment.width_fraction * laneWidth - 1);
  const active = segment.role === "work";
  const fill = active ? "var(--accent)" : "var(--chart-neutral-strong)";
  const className = selected ? "wprofile__block wprofile__block--selected" : "wprofile__block";
  const label = `${segment.name} · ${segment.extent_text}${
    segment.target_text ? ` · ${segment.target_text}` : ""
  }${segment.repetition_index ? ` · Wiederholung ${segment.repetition_index}` : ""}`;

  if (track.kind === "numeric" && track.domain && segment.target?.values) {
    const values = segment.target.values;
    const from = mapValue(values.min, track, laneTop, trackHeight);
    const to = mapValue(values.max, track, laneTop, trackHeight);
    const y = Math.min(from, to);
    const barHeight = Math.max(3, Math.abs(to - from));
    return (
      <rect
        x={x + 0.5}
        y={y}
        width={width}
        height={barHeight}
        rx={1.5}
        fill={fill}
        fillOpacity={selected ? 0.95 : 0.72}
        stroke={selected ? "var(--accent-hover)" : undefined}
        strokeWidth={selected ? 1.5 : 0}
        className={className}
        onClick={() => onSelect(segment.node_id)}
      >
        <title>{label}</title>
      </rect>
    );
  }

  return (
    <rect
      x={x + 0.5}
      y={laneTop + 7}
      width={width}
      height={trackHeight - 14}
      rx={4}
      fill={fill}
      fillOpacity={selected ? 0.95 : active ? 0.65 : 0.38}
      stroke={selected ? "var(--accent-hover)" : undefined}
      strokeWidth={selected ? 1.5 : 0}
      className={className}
      onClick={() => onSelect(segment.node_id)}
    >
      <title>{label}</title>
    </rect>
  );
}

function mapValue(
  value: number,
  track: PlanGraphTrack,
  laneTop: number,
  trackHeight: number,
): number {
  const domain = track.domain;
  if (!domain || domain.max <= domain.min) return laneTop + trackHeight / 2;
  const ratio = (value - domain.min) / (domain.max - domain.min);
  const inset = 6;
  const usable = trackHeight - inset * 2;
  const normalized = track.direction === "faster-up" ? ratio : 1 - ratio;
  return laneTop + inset + normalized * usable;
}

function Axis({
  axis,
  left,
  width,
  y,
}: {
  axis: PlanGraph["axis"];
  left: number;
  width: number;
  y: number;
}) {
  if (axis.mode === "schematic") {
    return (
      <g>
        <text x={left} y={y + 12} className="wprofile__axis-label">
          schematisch
        </text>
        <text x={left + width} y={y + 12} textAnchor="end" className="wprofile__axis-label">
          {axis.total_text}
        </text>
      </g>
    );
  }
  return (
    <g>
      {axis.ticks.map((tick, index) => (
        <text
          key={`axis-${index}`}
          x={left + tick.at * width}
          y={y + 12}
          textAnchor={tick.at === 0 ? "start" : tick.at === 1 ? "end" : "middle"}
          className="wprofile__axis-label"
        >
          {tick.label}
        </text>
      ))}
    </g>
  );
}

function isSelected(segment: PlanGraphSegment, selected: string | null): boolean {
  if (!selected) return false;
  return (
    segment.node_id === selected ||
    segment.group_id === selected ||
    segment.repeat_group_ids.includes(selected)
  );
}

function joinGerman(values: string[]): string {
  if (values.length <= 1) return values[0] ?? "";
  return `${values.slice(0, -1).join(", ")} und ${values[values.length - 1]}`;
}

function emptyTrack(): PlanGraphTrack {
  return {
    key: "empty",
    metric: "none",
    unit: "none",
    label: "Ohne Ziel",
    short: "—",
    kind: "none",
    segments: [],
  };
}
