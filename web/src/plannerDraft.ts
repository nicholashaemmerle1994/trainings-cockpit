import type {
  PlanDetail,
  PlanDraftProjection,
  PlanGraphTarget,
  PlanNode,
  PlanNodeEnd,
} from "./types";

export type DraftFieldKind =
  | "text"
  | "duration"
  | "distance"
  | "decimal"
  | "pace"
  | "integer";

/** Ein Feldpuffer gehört genau zu Knoten-ID und Feldpfad. */
export interface DraftFieldBuffer {
  nodeId: string;
  fieldPath: string;
  kind: DraftFieldKind;
  raw: string;
  targetKind?: TargetEditorKind;
  unit?: TargetEditorUnit;
}

export type DraftFieldBuffers = Record<string, DraftFieldBuffer>;

export type TargetEditorKind = "none" | "zone" | "heartRate" | "pace" | "power";

export type TargetEditorUnit =
  | "secondsPerKm"
  | "secondsPer100m"
  | "watts"
  | "percentFtp";

export interface TargetEditor {
  kind: TargetEditorKind;
  unit?: TargetEditorUnit;
  mode: "value" | "range";
}

export const TARGET_KIND_LABELS: Record<TargetEditorKind, string> = {
  none: "Ohne Ziel",
  zone: "Herzfrequenz · Zone",
  heartRate: "Herzfrequenz · bpm",
  pace: "Pace",
  power: "Leistung",
};

export function targetUnitLabel(unit: TargetEditorUnit | undefined): string {
  if (unit === "secondsPerKm") return "min/km";
  if (unit === "secondsPer100m") return "min/100 m";
  if (unit === "percentFtp") return "% FTP";
  if (unit === "watts") return "W";
  return "";
}

export function targetEditorLabel(editor: TargetEditor): string {
  if (editor.kind === "pace") {
    return `${TARGET_KIND_LABELS.pace} · ${targetUnitLabel(editor.unit)}`;
  }
  if (editor.kind === "power") {
    return `${TARGET_KIND_LABELS.power} · ${targetUnitLabel(editor.unit)}`;
  }
  return TARGET_KIND_LABELS[editor.kind];
}

export function targetEditorForNode(node: PlanNode): TargetEditor {
  const target = node.target;
  if (!target || target.kind === "none" || target.kind === "missing") {
    return { kind: "none", mode: "value" };
  }
  if (target.kind === "zone") return { kind: "zone", mode: "value" };
  if (target.kind === "heartRate") {
    return {
      kind: "heartRate",
      mode: target.values?.kind === "range" ? "range" : "value",
    };
  }
  if (target.kind === "power") {
    return {
      kind: "power",
      unit: target.unit === "percentFtp" ? "percentFtp" : "watts",
      mode: target.values?.kind === "range" ? "range" : "value",
    };
  }
  return {
    kind: "pace",
    unit:
      target.unit === "secondsPer100m" ? "secondsPer100m" : "secondsPerKm",
    mode: target.values?.kind === "range" ? "range" : "value",
  };
}

export function targetEditorsFromNodes(
  nodes: PlanNode[],
  existing: Record<string, TargetEditor> = {},
): Record<string, TargetEditor> {
  const out = { ...existing };
  for (const node of nodes) {
    if (node.kind === "step") out[node.node_id] = targetEditorForNode(node);
    if (node.kind === "repeat") {
      Object.assign(out, targetEditorsFromNodes(node.children ?? [], out));
    }
  }
  return out;
}
/** Standard-Paceeinheit einer Sportart; importierte Einheiten bleiben sichtbar. */
export function defaultPaceUnit(sport: string): TargetEditorUnit {
  return sport.toLowerCase().includes("swim") ? "secondsPer100m" : "secondsPerKm";
}

export function paceUnitOptions(
  sport: string,
  current: TargetEditorUnit | undefined,
): TargetEditorUnit[] {
  const options: TargetEditorUnit[] = [defaultPaceUnit(sport)];
  if (current && !options.includes(current)) options.push(current);
  return options;
}

/** Echte Umrechnung zwischen min/km und min/100 m (1 km = zehn 100-m-Strecken). */
export function convertPace(
  seconds: number,
  from: TargetEditorUnit,
  to: TargetEditorUnit,
): number {
  if (from === to) return seconds;
  if (from === "secondsPerKm" && to === "secondsPer100m") return seconds / 10;
  if (from === "secondsPer100m" && to === "secondsPerKm") return seconds * 10;
  return seconds;
}

export function numberText(value: number): string {
  const text = Number.isInteger(value)
    ? String(value)
    : value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
  return text.replace(".", ",");
}

export function paceText(seconds: number): string {
  const total = Math.round(seconds);
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

export function targetValueText(
  node: PlanNode,
  editor: TargetEditor,
): string {
  const values = node.target?.values;
  if (!values) return "";
  const raw =
    values.kind === "range"
      ? values.min
      : values.value ?? values.min;
  if (raw == null || Number.isNaN(raw)) return "";
  if (editor.kind === "pace") return paceText(raw);
  return numberText(raw);
}

export function targetRangeText(
  node: PlanNode,
  editor: TargetEditor,
  bound: "min" | "max",
): string {
  const values = node.target?.values;
  if (!values) return "";
  if (values.kind === "range" && values.max === values.min && bound === "max") {
    return "";
  }
  const raw = bound === "min" ? values.min : values.max;
  if (raw == null || Number.isNaN(raw)) return "";
  if (editor.kind === "pace") return paceText(raw);
  return numberText(raw);
}

interface TargetFieldSpec {
  single: string;
  from: string;
  to: string;
  placeholder: string;
  hint: string;
}

/** Eine Quelle für Feldtitel, Grenzbezeichnungen und Hinweise. */
export function targetFieldSpec(editor: TargetEditor): TargetFieldSpec {
  if (editor.kind === "pace") {
    const unit = targetUnitLabel(editor.unit);
    return {
      single: `Pace-Einzelwert (${unit})`,
      from: `Schneller (${unit})`,
      to: `Langsamer (${unit})`,
      placeholder: editor.unit === "secondsPer100m" ? "z. B. 2:00" : "z. B. 5:30",
      hint:
        "Pace als Minuten:Sekunden. Der schnellere Wert ist die kleinere Zeit; " +
        "Sekunden müssen zwischen 00 und 59 liegen.",
    };
  }
  if (editor.kind === "power") {
    const unit = targetUnitLabel(editor.unit);
    return {
      single: `Watt-Einzelwert (${unit})`,
      from: `Von (${unit})`,
      to: `Bis (${unit})`,
      placeholder: editor.unit === "percentFtp" ? "z. B. 60" : "z. B. 160",
      hint:
        editor.unit === "percentFtp"
          ? "Prozent der Schwelle; die relative Vorgabe bleibt erhalten."
          : "Watt als Zahl; auch 0 W ist eine gültige Vorgabe.",
    };
  }
  return {
    single: "Zielwert",
    from: "Von",
    to: "Bis",
    placeholder: "",
    hint: "",
  };
}

export function newNodeId(): string {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return `node:draft:${random}`;
}

export function createStepNode(): PlanNode {
  return {
    kind: "step",
    node_id: newNodeId(),
    name: "Neuer Abschnitt",
    role: "steady",
    end: { kind: "open", text: "Ende offen" },
    target: { kind: "none", text: "Ohne Ziel" },
    notes: null,
    source_ref: null,
  };
}

export function createRepeatNode(): PlanNode {
  return {
    kind: "repeat",
    node_id: newNodeId(),
    name: "Wiederholungsblock",
    repetitions: 3,
    skip_final_recovery: false,
    children: [],
    source_ref: null,
  };
}

export function subtreeIds(node: PlanNode): string[] {
  const ids = [node.node_id];
  for (const child of node.children ?? []) ids.push(...subtreeIds(child));
  return ids;
}

export function nodeListAt(
  nodes: PlanNode[],
  parentId: string | null,
): PlanNode[] | null {
  if (parentId == null) return nodes;
  for (const node of nodes) {
    if (node.node_id === parentId) {
      return node.kind === "repeat" ? node.children ?? [] : null;
    }
    if (node.kind === "repeat") {
      const found = nodeListAt(node.children ?? [], parentId);
      if (found) return found;
    }
  }
  return null;
}

export function insertChild(
  nodes: PlanNode[],
  parentId: string | null,
  child: PlanNode,
): PlanNode[] {
  if (parentId == null) return [...nodes, child];
  return nodes.map((node) => {
    if (node.node_id === parentId && node.kind === "repeat") {
      return { ...node, children: [...(node.children ?? []), child] };
    }
    if (node.kind === "repeat") {
      return { ...node, children: insertChild(node.children ?? [], parentId, child) };
    }
    return node;
  });
}

export interface RemovedNode {
  nodes: PlanNode[];
  removed: PlanNode;
  parentId: string | null;
  nextSelection: string | null;
}

export function removeNode(
  nodes: PlanNode[],
  nodeId: string,
): RemovedNode | null {
  for (let index = 0; index < nodes.length; index += 1) {
    const node = nodes[index];
    if (node.node_id === nodeId) {
      const remaining = [...nodes.slice(0, index), ...nodes.slice(index + 1)];
      const next = remaining[index] ?? remaining[index - 1] ?? null;
      return {
        nodes: remaining,
        removed: node,
        parentId: null,
        nextSelection: next?.node_id ?? null,
      };
    }
    if (node.kind === "repeat") {
      const inner = removeNode(node.children ?? [], nodeId);
      if (inner) {
        const parentId = node.node_id;
        return {
          nodes: nodes.map((candidate) =>
            candidate.node_id === parentId
              ? { ...candidate, children: inner.nodes }
              : candidate,
          ),
          removed: inner.removed,
          parentId,
          nextSelection: inner.nextSelection ?? parentId,
        };
      }
    }
  }
  return null;
}

export function moveNodeInLevel(
  nodes: PlanNode[],
  nodeId: string,
  delta: -1 | 1,
): PlanNode[] {
  const index = nodes.findIndex((node) => node.node_id === nodeId);
  if (index >= 0) {
    const target = index + delta;
    if (target < 0 || target >= nodes.length) return nodes;
    const next = [...nodes];
    const [moved] = next.splice(index, 1);
    next.splice(target, 0, moved);
    return next;
  }
  return nodes.map((node) => {
    if (node.kind !== "repeat") return node;
    const children = moveNodeInLevel(node.children ?? [], nodeId, delta);
    return children === node.children ? node : { ...node, children };
  });
}

export function finalRecoveryChild(node: PlanNode): PlanNode | null {
  if (node.kind !== "repeat") return null;
  const children = node.children ?? [];
  const last = children[children.length - 1];
  return last?.kind === "step" && last.role === "recovery" ? last : null;
}

/** Hält „letzte Erholung auslassen“ nach jeder Strukturänderung ehrlich. */
export function normalizeSkipFinalRecovery(nodes: PlanNode[]): PlanNode[] {
  return nodes.map((node) => {
    if (node.kind !== "repeat") return node;
    const children = normalizeSkipFinalRecovery(node.children ?? []);
    const skip =
      node.skip_final_recovery === true &&
      finalRecoveryChild({ ...node, children }) !== null;
    return { ...node, children, skip_final_recovery: skip };
  });
}

function cloneWithNewIds(node: PlanNode): PlanNode {
  if (node.kind === "repeat") {
    return {
      ...node,
      node_id: newNodeId(),
      children: (node.children ?? []).map(cloneWithNewIds),
    };
  }
  if (node.kind === "step") {
    return { ...node, node_id: newNodeId() };
  }
  return { ...node, node_id: newNodeId() };
}

export interface DissolvedRepeat {
  nodes: PlanNode[];
  firstId: string | null;
}

/** Erzeugt die tatsächliche Ausführungsfolge; Summe und Ablauf bleiben gleich. */
export function dissolveRepeat(
  nodes: PlanNode[],
  nodeId: string,
): DissolvedRepeat | null {
  const index = nodes.findIndex((node) => node.node_id === nodeId);
  if (index >= 0) {
    const node = nodes[index];
    if (node.kind !== "repeat") return null;
    const children = node.children ?? [];
    if (children.length === 0) return null;
    const repetitions = node.repetitions ?? 1;
    const expanded: PlanNode[] = [];
    for (let repetition = 1; repetition <= repetitions; repetition += 1) {
      const isLast = repetition === repetitions;
      const omitted =
        isLast && node.skip_final_recovery ? finalRecoveryChild(node) : null;
      for (const child of children) {
        if (omitted && child.node_id === omitted.node_id) continue;
        expanded.push(cloneWithNewIds(child));
      }
    }
    const next = [...nodes.slice(0, index), ...expanded, ...nodes.slice(index + 1)];
    return { nodes: next, firstId: expanded[0]?.node_id ?? null };
  }
  for (let index = 0; index < nodes.length; index += 1) {
    const node = nodes[index];
    if (node.kind !== "repeat") continue;
    const inner = dissolveRepeat(node.children ?? [], nodeId);
    if (inner) {
      return {
        nodes: nodes.map((candidate) =>
          candidate.node_id === node.node_id
            ? { ...candidate, children: inner.nodes }
            : candidate,
        ),
        firstId: inner.firstId,
      };
    }
  }
  return null;
}

export function fieldKey(nodeId: string, fieldPath: string): string {
  return `${nodeId}:${fieldPath}`;
}

export function endFieldKey(nodeId: string): string {
  return fieldKey(nodeId, "end.value");
}

export function nameFieldKey(nodeId: string): string {
  return fieldKey(nodeId, "name");
}

/** Serialisierte Knotenform, die der Entwurfsendpunkt erwartet. */
export function serializeNode(node: PlanNode): Record<string, unknown> {
  if (node.kind === "step") {
    return {
      kind: "step",
      node_id: node.node_id,
      name: node.name ?? "",
      role: node.role ?? "steady",
      end: serializeEnd(node.end),
      target: serializeTarget(node.target),
      notes: node.notes ?? null,
      source_ref: node.source_ref ?? null,
    };
  }
  if (node.kind === "repeat") {
    return {
      kind: "repeat",
      node_id: node.node_id,
      name: node.name ?? "",
      repetitions: node.repetitions ?? 1,
      skip_final_recovery: node.skip_final_recovery ?? false,
      source_ref: node.source_ref ?? null,
      children: (node.children ?? []).map(serializeNode),
    };
  }
  return {
    kind: "unsupported",
    node_id: node.node_id,
    label: node.label ?? "Nicht unterstützter Abschnitt",
    reason: node.reason ?? "Unbekannter Inhalt.",
    source_ref: node.source_ref ?? `/draft/${node.node_id}`,
  };
}

function serializeEnd(end: PlanNodeEnd | undefined): Record<string, unknown> {
  if (!end || end.kind === "open") return { kind: "open" };
  if (end.kind === "time" && end.seconds != null) {
    return { kind: "time", seconds: end.seconds };
  }
  if (end.kind === "distance" && end.metres != null) {
    return { kind: "distance", metres: end.metres };
  }
  return { kind: "open" };
}

function serializeTarget(target: PlanGraphTarget | undefined): Record<string, unknown> {
  if (!target || target.kind === "none" || target.kind === "missing") {
    return { kind: "none" };
  }
  if (target.kind === "zone") {
    return {
      kind: "zone",
      metric: target.metric ?? "heartRate",
      zone_id: target.zone_id ?? "",
      zone_set_id: target.zone_set_id ?? null,
    };
  }
  return {
    kind: target.kind,
    unit: target.unit,
    values: target.values
      ? {
          kind: target.values.kind,
          value: target.values.value,
          min: target.values.min,
          max: target.values.max,
        }
      : null,
  };
}

export function serializeBuffers(buffers: DraftFieldBuffers): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(buffers).map(([key, buffer]) => [
      key,
      {
        node_id: buffer.nodeId,
        field_path: buffer.fieldPath,
        kind: buffer.kind,
        raw: buffer.raw,
        target_kind: buffer.targetKind ?? null,
        unit: buffer.unit ?? null,
      },
    ]),
  );
}

export function draftRequest(
  name: string,
  nodes: PlanNode[],
  buffers: DraftFieldBuffers,
  date?: string,
): Record<string, unknown> {
  return {
    name,
    ...(date ? { date } : {}),
    nodes: nodes.map(serializeNode),
    field_buffers: serializeBuffers(buffers),
  };
}

export interface NewPlanRequest {
  draftId: string;
  sport: string;
  date: string;
  name: string;
  template: "simple" | "repeat" | "empty";
  nodes?: PlanNode[];
  buffers?: DraftFieldBuffers;
}

/** Der neue Entwurf wird nur lokal projiziert; kein Event-Create. */
export function newDraftRequest(input: NewPlanRequest): Record<string, unknown> {
  return {
    draft_id: input.draftId,
    sport: input.sport,
    date: input.date,
    name: input.name,
    template: input.template,
    ...(input.nodes ? { nodes: input.nodes.map(serializeNode) } : {}),
    ...(input.buffers
      ? { field_buffers: serializeBuffers(input.buffers) }
      : {}),
  };
}

export function bufferRaw(
  buffers: DraftFieldBuffers,
  nodeId: string,
  fieldPath: string,
): string | undefined {
  return buffers[fieldKey(nodeId, fieldPath)]?.raw;
}

/** Der zuletzt gültige Wert als Starttext; offene Enden bleiben leer. */
export function endSeed(node: PlanNode): string {
  if (!node.end || node.end.kind === "open") return "";
  return node.end.text;
}

export function nodeTitle(node: PlanNode): string {
  if (node.kind === "repeat") {
    const name = (node.name || "Wiederholung").trim();
    const repetitions = node.repetitions ?? 1;
    const cleaned = name.replace(/\s*\d+\s*[x×]\s*$/i, "").trim();
    if (cleaned && cleaned !== name) return `${repetitions} × ${cleaned}`;
    if (new RegExp(`^${repetitions}\\s*[x×]`).test(name)) return name;
    return `${repetitions} × ${name}`;
  }
  if (node.kind === "unsupported") return node.label || "Nicht unterstützter Abschnitt";
  return node.name || "Abschnitt";
}

export function nodeMeta(node: PlanNode): string {
  if (node.kind === "repeat") {
    const children = (node.children ?? [])
      .map((child) => child.name || child.label)
      .filter(Boolean)
      .join(" / ");
    return [
      children || "Keine Kindabschnitte",
      node.skip_final_recovery ? "letzte Erholung entfällt" : "",
    ]
      .filter(Boolean)
      .join(" · ");
  }
  if (node.kind === "unsupported") return node.reason ?? "Nicht bearbeitbar";
  return [node.end?.text, node.target?.text].filter(Boolean).join(" · ") || "Ohne Vorgabe";
}

export function nodeById(nodes: PlanNode[], nodeId: string): PlanNode | null {
  for (const node of nodes) {
    if (node.node_id === nodeId) return node;
    if (node.kind === "repeat") {
      const found = nodeById(node.children ?? [], nodeId);
      if (found) return found;
    }
  }
  return null;
}

export function parentGroupId(nodes: PlanNode[], nodeId: string): string | null {
  for (const node of nodes) {
    if (node.kind !== "repeat") continue;
    if ((node.children ?? []).some((child) => child.node_id === nodeId)) {
      return node.node_id;
    }
    const nested = parentGroupId(node.children ?? [], nodeId);
    if (nested) return nested;
  }
  return null;
}

/** Semantische Prüfung ohne Auswahl- und Aufklappzustand. */
export function semanticallyDirty(
  detail: PlanDetail,
  name: string,
  nodes: PlanNode[],
  date?: string,
): boolean {
  if (name !== detail.name) return true;
  if (date != null && date !== detail.date) return true;
  return (
    JSON.stringify(nodes.map(serializeNode)) !==
    JSON.stringify(detail.nodes.map(serializeNode))
  );
}

export function visibleFieldMessage(
  projection: PlanDraftProjection | null,
  key: string,
): string | null {
  const state = projection?.draft.field_states[key];
  if (!state || state.validity === "valid") return null;
  return state.message || "Feld unvollständig.";
}

export function incompleteFields(projection: PlanDraftProjection | null): number {
  if (!projection) return 0;
  return Object.values(projection.draft.field_states).filter(
    (state) => state.validity !== "valid",
  ).length;
}
