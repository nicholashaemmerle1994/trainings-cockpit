import type { PlanNode } from "./types";
import type { DraftFieldBuffers, TargetEditor } from "./plannerDraft";

/**
 * Lokale Entwürfe für den Planer.
 *
 * Die Ablage ist bewusst browserlokal und nach Account/Athlet getrennt. Sie
 * ersetzt keinen Remote-Vorgang: Wiederherstellen zeigt immer eine
 * Entscheidung, bevor ein Entwurf wieder im Editor landet.
 */
export interface StoredPlannerDraft {
  version: 1;
  account_id: string;
  athlete_id: string;
  scope: string;
  kind: "existing" | "new";
  event_id: number | null;
  draft_id: string | null;
  new_plan: {
    draftId: string;
    sport: string;
    date: string;
    name: string;
    template: "simple" | "repeat" | "empty";
    /** Vollständiger Aufbau, wenn der Entwurf aus einer Vorlage stammt. */
    nodes?: PlanNode[];
  } | null;
  saved_at: string;
  name: string;
  date: string;
  nodes: PlanNode[];
  buffers: DraftFieldBuffers;
  end_kinds: Record<string, "time" | "distance">;
  target_editors: Record<string, TargetEditor>;
  selected: string | null;
  expanded: string | null;
  base_source_hash: string | null;
}

const PREFIX = "tc.planner.draft.v1";
const VERSION = 1;

function accountPart(accountId: string, athleteId: string): string {
  return `${encodeURIComponent(accountId)}:${encodeURIComponent(athleteId)}`;
}

export function plannerDraftScope(
  eventId?: number | null,
  draftId?: string | null,
): string {
  if (eventId != null) return `event:${eventId}`;
  if (draftId) return `new:${draftId}`;
  return "new:unknown";
}

function storageKey(accountId: string, athleteId: string, scope: string): string {
  return `${PREFIX}:${accountPart(accountId, athleteId)}:${encodeURIComponent(scope)}`;
}

function storageAvailable(): boolean {
  try {
    return typeof window !== "undefined" && window.localStorage != null;
  } catch {
    return false;
  }
}

function isEditor(value: unknown): value is TargetEditor {
  if (!value || typeof value !== "object") return false;
  const editor = value as Record<string, unknown>;
  return (
    ["none", "zone", "heartRate", "pace", "power"].includes(
      String(editor.kind),
    ) && ["value", "range"].includes(String(editor.mode))
  );
}

function isBuffer(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const buffer = value as Record<string, unknown>;
  return (
    typeof buffer.nodeId === "string" &&
    typeof buffer.fieldPath === "string" &&
    typeof buffer.kind === "string" &&
    typeof buffer.raw === "string"
  );
}

function parseDraft(raw: string): StoredPlannerDraft | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== "object") return null;
  const entry = parsed as Record<string, unknown>;
  if (
    entry.version !== VERSION ||
    typeof entry.account_id !== "string" ||
    typeof entry.athlete_id !== "string" ||
    typeof entry.scope !== "string" ||
    (entry.kind !== "existing" && entry.kind !== "new") ||
    typeof entry.saved_at !== "string" ||
    typeof entry.name !== "string" ||
    typeof entry.date !== "string" ||
    !Array.isArray(entry.nodes)
  ) {
    return null;
  }
  if (entry.kind === "new") {
    const plan = entry.new_plan;
    if (
      !plan ||
      typeof plan !== "object" ||
      typeof (plan as Record<string, unknown>).draftId !== "string" ||
      typeof (plan as Record<string, unknown>).sport !== "string" ||
      typeof (plan as Record<string, unknown>).date !== "string" ||
      !["simple", "repeat", "empty"].includes(
        String((plan as Record<string, unknown>).template),
      )
    ) {
      return null;
    }
  }
  const buffers: DraftFieldBuffers = {};
  if (entry.buffers && typeof entry.buffers === "object") {
    for (const [key, value] of Object.entries(
      entry.buffers as Record<string, unknown>,
    )) {
      if (isBuffer(value)) buffers[key] = value as StoredPlannerDraft["buffers"][string];
    }
  }
  const targetEditors: Record<string, TargetEditor> = {};
  if (entry.target_editors && typeof entry.target_editors === "object") {
    for (const [key, value] of Object.entries(
      entry.target_editors as Record<string, unknown>,
    )) {
      if (isEditor(value)) targetEditors[key] = value;
    }
  }
  return {
    ...(entry as unknown as StoredPlannerDraft),
    nodes: entry.nodes as PlanNode[],
    buffers,
    end_kinds:
      entry.end_kinds && typeof entry.end_kinds === "object"
        ? (entry.end_kinds as StoredPlannerDraft["end_kinds"])
        : {},
    target_editors: targetEditors,
    selected: typeof entry.selected === "string" ? entry.selected : null,
    expanded: typeof entry.expanded === "string" ? entry.expanded : null,
    base_source_hash:
      typeof entry.base_source_hash === "string" ? entry.base_source_hash : null,
  };
}

export function loadPlannerDraft(
  accountId: string,
  athleteId: string,
  scope: string,
): StoredPlannerDraft | null {
  if (!storageAvailable()) return null;
  try {
    const raw = window.localStorage.getItem(
      storageKey(accountId, athleteId, scope),
    );
    if (!raw) return null;
    const entry = parseDraft(raw);
    if (
      !entry ||
      entry.account_id !== accountId ||
      entry.athlete_id !== athleteId ||
      entry.scope !== scope
    ) {
      return null;
    }
    return entry;
  } catch {
    return null;
  }
}

export function savePlannerDraft(entry: StoredPlannerDraft): void {
  if (!storageAvailable()) return;
  try {
    window.localStorage.setItem(
      storageKey(entry.account_id, entry.athlete_id, entry.scope),
      JSON.stringify(entry),
    );
  } catch {
    /* Privater Modus oder voller Speicher: Der Editor bleibt nutzbar. */
  }
}

export function clearPlannerDraft(
  accountId: string,
  athleteId: string,
  scope: string,
): void {
  if (!storageAvailable()) return;
  try {
    window.localStorage.removeItem(storageKey(accountId, athleteId, scope));
  } catch {
    /* siehe oben */
  }
}

/** Der jüngste lokale Neuentwurf dieses Accounts, für den Wiederanlauf. */
export function latestNewPlannerDraft(
  accountId: string,
  athleteId: string,
): StoredPlannerDraft | null {
  if (!storageAvailable()) return null;
  const prefix = `${PREFIX}:${accountPart(accountId, athleteId)}:`;
  let newest: StoredPlannerDraft | null = null;
  try {
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index);
      if (!key || !key.startsWith(prefix)) continue;
      const raw = window.localStorage.getItem(key);
      if (!raw) continue;
      const entry = parseDraft(raw);
      if (
        !entry ||
        entry.kind !== "new" ||
        entry.account_id !== accountId ||
        entry.athlete_id !== athleteId ||
        !entry.new_plan
      ) {
        continue;
      }
      if (!newest || entry.saved_at > newest.saved_at) newest = entry;
    }
  } catch {
    return null;
  }
  return newest;
}
