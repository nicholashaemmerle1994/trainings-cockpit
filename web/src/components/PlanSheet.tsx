import { useEffect, useState } from "react";
import { api } from "../api";
import { fmtDateLong } from "../format";
import type { PlanDetail, PlanNode } from "../types";
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

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(null);
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
      {data && <PlanBody data={data} />}
    </Sheet>
  );
}

function PlanBody({ data }: { data: PlanDetail }) {
  const date = fmtDateLong(data.date);
  const repetitions = data.nodes
    .filter((node) => node.kind === "repeat")
    .reduce((sum, node) => sum + (node.repetitions ?? 0), 0);

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
        </span>
      </div>

      <section className="sheet-sec plan-structure" aria-label="Aufbau der Planung">
        <h2>Aufbau</h2>
        {data.nodes.length === 0 && (
          <p className="plan-note">Für diese Planung liegt kein Aufbau vor.</p>
        )}
        <PlanNodeList nodes={data.nodes} />
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

function PlanNodeList({ nodes }: { nodes: PlanNode[] }) {
  return (
    <ol className="plan-nodes">
      {nodes.map((node, index) => (
        <PlanNodeItem key={node.node_id} node={node} index={index + 1} />
      ))}
    </ol>
  );
}

function PlanNodeItem({ node, index }: { node: PlanNode; index: number }) {
  if (node.kind === "repeat") {
    return (
      <li className="plan-node-item plan-node-item--group">
        <div className="plan-node">
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
        </div>
        {node.children && node.children.length > 0 && (
          <ol className="plan-node__children">
            {node.children.map((child, childIndex) => (
              <PlanNodeItem
                key={child.node_id}
                node={child}
                index={childIndex + 1}
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

  const meta = [node.end?.text, node.target?.text].filter(Boolean).join(" · ");
  return (
    <li className="plan-node-item">
      <div className="plan-node">
        <span className="plan-node__index">{index}</span>
        <span className="plan-node__main">
          <span className="plan-node__name">{node.name || "Abschnitt"}</span>
          <span className="plan-node__meta">{meta || "Ohne Vorgabe"}</span>
        </span>
      </div>
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
