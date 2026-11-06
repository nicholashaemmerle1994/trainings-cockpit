import type {
  PlanDetail,
  PlanDraftProjection,
  PlanGraphTarget,
  PlanNode,
  PlanNodeEnd,
} from "./types";

export type DraftFieldKind = "text" | "duration" | "distance";

/** Ein Feldpuffer gehört genau zu Knoten-ID und Feldpfad. */
export interface DraftFieldBuffer {
  nodeId: string;
  fieldPath: string;
  kind: DraftFieldKind;
  raw: string;
}

export type DraftFieldBuffers = Record<string, DraftFieldBuffer>;

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
      },
    ]),
  );
}

export function draftRequest(
  name: string,
  nodes: PlanNode[],
  buffers: DraftFieldBuffers,
): Record<string, unknown> {
  return {
    name,
    nodes: nodes.map(serializeNode),
    field_buffers: serializeBuffers(buffers),
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
): boolean {
  if (name !== detail.name) return true;
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
