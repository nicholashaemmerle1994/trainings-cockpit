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
  finalRecoveryChild,
  nameFieldKey,
  nodeMeta,
  nodeTitle,
  paceUnitOptions,
  subtreeIds,
  targetEditorLabel,
  targetFieldSpec,
  targetRangeText,
  targetUnitLabel,
  targetValueText,
  visibleFieldMessage,
  type DraftFieldBuffers,
  type DraftFieldKind,
  type TargetEditor,
  type TargetEditorKind,
  type TargetEditorUnit,
} from "../plannerDraft";

const ROLE_OPTIONS = [
  { value: "steady", label: "Gleichmäßig" },
  { value: "warmup", label: "Aufwärmen" },
  { value: "work", label: "Belastung" },
  { value: "recovery", label: "Erholung" },
  { value: "cooldown", label: "Abwärmen" },
];

const MAX_DISSOLVE_NODES = 2000;

export interface BufferOptions {
  targetKind?: TargetEditorKind;
  unit?: TargetEditorUnit;
}

function editorId(nodeId: string): string {
  return `plan-editor-${nodeId.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

function headingId(nodeId: string): string {
  return `plan-head-${nodeId.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

function fieldId(nodeId: string, field: string): string {
  return `field-${nodeId.replace(/[^a-zA-Z0-9_-]/g, "-")}-${field}`;
}

function targetFieldKind(editor: TargetEditor): DraftFieldKind {
  return editor.kind === "pace" ? "pace" : "decimal";
}

function bufferValue(
  buffers: DraftFieldBuffers,
  nodeId: string,
  path: string,
  fallback: string,
): string {
  return buffers[fieldKey(nodeId, path)]?.raw ?? fallback;
}

function issueForNode(
  projection: PlanDraftProjection | null,
  nodeId: string,
): string | null {
  const issue = projection?.draft.issues.find(
    (candidate) =>
      candidate.node_id === nodeId &&
      candidate.code !== "open_end" &&
      candidate.code !== "incomplete_field" &&
      candidate.code !== "invalid_field",
  );
  return issue?.message ?? null;
}

function invalidBufferInSubtree(
  projection: PlanDraftProjection | null,
  buffers: DraftFieldBuffers,
  node: PlanNode,
): string | null {
  const ids = new Set(subtreeIds(node));
  for (const key of Object.keys(buffers)) {
    const owner = key.slice(0, key.lastIndexOf(":"));
    if (!ids.has(owner)) continue;
    const state = projection?.draft.field_states[key];
    if (!state || state.validity !== "valid") {
      return state?.message || "Ein Feld ist noch unvollständig.";
    }
  }
  return null;
}

function invalidIssueInSubtree(
  projection: PlanDraftProjection | null,
  node: PlanNode,
): string | null {
  const ids = new Set(subtreeIds(node));
  const issue = projection?.draft.issues.find(
    (candidate) =>
      candidate.node_id != null &&
      ids.has(candidate.node_id) &&
      ["open_end", "empty_repeat", "no_executed_steps"].includes(candidate.code),
  );
  return issue?.message ?? null;
}

export function PlanEditor({
  detail,
  projection,
  nodes,
  buffers,
  endKinds,
  targetEditors,
  selectedNodeId,
  expandedNodeId,
  onToggle,
  onBuffer,
  onPatchNode,
  onEndKindChange,
  onTargetKindChange,
  onTargetUnitChange,
  onTargetModeChange,
  onMove,
  onRemove,
  onAddChild,
  onDissolve,
  registerHead,
}: {
  detail: PlanDetail;
  projection: PlanDraftProjection | null;
  nodes: PlanNode[];
  buffers: DraftFieldBuffers;
  endKinds: Record<string, "time" | "distance">;
  targetEditors: Record<string, TargetEditor>;
  selectedNodeId: string | null;
  expandedNodeId: string | null;
  onToggle: (nodeId: string) => void;
  onBuffer: (
    nodeId: string,
    fieldPath: string,
    kind: DraftFieldKind,
    raw: string,
    options?: BufferOptions,
  ) => void;
  onPatchNode: (nodeId: string, patch: Partial<PlanNode>) => void;
  onEndKindChange: (nodeId: string, kind: "time" | "distance") => void;
  onTargetKindChange: (
    nodeId: string,
    kind: TargetEditorKind,
    unit?: TargetEditorUnit,
  ) => void;
  onTargetUnitChange: (nodeId: string, unit: TargetEditorUnit) => void;
  onTargetModeChange: (nodeId: string, mode: "value" | "range") => void;
  onMove: (nodeId: string, delta: -1 | 1) => void;
  onRemove: (nodeId: string) => void;
  onAddChild: (groupId: string) => void;
  onDissolve: (groupId: string) => void;
  registerHead: (nodeId: string, element: HTMLButtonElement | null) => void;
}) {
  return (
    <ol className="plan-nodes">
      {nodes.map((node, index) => (
        <PlanNodeBranch
          key={node.node_id}
          node={node}
          index={index + 1}
          siblingCount={nodes.length}
          parentId={null}
          parentRepetitions={undefined}
          detail={detail}
          projection={projection}
          buffers={buffers}
          endKinds={endKinds}
          targetEditors={targetEditors}
          selectedNodeId={selectedNodeId}
          expandedNodeId={expandedNodeId}
          onToggle={onToggle}
          onBuffer={onBuffer}
          onPatchNode={onPatchNode}
          onEndKindChange={onEndKindChange}
          onTargetKindChange={onTargetKindChange}
          onTargetUnitChange={onTargetUnitChange}
          onTargetModeChange={onTargetModeChange}
          onMove={onMove}
          onRemove={onRemove}
          onAddChild={onAddChild}
          onDissolve={onDissolve}
          registerHead={registerHead}
        />
      ))}
    </ol>
  );
}

function PlanNodeBranch({
  node,
  index,
  siblingCount,
  parentId,
  parentRepetitions,
  detail,
  projection,
  buffers,
  endKinds,
  targetEditors,
  selectedNodeId,
  expandedNodeId,
  onToggle,
  onBuffer,
  onPatchNode,
  onEndKindChange,
  onTargetKindChange,
  onTargetUnitChange,
  onTargetModeChange,
  onMove,
  onRemove,
  onAddChild,
  onDissolve,
  registerHead,
}: {
  node: PlanNode;
  index: number;
  siblingCount: number;
  parentId: string | null;
  parentRepetitions?: number;
  detail: PlanDetail;
  projection: PlanDraftProjection | null;
  buffers: DraftFieldBuffers;
  endKinds: Record<string, "time" | "distance">;
  targetEditors: Record<string, TargetEditor>;
  selectedNodeId: string | null;
  expandedNodeId: string | null;
  onToggle: (nodeId: string) => void;
  onBuffer: (
    nodeId: string,
    fieldPath: string,
    kind: DraftFieldKind,
    raw: string,
    options?: BufferOptions,
  ) => void;
  onPatchNode: (nodeId: string, patch: Partial<PlanNode>) => void;
  onEndKindChange: (nodeId: string, kind: "time" | "distance") => void;
  onTargetKindChange: (
    nodeId: string,
    kind: TargetEditorKind,
    unit?: TargetEditorUnit,
  ) => void;
  onTargetUnitChange: (nodeId: string, unit: TargetEditorUnit) => void;
  onTargetModeChange: (nodeId: string, mode: "value" | "range") => void;
  onMove: (nodeId: string, delta: -1 | 1) => void;
  onRemove: (nodeId: string) => void;
  onAddChild: (groupId: string) => void;
  onDissolve: (groupId: string) => void;
  registerHead: (nodeId: string, element: HTMLButtonElement | null) => void;
}) {
  const selected = selectedNodeId === node.node_id;
  const open = expandedNodeId === node.node_id;
  const region = editorId(node.node_id);
  const editor = targetEditors[node.node_id] ?? { kind: "none", mode: "value" };
  const actions = (
    <NodeActions
      node={node}
      index={index}
      siblingCount={siblingCount}
      parentId={parentId}
      onMove={onMove}
      onRemove={onRemove}
    />
  );

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
          <GroupEditor
            node={node}
            projection={projection}
            buffers={buffers}
            editor={editor}
            region={region}
            onBuffer={onBuffer}
            onPatchNode={onPatchNode}
            onAddChild={onAddChild}
            onDissolve={onDissolve}
            actions={actions}
          />
        ) : (
          <StepEditor
            node={node}
            detail={detail}
            projection={projection}
            buffers={buffers}
            editor={editor}
            parentRepetitions={parentRepetitions}
            endKind={
              endKinds[node.node_id] ??
              (node.end?.kind === "distance" ? "distance" : "time")
            }
            region={region}
            onBuffer={onBuffer}
              onPatchNode={onPatchNode}
            onEndKindChange={onEndKindChange}
            onTargetKindChange={onTargetKindChange}
            onTargetUnitChange={onTargetUnitChange}
            onTargetModeChange={onTargetModeChange}
            actions={actions}
          />
        ))}

      {node.kind === "repeat" && (node.children?.length ?? 0) > 0 && (
        <ol className="plan-node__children">
          {node.children?.map((child, childIndex) => (
            <PlanNodeBranch
              key={child.node_id}
              node={child}
              index={childIndex + 1}
              siblingCount={node.children?.length ?? 0}
              parentId={node.node_id}
              parentRepetitions={node.repetitions ?? 1}
              detail={detail}
              projection={projection}
              buffers={buffers}
              endKinds={endKinds}
              targetEditors={targetEditors}
              selectedNodeId={selectedNodeId}
              expandedNodeId={expandedNodeId}
              onToggle={onToggle}
              onBuffer={onBuffer}
                  onPatchNode={onPatchNode}
              onEndKindChange={onEndKindChange}
              onTargetKindChange={onTargetKindChange}
              onTargetUnitChange={onTargetUnitChange}
              onTargetModeChange={onTargetModeChange}
              onMove={onMove}
              onRemove={onRemove}
              onAddChild={onAddChild}
              onDissolve={onDissolve}
              registerHead={registerHead}
            />
          ))}
        </ol>
      )}
    </li>
  );
}

function NodeActions({
  node,
  index,
  siblingCount,
  parentId,
  onMove,
  onRemove,
}: {
  node: PlanNode;
  index: number;
  siblingCount: number;
  parentId: string | null;
  onMove: (nodeId: string, delta: -1 | 1) => void;
  onRemove: (nodeId: string) => void;
}) {
  const first = index <= 1;
  const last = index >= siblingCount;
  return (
    <div className="plan-node__actions">
      <div className="plan-node__move">
        <button
          type="button"
          className="plan-icon-button"
          aria-label={`${nodeTitle(node)} nach oben verschieben`}
          title="Nach oben"
          disabled={first}
          onClick={() => onMove(node.node_id, -1)}
        >
          ↑
        </button>
        <button
          type="button"
          className="plan-icon-button"
          aria-label={`${nodeTitle(node)} nach unten verschieben`}
          title="Nach unten"
          disabled={last}
          onClick={() => onMove(node.node_id, 1)}
        >
          ↓
        </button>
      </div>
      {parentId && (
        <span className="plan-node__level">nur in dieser Gruppe</span>
      )}
      <button
        type="button"
        className="plan-node__remove"
        onClick={() => onRemove(node.node_id)}
      >
        Entfernen
      </button>
    </div>
  );
}

function GroupEditor({
  node,
  projection,
  buffers,
  editor,
  region,
  onBuffer,
  onPatchNode,
  onAddChild,
  onDissolve,
  actions,
}: {
  node: PlanNode;
  projection: PlanDraftProjection | null;
  buffers: DraftFieldBuffers;
  editor: TargetEditor;
  region: string;
  onBuffer: (
    nodeId: string,
    fieldPath: string,
    kind: DraftFieldKind,
    raw: string,
    options?: BufferOptions,
  ) => void;
  onPatchNode: (nodeId: string, patch: Partial<PlanNode>) => void;
  onAddChild: (groupId: string) => void;
  onDissolve: (groupId: string) => void;
  actions: ReactNode;
}) {
  const nameKey = nameFieldKey(node.node_id);
  const repetitionsKey = fieldKey(node.node_id, "repetitions");
  const nameRaw = buffers[nameKey]?.raw ?? node.name ?? "";
  const repetitionsRaw =
    buffers[repetitionsKey]?.raw ?? String(node.repetitions ?? 1);
  const nameError = visibleFieldMessage(projection, nameKey);
  const repetitionsError = visibleFieldMessage(projection, repetitionsKey);
  const lastRecovery = finalRecoveryChild(node);
  const skipChecked = node.skip_final_recovery === true && lastRecovery !== null;
  const groupIssue = issueForNode(projection, node.node_id);
  const invalidBuffer = invalidBufferInSubtree(projection, buffers, node);
  const invalidIssue = invalidIssueInSubtree(projection, node);
  const repetitionsNumber = node.repetitions ?? 1;
  const estimated = repetitionsNumber * (node.children?.length ?? 0);
  let dissolveReason: string | null = null;
  if ((node.children?.length ?? 0) === 0) {
    dissolveReason = "Der Block hat noch keine Schritte.";
  } else if (repetitionsError) {
    dissolveReason = repetitionsError;
  } else if (invalidBuffer) {
    dissolveReason = `Auflösen gesperrt: ${invalidBuffer}`;
  } else if (invalidIssue) {
    dissolveReason = `Auflösen gesperrt: ${invalidIssue}`;
  } else if (estimated > MAX_DISSOLVE_NODES) {
    dissolveReason =
      `Der Block würde ${estimated.toLocaleString("de-DE")} Einzelabschnitte ` +
      `erzeugen. Diese Größe bleibt als Gruppe erhalten.`;
  }

  return (
    <section
      id={region}
      className="plan-inline"
      role="region"
      aria-labelledby={headingId(node.node_id)}
    >
      <p className="plan-inline__context">
        {editor.kind === "none" ? "Gruppe" : targetEditorLabel(editor)}
      </p>
      <p className="plan-inline__context plan-inline__context--accent">
        Gilt für alle {repetitionsNumber}{" "}
        {repetitionsNumber === 1 ? "Wiederholung" : "Wiederholungen"}
      </p>

      <div className="plan-field-row">
        <div className="plan-field">
          <label htmlFor={fieldId(node.node_id, "group-name")}>Gruppenname</label>
          <input
            id={fieldId(node.node_id, "group-name")}
            className="plan-input"
            type="text"
            value={nameRaw}
            aria-invalid={nameError ? true : undefined}
            aria-describedby={
              nameError ? `${fieldId(node.node_id, "group-name")}-error` : undefined
            }
            onChange={(event) =>
              onBuffer(node.node_id, "name", "text", event.target.value)
            }
          />
          {nameError && (
            <p
              id={`${fieldId(node.node_id, "group-name")}-error`}
              className="plan-field__error"
              role="alert"
            >
              {nameError}
            </p>
          )}
        </div>
        <div className="plan-field">
          <label htmlFor={fieldId(node.node_id, "repetitions")}>
            Wiederholungen
          </label>
          <input
            id={fieldId(node.node_id, "repetitions")}
            className="plan-input"
            type="text"
            inputMode="numeric"
            value={repetitionsRaw}
            aria-invalid={repetitionsError ? true : undefined}
            aria-describedby={
              repetitionsError
                ? `${fieldId(node.node_id, "repetitions")}-error`
                : `${fieldId(node.node_id, "repetitions")}-hint`
            }
            onChange={(event) =>
              onBuffer(node.node_id, "repetitions", "integer", event.target.value)
            }
          />
          <p
            id={`${fieldId(node.node_id, "repetitions")}-hint`}
            className="plan-field__hint"
          >
            Positive ganze Zahl. Große Zahlen bleiben rechnerisch exakt; der Graph
            fasst nur die Darstellung zusammen.
          </p>
          {repetitionsError && (
            <p
              id={`${fieldId(node.node_id, "repetitions")}-error`}
              className="plan-field__error"
              role="alert"
            >
              {repetitionsError}
            </p>
          )}
        </div>
      </div>

      {(node.children?.length ?? 0) === 0 && (
        <p className="plan-note plan-note--warning" role="status">
          Dieser Wiederholungsblock enthält noch keinen Schritt und führt damit
          nichts aus. Speichern bleibt gesperrt.
        </p>
      )}

      <label className="plan-check">
        <input
          type="checkbox"
          checked={skipChecked}
          disabled={!lastRecovery}
          onChange={(event) =>
            onPatchNode(node.node_id, {
              skip_final_recovery: event.target.checked,
            })
          }
        />
        <span>
          Letzte Erholung auslassen
          <span className="plan-check__hint">
            Gilt nur für die letzte der {repetitionsNumber} Wiederholungen. Das
            letzte Kind muss als Erholung gekennzeichnet sein.
          </span>
        </span>
      </label>
      {!lastRecovery && (
        <p className="plan-field__hint">
          Nicht aktivierbar: Das letzte Kind ist keine Erholung.
        </p>
      )}

      <div className="plan-inline__buttons">
        <button
          type="button"
          className="btn btn--ghost"
          onClick={() => onAddChild(node.node_id)}
        >
          + Schritt im Block
        </button>
        <button
          type="button"
          className="btn btn--ghost"
          disabled={dissolveReason !== null}
          title={dissolveReason ?? "In unabhängige Einzelabschnitte auflösen"}
          onClick={() => onDissolve(node.node_id)}
        >
          In einzelne Abschnitte auflösen
        </button>
      </div>
      {dissolveReason && (
        <p className="plan-field__hint" role="status">
          {dissolveReason}
        </p>
      )}

      {groupIssue && (
        <p className="plan-field__warning" role="status">
          {groupIssue}
        </p>
      )}

      <p className="plan-inline__footer">
        Es wird nur eine Vorlage der Kinder bearbeitet. Der Graph darf die
        Ausführungen mehrfach zeigen; gespeichert wird in diesem Paket noch nichts.
      </p>
      {actions}
    </section>
  );
}

function StepEditor({
  node,
  detail,
  projection,
  buffers,
  editor,
  parentRepetitions,
  endKind,
  region,
  onBuffer,
  onPatchNode,
  onEndKindChange,
  onTargetKindChange,
  onTargetUnitChange,
  onTargetModeChange,
  actions,
}: {
  node: PlanNode;
  detail: PlanDetail;
  projection: PlanDraftProjection | null;
  buffers: DraftFieldBuffers;
  editor: TargetEditor;
  parentRepetitions?: number;
  endKind: "time" | "distance";
  region: string;
  onBuffer: (
    nodeId: string,
    fieldPath: string,
    kind: DraftFieldKind,
    raw: string,
    options?: BufferOptions,
  ) => void;
  onPatchNode: (nodeId: string, patch: Partial<PlanNode>) => void;
  onEndKindChange: (nodeId: string, kind: "time" | "distance") => void;
  onTargetKindChange: (
    nodeId: string,
    kind: TargetEditorKind,
    unit?: TargetEditorUnit,
  ) => void;
  onTargetUnitChange: (nodeId: string, unit: TargetEditorUnit) => void;
  onTargetModeChange: (nodeId: string, mode: "value" | "range") => void;
  actions: ReactNode;
}) {
  const nameKey = nameFieldKey(node.node_id);
  const endKey = fieldKey(node.node_id, "end.value");
  const nameRaw = buffers[nameKey]?.raw ?? node.name ?? "";
  const endRaw = buffers[endKey]?.raw ?? endSeed(node);
  const nameError = visibleFieldMessage(projection, nameKey);
  const endError = visibleFieldMessage(projection, endKey);
  const targetSpec = targetFieldSpec(editor);
  const unit = editor.unit;
  const valueKey = fieldKey(node.node_id, "target.value");
  const minKey = fieldKey(node.node_id, "target.min");
  const maxKey = fieldKey(node.node_id, "target.max");
  const valueFallback =
    editor.kind === "pace" || editor.kind === "power" || editor.kind === "heartRate"
      ? targetValueText(node, editor)
      : "";
  const minFallback =
    editor.kind === "pace" || editor.kind === "power" || editor.kind === "heartRate"
      ? targetRangeText(node, editor, "min")
      : "";
  const maxFallback =
    editor.kind === "pace" || editor.kind === "power" || editor.kind === "heartRate"
      ? targetRangeText(node, editor, "max")
      : "";
  const valueRaw = bufferValue(buffers, node.node_id, "target.value", valueFallback);
  const minRaw = bufferValue(buffers, node.node_id, "target.min", minFallback);
  const maxRaw = bufferValue(buffers, node.node_id, "target.max", maxFallback);
  const valueError = visibleFieldMessage(projection, valueKey);
  const minError = visibleFieldMessage(projection, minKey);
  const maxError = visibleFieldMessage(projection, maxKey);
  const zoneOptions = detail.zone_options ?? {
    sport: detail.sport,
    available: false,
    zone_set_id: null,
    max_hr: null,
    zones: [],
  };
  const currentZone = zoneOptions.zones.find(
    (zone) => zone.id === node.target?.zone_id,
  );
  const unknownZone =
    node.target?.kind === "zone" &&
    node.target.zone_id &&
    !currentZone
      ? node.target.zone_id
      : null;
  const bpmCapability = detail.capabilities?.targets?.heartRateBpm ?? {
    local: true,
    editable: false,
    synchronizable: false,
    reason: "Kein belegter Schreibvertrag für absolute bpm-Werte.",
  };
  const powerZoneCapability = detail.capabilities?.targets?.powerZone;
  const paceUnits =
    editor.kind === "pace"
      ? paceUnitOptions(detail.sport, editor.unit)
      : [];
  const powerUnits: TargetEditorUnit[] =
    editor.kind === "power" ? ["watts", "percentFtp"] : [];
  const unitOptions = editor.kind === "pace" ? paceUnits : powerUnits;
  const unitLocked =
    editor.kind === "pace" &&
    unitOptions.length > 1 &&
    Boolean(valueError || minError || maxError);
  const unitId = fieldId(node.node_id, "target-unit");
  const modeId = fieldId(node.node_id, "target-mode");
  const targetId = fieldId(node.node_id, "target");
  const zoneId = fieldId(node.node_id, "zone");
  const targetFieldProps = {
    kind: targetFieldKind(editor),
    targetKind: editor.kind,
    unit,
  } as const;

  return (
    <section
      id={region}
      className="plan-inline"
      role="region"
      aria-labelledby={headingId(node.node_id)}
    >
      {parentRepetitions != null && (
        <p className="plan-inline__context plan-inline__context--accent">
          Gilt für alle {parentRepetitions}{" "}
          {parentRepetitions === 1 ? "Wiederholung" : "Wiederholungen"}
        </p>
      )}
      <div className="plan-field">
        <label htmlFor={fieldId(node.node_id, "name")}>Name</label>
        <input
          id={fieldId(node.node_id, "name")}
          className="plan-input"
          type="text"
          value={nameRaw}
          aria-invalid={nameError ? true : undefined}
          aria-describedby={
            nameError ? `${fieldId(node.node_id, "name")}-error` : undefined
          }
          onChange={(event) =>
            onBuffer(node.node_id, "name", "text", event.target.value)
          }
        />
        {nameError && (
          <p
            id={`${fieldId(node.node_id, "name")}-error`}
            className="plan-field__error"
            role="alert"
          >
            {nameError}
          </p>
        )}
      </div>

      <div className="plan-field-row">
        <div className="plan-field">
          <label htmlFor={`${fieldId(node.node_id, "end")}-kind`}>
            Abschnitt endet nach
          </label>
          <select
            id={`${fieldId(node.node_id, "end")}-kind`}
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
          <label htmlFor={fieldId(node.node_id, "end")}>Umfang</label>
          <input
            id={fieldId(node.node_id, "end")}
            className="plan-input"
            type="text"
            inputMode="decimal"
            value={endRaw}
            placeholder={endKind === "distance" ? "z. B. 1,5 km" : "z. B. 45 min"}
            aria-invalid={endError ? true : undefined}
            aria-describedby={
              endError
                ? `${fieldId(node.node_id, "end")}-error`
                : `${fieldId(node.node_id, "end")}-hint`
            }
            onChange={(event) =>
              onBuffer(
                node.node_id,
                "end.value",
                endKind === "distance" ? "distance" : "duration",
                event.target.value,
              )
            }
          />
          <p
            id={`${fieldId(node.node_id, "end")}-hint`}
            className="plan-field__hint"
          >
            {endKind === "distance"
              ? "Meter oder Kilometer; 1,5 km wird zu 1.500 m."
              : "Minuten, z. B. 45; auch 1:30 oder 45 min."}
          </p>
          {endError && (
            <p
              id={`${fieldId(node.node_id, "end")}-error`}
              className="plan-field__error"
              role="alert"
            >
              {endError}
            </p>
          )}
        </div>
      </div>

      <div className="plan-field-row">
        <div className="plan-field">
          <label htmlFor={fieldId(node.node_id, "role")}>Abschnittstyp</label>
          <select
            id={fieldId(node.node_id, "role")}
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
            value={editor.kind}
            onChange={(event) =>
              onTargetKindChange(
                node.node_id,
                event.target.value as TargetEditorKind,
              )
            }
          >
            <option value="none">Ohne Ziel</option>
            <option value="zone" disabled={!zoneOptions.available}>
              Herzfrequenz · Zone
            </option>
            <option value="pace">Pace</option>
            <option value="power">Leistung</option>
            {editor.kind === "heartRate" && (
              <option value="heartRate" disabled>
                Herzfrequenz · bpm (nicht bearbeitbar)
              </option>
            )}
            {powerZoneCapability && !powerZoneCapability.editable && (
              <option value="powerZone" disabled>
                Leistungszone (nicht belegt)
              </option>
            )}
          </select>
          <p className="plan-field__hint">
            Jede Zielart trägt ihre eigene Einheit. Ein Wechsel übernimmt keine
            Zahlen der bisherigen Einheit.
          </p>
        </div>
      </div>

      {(editor.kind === "pace" || editor.kind === "power") && unitOptions.length > 0 && (
        <div className="plan-field-row">
          <div className="plan-field">
            <label htmlFor={unitId}>Zieleinheit</label>
            <select
              id={unitId}
              className="plan-input"
              value={editor.unit ?? unitOptions[0]}
              disabled={unitLocked}
              onChange={(event) =>
                onTargetUnitChange(
                  node.node_id,
                  event.target.value as TargetEditorUnit,
                )
              }
            >
              {unitOptions.map((option) => (
                <option key={option} value={option}>
                  {targetUnitLabel(option)}
                </option>
              ))}
            </select>
            {unitLocked && (
              <p className="plan-field__hint">
                Einheitenwechsel erst nach einem gültigen Pacewert.
              </p>
            )}
          </div>
          <div className="plan-field">
            <label htmlFor={modeId}>Wert oder Bereich</label>
            <select
              id={modeId}
              className="plan-input"
              value={editor.mode}
              onChange={(event) =>
                onTargetModeChange(
                  node.node_id,
                  event.target.value as "value" | "range",
                )
              }
            >
              <option value="value">Einzelwert</option>
              <option value="range">Bereich</option>
            </select>
          </div>
        </div>
      )}

      {(editor.kind === "pace" || editor.kind === "power") && (
        <>
          {editor.mode === "value" ? (
            <TargetField
              nodeId={node.node_id}
              field="target-value"
              label={targetSpec.single}
              placeholder={targetSpec.placeholder}
              value={valueRaw}
              error={valueError}
              inputMode={editor.kind === "power" ? "decimal" : "text"}
              onChange={(raw) =>
                onBuffer(node.node_id, "target.value", targetFieldProps.kind, raw, {
                  targetKind: targetFieldProps.targetKind,
                  unit: targetFieldProps.unit,
                })
              }
            />
          ) : (
            <div className="plan-field-row">
              <TargetField
                nodeId={node.node_id}
                field="target-min"
                label={targetSpec.from}
                placeholder={targetSpec.placeholder}
                value={minRaw}
                error={minError}
                inputMode={editor.kind === "power" ? "decimal" : "text"}
                onChange={(raw) =>
                  onBuffer(node.node_id, "target.min", targetFieldProps.kind, raw, {
                    targetKind: targetFieldProps.targetKind,
                    unit: targetFieldProps.unit,
                  })
                }
              />
              <TargetField
                nodeId={node.node_id}
                field="target-max"
                label={targetSpec.to}
                placeholder={targetSpec.placeholder}
                value={maxRaw}
                error={maxError}
                inputMode={editor.kind === "power" ? "decimal" : "text"}
                onChange={(raw) =>
                  onBuffer(node.node_id, "target.max", targetFieldProps.kind, raw, {
                    targetKind: targetFieldProps.targetKind,
                    unit: targetFieldProps.unit,
                  })
                }
              />
            </div>
          )}
          <p className="plan-field__hint">{targetSpec.hint}</p>
          {editor.kind === "power" && powerZoneCapability && (
            <p className="plan-field__hint">
              {powerZoneCapability.reason}
            </p>
          )}
        </>
      )}

      {editor.kind === "zone" && (
        <div className="plan-field">
          <label htmlFor={zoneId}>HF-Zone</label>
          <select
            id={zoneId}
            className="plan-input"
            value={node.target?.zone_id ?? ""}
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
                {node.target?.text ?? unknownZone} · Referenz nicht im Profil
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
              Die gespeicherte Zonenreferenz {unknownZone} ist im aktuellen Profil
              nicht enthalten. Sie bleibt erhalten, bis du bewusst eine vorhandene
              Zone wählst.
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

      {editor.kind === "heartRate" && (
        <div className="plan-field">
          <p className="plan-field__warning">
            Absolute bpm-Werte bleiben lesbar, sind aber ohne belegten
            Schreibvertrag nicht als synchronisierbares Feld freigeschaltet.{" "}
            {bpmCapability.reason ?? ""}
          </p>
          <p className="plan-field__hint">
            Gespeichert: {node.target?.text ?? "—"}
          </p>
        </div>
      )}

      {editor.kind === "none" && (
        <p className="plan-note plan-note--muted">
          Ohne Ziel werden keine Intensitätsfelder angezeigt und keine künstlichen
          Nullwerte gespeichert.
        </p>
      )}

      <p className="plan-inline__footer">
        Änderungen bleiben lokal. Ein Feld darf unfertig sein; gespeichert wird in
        diesem Paket noch nichts.
      </p>
      {actions}
    </section>
  );
}

function TargetField({
  nodeId,
  field,
  label,
  placeholder,
  value,
  error,
  inputMode,
  onChange,
}: {
  nodeId: string;
  field: string;
  label: string;
  placeholder: string;
  value: string;
  error: string | null;
  inputMode: "text" | "decimal";
  onChange: (raw: string) => void;
}) {
  const id = fieldId(nodeId, field);
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  return (
    <div className="plan-field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        className="plan-input"
        type="text"
        inputMode={inputMode}
        value={value}
        placeholder={placeholder}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : hintId}
        onChange={(event) => onChange(event.target.value)}
      />
      <p id={hintId} className="plan-field__hint">
        {placeholder}
      </p>
      {error && (
        <p id={errorId} className="plan-field__error" role="alert">
          {error}
        </p>
      )}
    </div>
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
  nodes,
  onDiscard,
}: {
  projection: PlanDraftProjection | null;
  buffers: DraftFieldBuffers;
  dirty: boolean;
  nodes: PlanNode[];
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
  const structural = issues.find((issue) =>
    ["empty_workout", "empty_repeat", "no_executed_steps"].includes(issue.code),
  );
  const status = structural
    ? structural.message
    : nodes.length === 0
      ? "Aufbau leer · Speichern gesperrt"
      : invalid
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
        <span
          className={
            dirty
              ? "plan-savebar__state plan-savebar__state--dirty"
              : "plan-savebar__state"
          }
        >
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
