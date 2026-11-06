import { useRef, type ReactNode } from "react";
import type {
  PlanDetail,
  PlanDraftProjection,
  PlanNode,
  PlanZoneOption,
} from "../types";
import {
  endSeed,
  fieldKey,
  nameFieldKey,
  nodeMeta,
  nodeTitle,
  visibleFieldMessage,
  type DraftFieldBuffers,
} from "../plannerDraft";

const ROLE_OPTIONS = [
  { value: "steady", label: "Gleichmäßig" },
  { value: "warmup", label: "Aufwärmen" },
  { value: "work", label: "Belastung" },
  { value: "recovery", label: "Erholung" },
  { value: "cooldown", label: "Abwärmen" },
];

const TARGET_LABEL: Record<string, string> = {
  none: "Ohne Ziel",
  zone: "Herzfrequenz · Zone",
  heartRate: "Herzfrequenz · bpm",
  power: "Leistung",
  pace: "Pace",
};

function editorId(nodeId: string): string {
  return `plan-editor-${nodeId.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

function headingId(nodeId: string): string {
  return `plan-head-${nodeId.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

export function PlanEditor({
  detail,
  projection,
  nodes,
  buffers,
  endKinds,
  selectedNodeId,
  expandedNodeId,
  onToggle,
  onBuffer,
  onClearBuffer,
  onPatchNode,
  onEndKindChange,
  registerHead,
}: {
  detail: PlanDetail;
  projection: PlanDraftProjection | null;
  nodes: PlanNode[];
  buffers: DraftFieldBuffers;
  endKinds: Record<string, "time" | "distance">;
  selectedNodeId: string | null;
  expandedNodeId: string | null;
  onToggle: (nodeId: string) => void;
  onBuffer: (
    nodeId: string,
    fieldPath: string,
    kind: "text" | "duration" | "distance",
    raw: string,
  ) => void;
  onClearBuffer: (nodeId: string, fieldPath: string) => void;
  onPatchNode: (nodeId: string, patch: Partial<PlanNode>) => void;
  onEndKindChange: (nodeId: string, kind: "time" | "distance") => void;
  registerHead: (nodeId: string, element: HTMLButtonElement | null) => void;
}) {
  return (
    <ol className="plan-nodes">
      {nodes.map((node, index) => (
        <PlanNodeBranch
          key={node.node_id}
          node={node}
          index={index + 1}
          detail={detail}
          projection={projection}
          buffers={buffers}
          endKinds={endKinds}
          selectedNodeId={selectedNodeId}
          expandedNodeId={expandedNodeId}
          onToggle={onToggle}
          onBuffer={onBuffer}
          onClearBuffer={onClearBuffer}
          onPatchNode={onPatchNode}
          onEndKindChange={onEndKindChange}
          registerHead={registerHead}
        />
      ))}
    </ol>
  );
}

function PlanNodeBranch({
  node,
  index,
  detail,
  projection,
  buffers,
  endKinds,
  selectedNodeId,
  expandedNodeId,
  onToggle,
  onBuffer,
  onClearBuffer,
  onPatchNode,
  onEndKindChange,
  registerHead,
}: {
  node: PlanNode;
  index: number;
  detail: PlanDetail;
  projection: PlanDraftProjection | null;
  buffers: DraftFieldBuffers;
  endKinds: Record<string, "time" | "distance">;
  selectedNodeId: string | null;
  expandedNodeId: string | null;
  onToggle: (nodeId: string) => void;
  onBuffer: (
    nodeId: string,
    fieldPath: string,
    kind: "text" | "duration" | "distance",
    raw: string,
  ) => void;
  onClearBuffer: (nodeId: string, fieldPath: string) => void;
  onPatchNode: (nodeId: string, patch: Partial<PlanNode>) => void;
  onEndKindChange: (nodeId: string, kind: "time" | "distance") => void;
  registerHead: (nodeId: string, element: HTMLButtonElement | null) => void;
}) {
  const selected = selectedNodeId === node.node_id;
  const open = expandedNodeId === node.node_id;
  const region = editorId(node.node_id);

  if (node.kind === "unsupported") {
    return (
      <li className="plan-node-item">
        <div className="plan-node plan-node--unsupported">
          <span className="plan-node__main">
            <span className="plan-node__name">{nodeTitle(node)}</span>
            <span className="plan-node__meta">{nodeMeta(node)}</span>
          </span>
          <span className="plan-node__badge">Nicht bearbeitbar</span>
        </div>
      </li>
    );
  }

  const incomplete =
    node.kind === "step" &&
    projection?.draft.issues.some(
      (issue) => issue.node_id === node.node_id && issue.code === "open_end",
    );

  return (
    <li
      className={[
        "plan-node-item",
        node.kind === "repeat" ? "plan-node-item--group" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <button
        type="button"
        id={headingId(node.node_id)}
        ref={(element) => registerHead(node.node_id, element)}
        className={`plan-node${selected ? " plan-node--selected" : ""}${
          open ? " plan-node--open" : ""
        }`}
        aria-expanded={open}
        aria-controls={region}
        aria-label={`${nodeTitle(node)} ${open ? "schließen" : "bearbeiten"}`}
        onClick={() => onToggle(node.node_id)}
      >
        <span className="plan-node__index" aria-hidden="true">
          {node.kind === "repeat" ? `↻${node.repetitions ?? 1}` : index}
        </span>
        <span className="plan-node__main">
          <span className="plan-node__name">
            {nodeTitle(node)}
            {incomplete && <span className="plan-node__incomplete">unvollständig</span>}
          </span>
          <span className="plan-node__meta">{nodeMeta(node)}</span>
        </span>
        <span className="plan-node__caret" aria-hidden="true">
          {open ? "⌃" : "›"}
        </span>
      </button>

      {open &&
        (node.kind === "repeat" ? (
          <GroupEditor node={node} region={region} />
        ) : (
          <StepEditor
            node={node}
            detail={detail}
            projection={projection}
            buffers={buffers}
            endKind={endKinds[node.node_id] ?? (node.end?.kind === "distance" ? "distance" : "time")}
            region={region}
            onBuffer={onBuffer}
            onPatchNode={onPatchNode}
            onEndKindChange={onEndKindChange}
          />
        ))}

      {node.kind === "repeat" && (node.children?.length ?? 0) > 0 && (
        <ol className="plan-node__children">
          {node.children?.map((child, childIndex) => (
            <PlanNodeBranch
              key={child.node_id}
              node={child}
              index={childIndex + 1}
              detail={detail}
              projection={projection}
              buffers={buffers}
              endKinds={endKinds}
              selectedNodeId={selectedNodeId}
              expandedNodeId={expandedNodeId}
              onToggle={onToggle}
              onBuffer={onBuffer}
              onClearBuffer={onClearBuffer}
              onPatchNode={onPatchNode}
              onEndKindChange={onEndKindChange}
              registerHead={registerHead}
            />
          ))}
        </ol>
      )}
    </li>
  );
}

function GroupEditor({ node, region }: { node: PlanNode; region: string }) {
  return (
    <section
      id={region}
      className="plan-inline"
      role="region"
      aria-labelledby={headingId(node.node_id)}
    >
      <p className="plan-inline__context">
        Gilt für alle {node.repetitions ?? 1}{" "}
        {(node.repetitions ?? 1) === 1 ? "Wiederholung" : "Wiederholungen"}
      </p>
      <div className="plan-inline__summary">
        <span>Name</span>
        <strong>{node.name || "Wiederholung"}</strong>
        <span>Wiederholungen</span>
        <strong>{node.repetitions ?? 1}</strong>
      </div>
      <p className="plan-note plan-note--muted">
        Gruppeneinstellungen und das Verschieben der Kinder folgen in P15. Die
        Kinder dieses Blocks bleiben einzeln bearbeitbar.
      </p>
    </section>
  );
}

function StepEditor({
  node,
  detail,
  projection,
  buffers,
  endKind,
  region,
  onBuffer,
  onPatchNode,
  onEndKindChange,
}: {
  node: PlanNode;
  detail: PlanDetail;
  projection: PlanDraftProjection | null;
  buffers: DraftFieldBuffers;
  endKind: "time" | "distance";
  region: string;
  onBuffer: (
    nodeId: string,
    fieldPath: string,
    kind: "text" | "duration" | "distance",
    raw: string,
  ) => void;
  onPatchNode: (nodeId: string, patch: Partial<PlanNode>) => void;
  onEndKindChange: (nodeId: string, kind: "time" | "distance") => void;
}) {
  const nameKey = nameFieldKey(node.node_id);
  const endKey = fieldKey(node.node_id, "end.value");
  const nameRaw = buffers[nameKey]?.raw ?? node.name ?? "";
  const endRaw = buffers[endKey]?.raw ?? endSeed(node);
  const nameError = visibleFieldMessage(projection, nameKey);
  const endError = visibleFieldMessage(projection, endKey);
  const target = node.target;
  const targetKind = target?.kind ?? "none";
  const targetLocked = targetKind === "power" || targetKind === "pace";
  const zoneOptions = detail.zone_options ?? {
    sport: detail.sport,
    available: false,
    zone_set_id: null,
    max_hr: null,
    zones: [],
  };
  const currentZone = zoneOptions.zones.find((zone) => zone.id === target?.zone_id);
  const unknownZone =
    targetKind === "zone" && target?.zone_id && !currentZone ? target.zone_id : null;
  const bpmCapability = detail.capabilities?.targets?.heartRateBpm ?? {
    local: true,
    editable: false,
    synchronizable: false,
    reason: "Kein belegter Schreibvertrag für absolute bpm-Werte.",
  };

  const endValueId = `field-${node.node_id.replace(/[^a-zA-Z0-9_-]/g, "-")}-end`;
  const nameId = `field-${node.node_id.replace(/[^a-zA-Z0-9_-]/g, "-")}-name`;
  const roleId = `field-${node.node_id.replace(/[^a-zA-Z0-9_-]/g, "-")}-role`;
  const targetId = `field-${node.node_id.replace(/[^a-zA-Z0-9_-]/g, "-")}-target`;
  const zoneId = `field-${node.node_id.replace(/[^a-zA-Z0-9_-]/g, "-")}-zone`;
  const endErrorId = `${endValueId}-error`;
  const nameErrorId = `${nameId}-error`;

  return (
    <section
      id={region}
      className="plan-inline"
      role="region"
      aria-labelledby={headingId(node.node_id)}
    >
      <div className="plan-field">
        <label htmlFor={nameId}>Name</label>
        <input
          id={nameId}
          className="plan-input"
          type="text"
          value={nameRaw}
          aria-invalid={nameError ? true : undefined}
          aria-describedby={nameError ? nameErrorId : undefined}
          onChange={(event) =>
            onBuffer(node.node_id, "name", "text", event.target.value)
          }
        />
        {nameError && (
          <p id={nameErrorId} className="plan-field__error" role="alert">
            {nameError}
          </p>
        )}
      </div>

      <div className="plan-field-row">
        <div className="plan-field">
          <label htmlFor={`${endValueId}-kind`}>Abschnitt endet nach</label>
          <select
            id={`${endValueId}-kind`}
            className="plan-input"
            value={endKind}
            onChange={(event) => {
              const next = event.target.value as "time" | "distance";
              // Ein Wechsel löscht den bisherigen Umfang. Eine Geschwindigkeit
              // wird nicht abgeleitet; der neue Wert muss bewusst gesetzt werden.
              onEndKindChange(node.node_id, next);
            }}
          >
            <option value="time">Zeit</option>
            <option value="distance">Distanz</option>
          </select>
        </div>

        <div className="plan-field">
          <label htmlFor={endValueId}>Umfang</label>
          <input
            id={endValueId}
            className="plan-input"
            type="text"
            inputMode="decimal"
            value={endRaw}
            placeholder={endKind === "distance" ? "z. B. 1,5 km" : "z. B. 45 min"}
            aria-invalid={endError ? true : undefined}
            aria-describedby={endError ? endErrorId : `${endValueId}-hint`}
            onChange={(event) =>
              onBuffer(
                node.node_id,
                "end.value",
                endKind === "distance" ? "distance" : "duration",
                event.target.value,
              )
            }
          />
          <p id={`${endValueId}-hint`} className="plan-field__hint">
            {endKind === "distance"
              ? "Meter oder Kilometer; 1,5 km wird zu 1.500 m."
              : "Minuten, z. B. 45; auch 1:30 oder 45 min."}
          </p>
          {endError && (
            <p id={endErrorId} className="plan-field__error" role="alert">
              {endError}
            </p>
          )}
        </div>
      </div>

      <div className="plan-field-row">
        <div className="plan-field">
          <label htmlFor={roleId}>Abschnittstyp</label>
          <select
            id={roleId}
            className="plan-input"
            value={node.role ?? "steady"}
            onChange={(event) =>
              onPatchNode(node.node_id, { role: event.target.value })
            }
          >
            {ROLE_OPTIONS.map((role) => (
              <option key={role.value} value={role.value}>
                {role.label}
              </option>
            ))}
          </select>
        </div>

        <div className="plan-field">
          <label htmlFor={targetId}>Zielart</label>
          <select
            id={targetId}
            className="plan-input"
            value={targetKind}
            disabled={targetLocked}
            onChange={(event) => {
              const next = event.target.value;
              if (next === "none") {
                onPatchNode(node.node_id, {
                  target: { kind: "none", text: "Ohne Ziel" },
                });
                return;
              }
              if (next === "zone") {
                const first = zoneOptions.zones[0];
                onPatchNode(node.node_id, {
                  target: {
                    kind: "zone",
                    metric: "heartRate",
                    zone_id: currentZone?.id ?? first?.id ?? "",
                    zone_set_id: zoneOptions.zone_set_id,
                    text: first?.label ?? "HF-Zone",
                  },
                });
              }
            }}
          >
            <option value="none">Ohne Ziel</option>
            <option value="zone">Herzfrequenz · Zone</option>
            {targetKind === "heartRate" && (
              <option value="heartRate" disabled>
                Herzfrequenz · bpm (nicht synchronisierbar)
              </option>
            )}
            {targetKind === "power" && (
              <option value="power" disabled>
                Leistung (folgt in P13)
              </option>
            )}
            {targetKind === "pace" && (
              <option value="pace" disabled>
                Pace (folgt in P13)
              </option>
            )}
          </select>
          <p className="plan-field__hint">
            HF-Zonen kommen aus dem tatsächlichen Profil. Absolute bpm-Felder
            bleiben bis zum nachgewiesenen Adapter-Gate gesperrt.
          </p>
        </div>
      </div>

      {targetKind === "zone" && (
        <div className="plan-field">
          <label htmlFor={zoneId}>HF-Zone</label>
          <select
            id={zoneId}
            className="plan-input"
            value={target?.zone_id ?? ""}
            disabled={!zoneOptions.available}
            onChange={(event) => {
              const zone = zoneOptions.zones.find(
                (option) => option.id === event.target.value,
              );
              onPatchNode(node.node_id, {
                target: {
                  kind: "zone",
                  metric: "heartRate",
                  zone_id: event.target.value,
                  zone_set_id: zoneOptions.zone_set_id,
                  text: zone?.label ?? event.target.value,
                },
              });
            }}
          >
            {!zoneOptions.available && (
              <option value="">Kein HF-Zonenprofil für diese Sportart</option>
            )}
            {zoneOptions.zones.map((zone) => (
              <option key={zone.id} value={zone.id}>
                {zoneOptionText(zone)}
              </option>
            ))}
            {unknownZone && (
              <option value={unknownZone}>
                {target?.text ?? unknownZone} · Referenz nicht im Profil
              </option>
            )}
          </select>
          {currentZone && (
            <p className="plan-field__hint">
              {zoneOptionText(currentZone)} · aus dem tatsächlichen Profil.
            </p>
          )}
          {unknownZone && (
            <p className="plan-field__warning">
              Die gespeicherte Zonenreferenz {unknownZone} ist im aktuellen
              Profil nicht enthalten. Sie bleibt erhalten, bis du bewusst eine
              vorhandene Zone wählst.
            </p>
          )}
          {!zoneOptions.available && (
            <p className="plan-field__warning">
              Für {detail.sport_label} liegt kein HF-Zonenprofil vor. Es werden
              keine bpm-Grenzen erfunden; „Ohne Ziel“ bleibt möglich.
            </p>
          )}
        </div>
      )}

      {targetKind === "heartRate" && (
        <div className="plan-field">
          <p className="plan-field__warning">
            Absolute bpm-Werte bleiben lesbar, sind aber ohne belegten
            Schreibvertrag nicht als synchronisierbares Feld freigeschaltet.
            {" "}
            {bpmCapability.reason ?? ""}
          </p>
          <p className="plan-field__hint">Gespeichert: {target?.text ?? "—"}</p>
        </div>
      )}

      {targetLocked && (
        <p className="plan-note plan-note--muted">
          {TARGET_LABEL[targetKind] ?? targetKind} bleibt unverändert erhalten.
          Die Bearbeitung dieser Zielart folgt in P13.
        </p>
      )}

      <p className="plan-inline__footer">
        Änderungen bleiben lokal. Ein Feld darf unfertig sein; gespeichert wird
        in diesem Paket noch nichts.
      </p>
    </section>
  );
}

function zoneOptionText(zone: PlanZoneOption): string {
  const range =
    zone.low != null && zone.high != null
      ? `${Math.round(zone.low)}–${Math.round(zone.high)} bpm`
      : "Bereich nicht verfügbar";
  return `${zone.label} · ${range}`;
}

export function DraftStatus({
  projection,
  buffers,
  dirty,
  onDiscard,
}: {
  projection: PlanDraftProjection | null;
  buffers: DraftFieldBuffers;
  dirty: boolean;
  onDiscard: () => void;
}): ReactNode {
  const fieldCount = Object.keys(buffers).length;
  const invalid = projection
    ? Object.values(projection.draft.field_states).filter(
        (state) => state.validity !== "valid",
      ).length
    : 0;
  const issues = projection?.draft.issues ?? [];
  const openEnds = issues.filter((issue) => issue.code === "open_end").length;
  const status = invalid
    ? `${invalid} ${invalid === 1 ? "Feld ist" : "Felder sind"} unvollständig`
    : openEnds
      ? `${openEnds} ${openEnds === 1 ? "Abschnitt hat" : "Abschnitte haben"} noch kein Ende`
      : dirty
        ? "Ungespeicherte Änderungen"
        : fieldCount > 0
          ? "Keine fachliche Änderung"
          : "Entwurf unverändert";
  return (
    <div className="plan-savebar">
      <div>
        <span className={dirty ? "plan-savebar__state plan-savebar__state--dirty" : "plan-savebar__state"}>
          {status}
        </span>
        <span className="plan-savebar__hint">
          Lokal · kein Remote-Schreibvorgang
        </span>
      </div>
      <div className="plan-savebar__actions">
        <button type="button" className="btn btn--ghost" onClick={onDiscard}>
          Verwerfen
        </button>
        <button
          type="button"
          className="btn btn--primary"
          disabled
          title="Der Remote-Schreibpfad wird in P17 aktiviert."
        >
          Speichern
        </button>
      </div>
    </div>
  );
}

/** Ein stabiler Anker für „nur scrollen, wenn nötig“. */
export function useHeadScroll() {
  const heads = useRef(new Map<string, HTMLButtonElement>());
  return {
    register: (nodeId: string, element: HTMLButtonElement | null) => {
      if (element) heads.current.set(nodeId, element);
      else heads.current.delete(nodeId);
    },
    reveal: (nodeId: string) => {
      const element = heads.current.get(nodeId);
      if (!element) return;
      const rect = element.getBoundingClientRect();
      if (rect.top < 8 || rect.bottom > window.innerHeight - 8) {
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        element.scrollIntoView({
          block: "nearest",
          behavior: reduce ? "auto" : "smooth",
        });
      }
    },
  };
}
