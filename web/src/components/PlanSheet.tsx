import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { fmtDateLong } from "../format";
import {
  convertPace,
  createRepeatNode,
  createStepNode,
  defaultPaceUnit,
  dissolveRepeat,
  draftRequest,
  fieldKey,
  newDraftRequest,
  insertChild,
  moveNodeInLevel,
  nodeById,
  nodeTitle,
  normalizeSkipFinalRecovery,
  removeNode,
  semanticallyDirty,
  targetEditorForNode,
  targetEditorsFromNodes,
  targetRangeText,
  targetValueText,
  type DraftFieldBuffers,
  type DraftFieldKind,
  type TargetEditor,
  type TargetEditorKind,
  type TargetEditorUnit,
} from "../plannerDraft";
import type {
  PlanDetail,
  PlanDraftProjection,
  PlanGraph,
  PlanGraphSegment,
  PlanGraphTrack,
  PlanNode,
  PlannerConflict,
  PlannerDeleteResponse,
  PlannerSaveResponse,
} from "../types";
import {
  DraftStatus,
  PlanEditor,
  planFieldElementId,
  planHeadingElementId,
  useHeadScroll,
} from "./PlanEditor";
import type { NewPlanConfig } from "./AddWorkoutSheet";
import {
  registerNavigationGuard,
  unregisterNavigationGuard,
} from "../navigationGuard";
import {
  clearPlannerDraft,
  loadPlannerDraft,
  plannerDraftScope,
  savePlannerDraft,
  type StoredPlannerDraft,
} from "../plannerDraftStore";
import { Sheet } from "./Sheet";
import { StatusBadge } from "./ui";

function firstEditableNode(nodes: PlanNode[]): PlanNode | null {
  let fallback: PlanNode | null = null;
  for (const node of nodes) {
    if (node.kind === "step") return node;
    if (node.kind === "repeat") {
      fallback ??= node;
      const child = firstEditableNode(node.children ?? []);
      if (child) return child;
    }
  }
  return fallback ?? nodes.find((node) => node.kind !== "unsupported") ?? null;
}

function patchNodeTree(
  nodes: PlanNode[],
  nodeId: string,
  patch: Partial<PlanNode>,
): PlanNode[] {
  return nodes.map((node) => {
    if (node.node_id === nodeId) return { ...node, ...patch };
    if (node.kind === "repeat" && node.children) {
      return { ...node, children: patchNodeTree(node.children, nodeId, patch) };
    }
    return node;
  });
}

interface UndoSnapshot {
  message: string;
  nodes: PlanNode[];
  buffers: DraftFieldBuffers;
  endKinds: Record<string, "time" | "distance">;
  targetEditors: Record<string, TargetEditor>;
  selected: string | null;
  expanded: string | null;
}

function withoutNodeData(
  buffers: DraftFieldBuffers,
  targetEditors: Record<string, TargetEditor>,
  ids: Set<string>,
): {
  buffers: DraftFieldBuffers;
  targetEditors: Record<string, TargetEditor>;
} {
  const nextBuffers = Object.fromEntries(
    Object.entries(buffers).filter(([key]) => {
      const owner = key.slice(0, key.lastIndexOf(":"));
      return !ids.has(owner);
    }),
  );
  const nextEditors = Object.fromEntries(
    Object.entries(targetEditors).filter(([nodeId]) => !ids.has(nodeId)),
  );
  return { buffers: nextBuffers, targetEditors: nextEditors };
}

function subtreeNodeIds(nodes: PlanNode[], nodeId: string): Set<string> {
  const node = nodeById(nodes, nodeId);
  if (!node) return new Set([nodeId]);
  const ids = new Set<string>();
  const walk = (candidate: PlanNode) => {
    ids.add(candidate.node_id);
    for (const child of candidate.children ?? []) walk(child);
  };
  walk(node);
  return ids;
}

export function PlanSheet({
  eventId,
  newPlan,
  accountId,
  athleteId,
  online,
  onClose,
  onSaved,
  onDeleted,
  onPending,
  revision = 0,
}: {
  eventId?: number;
  newPlan?: NewPlanConfig | null;
  accountId: string;
  athleteId: string;
  online: boolean;
  onClose: () => void;
  onSaved?: (result: PlannerSaveResponse) => void;
  onDeleted?: (result: PlannerDeleteResponse) => void;
  onPending?: () => void;
  revision?: number;
}) {
  const [data, setData] = useState<PlanDetail | null>(null);
  const [projection, setProjection] = useState<PlanDraftProjection | null>(null);
  const [nodes, setNodes] = useState<PlanNode[]>([]);
  const [buffers, setBuffers] = useState<DraftFieldBuffers>({});
  const [endKinds, setEndKinds] = useState<Record<string, "time" | "distance">>({});
  const [targetEditors, setTargetEditors] = useState<Record<string, TargetEditor>>({});
  const [undo, setUndo] = useState<UndoSnapshot | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [planName, setPlanName] = useState("");
  const [planDate, setPlanDate] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveLocked, setSaveLocked] = useState(false);
  const [conflict, setConflict] = useState<PlannerConflict | null>(null);
  const [remoteOpen, setRemoteOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [recovery, setRecovery] = useState<StoredPlannerDraft | null>(null);
  const draftActive = useRef(false);
  const requestSeq = useRef(0);
  const saveSeq = useRef(0);
  const dirtyRef = useRef(false);
  const savingRef = useRef(false);
  const editingRef = useRef(false);
  const resetDraftRef = useRef<() => void>(() => {});
  const mountedRef = useRef(true);
  const headScroll = useHeadScroll();
  const isNew = newPlan != null;
  const scope = plannerDraftScope(eventId, newPlan?.draftId);

  const applyNewProjection = (next: PlanDraftProjection) => {
    setData(next);
    setProjection(next);
    setPlanName(next.name);
    setPlanDate(next.date);
    setNodes(next.nodes);
    setTargetEditors(targetEditorsFromNodes(next.nodes));
    setEditing(true);
    const first = firstEditableNode(next.nodes);
    setSelected(first?.node_id ?? null);
    setExpanded(first?.node_id ?? null);
  };

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    draftActive.current = false;
    requestSeq.current += 1;
    setData(null);
    setProjection(null);
    setNodes([]);
    setBuffers({});
    setEndKinds({});
    setTargetEditors({});
    setUndo(null);
    setAddOpen(false);
    setEditing(false);
    setPlanName("");
    setPlanDate("");
    setExpanded(null);
    setSelected(null);
    setError(null);
    setDraftError(null);
    setSaving(false);
    setSaveMessage(null);
    setSaveError(null);
    setSaveLocked(false);
    setConflict(null);
    setRemoteOpen(false);
    setDeleteOpen(false);
    setDeleting(false);
    setDeleteError(null);
    setRecovery(null);
    editingRef.current = false;

    if (newPlan) {
      // „Weiter“ legt nur einen lokalen Entwurf an. Dieser Request ist kein
      // Event-Create und liest auch keinen Remote-Plan.
      api
        .newPlanDraft(
          newDraftRequest({
            draftId: newPlan.draftId,
            sport: newPlan.sport,
            date: newPlan.date,
            name: newPlan.name,
            template: newPlan.template,
          }),
        )
        .then((next) => {
          if (!alive) return;
          applyNewProjection(next);
          const stored = loadPlannerDraft(
            accountId,
            athleteId,
            plannerDraftScope(null, newPlan.draftId),
          );
          if (stored) {
            // Erst entscheiden, dann bearbeiten: Der gespeicherte Entwurf wird
            // nicht ungefragt über die neue Projektion gelegt.
            setEditing(false);
            setRecovery(stored);
          }
        })
        .catch((cause: unknown) => {
          if (alive) {
            setError(
              cause instanceof Error
                ? cause.message
                : "Der lokale Entwurf konnte nicht angelegt werden.",
            );
          }
        });
      return () => {
        alive = false;
      };
    }

    if (eventId == null) {
      setError("Planung nicht gefunden.");
      return () => {
        alive = false;
      };
    }
    api
      .planDetail(eventId)
      .then((next) => {
        // Ein begonnener Entwurf wird von einem späteren Hintergrund-Read
        // nicht überschrieben.
        if (alive && !draftActive.current) {
          setData(next);
          setPlanName(next.name);
          setPlanDate(next.date);
          setNodes(next.nodes);
          setRecovery(loadPlannerDraft(accountId, athleteId, plannerDraftScope(eventId)));
        }
      })
      .catch((cause: unknown) => {
        if (alive) setError(cause instanceof Error ? cause.message : "Planung nicht geladen.");
      });
    return () => {
      alive = false;
    };
  }, [eventId, newPlan, accountId, athleteId]);

  useEffect(() => {
    if (revision === 0 || editing || isNew || eventId == null || draftActive.current) return;
    // Ein bestätigter Sync/Write aktualisiert die Leseansicht, aber nie einen
    // offenen Entwurf.
    let alive = true;
    api
      .planDetail(eventId)
      .then((next) => {
        if (!alive || draftActive.current) return;
        setData(next);
        setPlanName(next.name);
        setPlanDate(next.date);
        setNodes(next.nodes);
      })
      .catch(() => {
        /* Die vorhandene Ansicht bleibt stehen; der nächste Reload versucht es erneut. */
      });
    return () => {
      alive = false;
    };
  }, [revision, editing, isNew, eventId]);

  useEffect(() => {
    if (!editing || !data) return;
    const seq = ++requestSeq.current;
    const timer = window.setTimeout(() => {
      const request = newPlan
        ? api.newPlanDraft(
            newDraftRequest({
              draftId: newPlan.draftId,
              sport: newPlan.sport,
              date: planDate,
              name: planName,
              template: newPlan.template,
              nodes,
              buffers,
            }),
          )
        : data.id != null
          ? api.planDraft(
              data.id,
              draftRequest(planName, nodes, buffers, planDate),
            )
          : Promise.reject(new Error("Planung nicht gefunden."));
      request
        .then((next) => {
          if (seq !== requestSeq.current) return;
          setProjection(next);
          setDraftError(null);
          setNodes((current) =>
            JSON.stringify(current) === JSON.stringify(next.nodes)
              ? current
              : next.nodes,
          );
        })
        .catch((cause: unknown) => {
          if (seq !== requestSeq.current) return;
          setDraftError(
            cause instanceof Error ? cause.message : "Entwurf konnte nicht geprüft werden.",
          );
        });
    }, 260);
    return () => {
      window.clearTimeout(timer);
      if (requestSeq.current === seq) requestSeq.current += 1;
    };
  }, [editing, data, newPlan, planName, planDate, nodes, buffers]);

  const current = projection ?? data;
  const dirty = isNew
    ? current != null
    : current != null &&
      semanticallyDirty(data ?? current, planName, nodes, planDate);
  const hasFieldInput = Object.keys(buffers).length > 0;
  const guardDirty = editing && (dirty || hasFieldInput);
  dirtyRef.current = guardDirty;
  savingRef.current = saving || saveLocked;
  editingRef.current = editing;
  const structuralBlock = projection?.draft.issues.some((issue) =>
    ["empty_workout", "empty_repeat", "no_executed_steps", "open_end"].includes(
      issue.code,
    ),
  );
  const invalidField = projection
    ? Object.values(projection.draft.field_states).some(
        (state) => state.validity !== "valid",
      )
    : false;
  const canSave =
    editing &&
    dirty &&
    !saving &&
    projection != null &&
    projection.draft.valid &&
    projection.draft.write.available &&
    !saveLocked &&
    conflict == null &&
    !structuralBlock &&
    !invalidField &&
    nodes.length > 0;

  const clearLocalDraft = () => {
    clearPlannerDraft(accountId, athleteId, scope);
    setRecovery(null);
  };

  const startEdit = () => {
    if (!data || (!data.rights.can_edit_structure && !data.rights.can_edit_metadata)) {
      return;
    }
    clearLocalDraft();
    draftActive.current = true;
    setEditing(true);
    setProjection(null);
    setDraftError(null);
    setSaveError(null);
    setSaveMessage(null);
    setConflict(null);
    setRemoteOpen(false);
    setSaveLocked(false);
    setPlanName(data.name);
    setPlanDate(data.date);
    setNodes(data.nodes);
    setBuffers({});
    setEndKinds({});
    setTargetEditors(targetEditorsFromNodes(data.nodes));
    setUndo(null);
    setAddOpen(false);
    const first = data.rights.can_edit_structure
      ? firstEditableNode(data.nodes)
      : null;
    setSelected(first?.node_id ?? null);
    setExpanded(first?.node_id ?? null);
    window.requestAnimationFrame(() => {
      if (first) {
        document.getElementById(planHeadingElementId(first.node_id))?.focus();
      } else {
        // Metadatenmodus: kein Struktur-Editor, der Name ist das erste Feld.
        document.getElementById("plan-meta-name")?.focus();
      }
    });
  };

  /** Nur den lokalen Zustand zurücksetzen; Navigation erledigt der Aufrufer. */
  const resetDraft = () => {
    clearLocalDraft();
    draftActive.current = false;
    editingRef.current = false;
    dirtyRef.current = false;
    savingRef.current = false;
    setEditing(false);
    setProjection(null);
    setDraftError(null);
    setSaveError(null);
    setSaveMessage(null);
    setConflict(null);
    setRemoteOpen(false);
    setSaveLocked(false);
    setPlanName(data?.name ?? "");
    setPlanDate(data?.date ?? "");
    setNodes(data?.nodes ?? []);
    setBuffers({});
    setEndKinds({});
    setTargetEditors({});
    setUndo(null);
    setAddOpen(false);
    setSelected(null);
    setExpanded(null);
  };
  resetDraftRef.current = resetDraft;

  const discard = () => {
    if (isNew) {
      // Abbrechen vor dem ersten Speichern hinterlässt kein Remote-Event.
      resetDraft();
      onClose();
      return;
    }
    resetDraft();
  };

  const restoreRecovery = () => {
    if (!recovery) return;
    draftActive.current = true;
    setEditing(true);
    setProjection(null);
    setPlanName(recovery.name);
    setPlanDate(recovery.date);
    setNodes(recovery.nodes);
    setBuffers(recovery.buffers);
    setEndKinds(recovery.end_kinds);
    setTargetEditors(recovery.target_editors);
    setUndo(null);
    setAddOpen(false);
    setSelected(recovery.selected);
    setExpanded(recovery.expanded);
    const currentHash = data?.source_snapshot?.relevant_content_hash ?? null;
    setDraftError(
      recovery.base_source_hash &&
        currentHash &&
        recovery.base_source_hash !== currentHash
        ? "Der gespeicherte Entwurf beruht auf einer älteren Remoteversion. Bitte vor dem Speichern prüfen; es wird nichts automatisch geschrieben."
        : null,
    );
    setRecovery(null);
  };

  const discardRecovery = () => {
    clearLocalDraft();
  };

  const focusIssue = (nodeId: string | null, fieldPath: string | null) => {
    if (nodeId == null) {
      document.getElementById("plan-add-trigger")?.focus();
      return;
    }
    const node = nodeById(nodes, nodeId);
    setSelected(nodeId);
    setExpanded(nodeId);
    window.requestAnimationFrame(() => {
      const id =
        fieldPath && node
          ? planFieldElementId(nodeId, fieldPath, node.kind)
          : planHeadingElementId(nodeId);
      const element = document.getElementById(id) as HTMLElement | null;
      if (!element) return;
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      element.scrollIntoView({
        block: "center",
        behavior: reduce ? "auto" : "smooth",
      });
      element.focus({ preventScroll: true });
    });
  };

  useEffect(() => {
    const guard = {
      isDirty: () => dirtyRef.current,
      isSaving: () => savingRef.current,
      discard: () => resetDraftRef.current(),
    };
    registerNavigationGuard(guard);
    return () => unregisterNavigationGuard(guard);
  }, []);

  // Kurz entprellt sichern; ein Absturz oder Reload verliert den Entwurf
  // damit nicht. Wiederhergestellt wird nur nach ausdrücklicher Entscheidung.
  useEffect(() => {
    if (!editing) return;
    const timer = window.setTimeout(() => {
      if (!editingRef.current) return;
      if (!guardDirty) {
        clearPlannerDraft(accountId, athleteId, scope);
        return;
      }
      savePlannerDraft({
        version: 1,
        account_id: accountId,
        athlete_id: athleteId,
        scope,
        kind: isNew ? "new" : "existing",
        event_id: eventId ?? null,
        draft_id: newPlan?.draftId ?? null,
        new_plan: newPlan
          ? {
              draftId: newPlan.draftId,
              sport: newPlan.sport,
              date: newPlan.date,
              name: newPlan.name,
              template: newPlan.template,
            }
          : null,
        saved_at: new Date().toISOString(),
        name: planName,
        date: planDate,
        nodes,
        buffers,
        end_kinds: endKinds,
        target_editors: targetEditors,
        selected,
        expanded,
        base_source_hash: data?.source_snapshot?.relevant_content_hash ?? null,
      });
    }, 450);
    return () => window.clearTimeout(timer);
  }, [
    editing,
    guardDirty,
    accountId,
    athleteId,
    scope,
    isNew,
    eventId,
    newPlan,
    planName,
    planDate,
    nodes,
    buffers,
    endKinds,
    targetEditors,
    selected,
    expanded,
    data?.source_snapshot?.relevant_content_hash,
  ]);

  const save = async () => {
    if (!canSave || saving) return;
    if (
      !online ||
      (typeof navigator !== "undefined" && !navigator.onLine)
    ) {
      setSaveMessage(null);
      setSaveError(
        "Offline – es wurde nichts remote gespeichert. Der lokale Entwurf bleibt erhalten.",
      );
      return;
    }
    const seq = ++saveSeq.current;
    setSaving(true);
    setSaveError(null);
    setSaveMessage(null);
    setConflict(null);
    setRemoteOpen(false);
    try {
      const body = newPlan
        ? newDraftRequest({
            draftId: newPlan.draftId,
            sport: newPlan.sport,
            date: planDate,
            name: planName,
            template: newPlan.template,
            nodes,
            buffers,
          })
        : data?.id != null
          ? draftRequest(planName, nodes, buffers, planDate)
          : null;
      if (!body) throw new Error("Planung nicht gefunden.");
      const result = newPlan
        ? await api.saveNewPlan(body)
        : await api.savePlan(data!.id!, body);
      // Eine verspätete Antwort eines älteren Speicherversuchs oder eines
      // bereits verlassenen Blattes darf den neueren Zustand nicht überschreiben.
      if (seq !== saveSeq.current || !mountedRef.current) return;
      if (result.status.state === "saved" || result.status.state === "clean") {
        clearLocalDraft();
        draftActive.current = false;
        dirtyRef.current = false;
        editingRef.current = false;
        setEditing(false);
        setProjection(null);
        setSaveMessage(result.status.message);
        onSaved?.(result);
        return;
      }
      if (result.status.state === "conflict") {
        setConflict(result.status.conflict);
        setSaveMessage(result.status.message);
        return;
      }
      setSaveLocked(result.status.locked);
      setSaveError(result.status.message);
      setSaveMessage(result.status.message);
      if (result.status.locked) onPending?.();
    } catch (cause: unknown) {
      if (seq !== saveSeq.current) return;
      setSaveError(
        typeof navigator !== "undefined" && !navigator.onLine
          ? "Offline – es wurde nichts remote gespeichert. Der lokale Entwurf bleibt erhalten."
          : cause instanceof Error
            ? cause.message
            : "Speichern fehlgeschlagen.",
      );
    } finally {
      if (seq === saveSeq.current) setSaving(false);
    }
  };

  const removePlan = async () => {
    const id = eventId ?? data?.id ?? null;
    if (id == null || isNew || deleting) return;
    if (
      !online ||
      (typeof navigator !== "undefined" && !navigator.onLine)
    ) {
      setDeleteError(
        "Offline – die Einheit wurde nicht gelöscht. Es wurde nichts remote geändert.",
      );
      return;
    }
    setDeleting(true);
    setDeleteError(null);
    try {
      const result = await api.deletePlan(id);
      if (!mountedRef.current) return;
      clearLocalDraft();
      draftActive.current = false;
      dirtyRef.current = false;
      editingRef.current = false;
      if (onDeleted) onDeleted(result);
      else onClose();
    } catch (cause: unknown) {
      if (!mountedRef.current) return;
      setDeleteError(
        typeof navigator !== "undefined" && !navigator.onLine
          ? "Offline – die Einheit wurde nicht gelöscht. Es wurde nichts remote geändert."
          : cause instanceof Error
            ? cause.message
            : "Löschen fehlgeschlagen.",
      );
    } finally {
      if (mountedRef.current) setDeleting(false);
    }
  };

  const adoptRemote = async () => {
    // Bei einer extern gelöschten Einheit gibt es keine Remoteversion zum
    // Übernehmen. Dann wird nur der lokale Entwurf verworfen und geschlossen.
    const remoteExists = conflict?.remote != null;
    setConflict(null);
    setRemoteOpen(false);
    setSaveError(null);
    setSaveMessage(null);
    clearLocalDraft();
    editingRef.current = false;
    dirtyRef.current = false;
    if (isNew || eventId == null || !remoteExists) {
      onClose();
      return;
    }
    try {
      const next = await api.planRemote(eventId);
      draftActive.current = false;
      setEditing(false);
      setProjection(null);
      setBuffers({});
      setEndKinds({});
      setTargetEditors({});
      setUndo(null);
      setAddOpen(false);
      setSelected(null);
      setExpanded(null);
      setData(next);
      setPlanName(next.name);
      setPlanDate(next.date);
      setNodes(next.nodes);
    } catch (cause: unknown) {
      setSaveError(
        cause instanceof Error
          ? cause.message
          : "Die Remoteversion konnte nicht geladen werden.",
      );
    }
  };

  const onSelect = (nodeId: string) => {
    if (!editing) {
      setSelected((currentId) => (currentId === nodeId ? null : nodeId));
      return;
    }
    // Graphauswahl öffnet den zugehörigen Abschnitt; erneutes Wählen
    // derselben Auswahl lässt ihn offen.
    setSelected(nodeId);
    setExpanded(nodeId);
    window.requestAnimationFrame(() => headScroll.reveal(nodeId));
  };

  const onToggle = (nodeId: string) => {
    setSelected(nodeId);
    setExpanded((currentId) => (currentId === nodeId ? null : nodeId));
  };

  const onBuffer = (
    nodeId: string,
    fieldPath: string,
    kind: DraftFieldKind,
    raw: string,
    options?: { targetKind?: TargetEditorKind; unit?: TargetEditorUnit },
  ) => {
    const key = fieldKey(nodeId, fieldPath);
    setUndo(null);
    setBuffers((currentBuffers) => ({
      ...currentBuffers,
      [key]: {
        nodeId,
        fieldPath,
        kind,
        raw,
        targetKind: options?.targetKind,
        unit: options?.unit,
      },
    }));
  };

  const replaceTargetBuffers = (
    nodeId: string,
    entries: {
      fieldPath: string;
      kind: DraftFieldKind;
      raw: string;
      targetKind: TargetEditorKind;
      unit?: TargetEditorUnit;
    }[],
  ) => {
    setBuffers((currentBuffers) => {
      const next = { ...currentBuffers };
      for (const key of Object.keys(next)) {
        if (key.startsWith(`${nodeId}:target.`)) delete next[key];
      }
      for (const entry of entries) {
        next[fieldKey(nodeId, entry.fieldPath)] = {
          nodeId,
          fieldPath: entry.fieldPath,
          kind: entry.kind,
          raw: entry.raw,
          targetKind: entry.targetKind,
          unit: entry.unit,
        };
      }
      return next;
    });
  };

  const onPatchNode = (nodeId: string, patch: Partial<PlanNode>) => {
    setUndo(null);
    setNodes((currentNodes) =>
      normalizeSkipFinalRecovery(patchNodeTree(currentNodes, nodeId, patch)),
    );
  };

  const onEndKindChange = (nodeId: string, kind: "time" | "distance") => {
    setUndo(null);
    setEndKinds((currentKinds) => ({ ...currentKinds, [nodeId]: kind }));
    setBuffers((currentBuffers) => {
      const key = fieldKey(nodeId, "end.value");
      if (!(key in currentBuffers)) return currentBuffers;
      const next = { ...currentBuffers };
      delete next[key];
      return next;
    });
    setNodes((currentNodes) =>
      patchNodeTree(currentNodes, nodeId, {
        end: { kind: "open", text: "Ende offen" },
      }),
    );
  };

  const onTargetKindChange = (
    nodeId: string,
    kind: TargetEditorKind,
    unit?: TargetEditorUnit,
  ) => {
    const node = nodeById(nodes, nodeId);
    if (!node || node.kind !== "step") return;
    setUndo(null);
    replaceTargetBuffers(nodeId, []);
    if (kind === "none") {
      setTargetEditors((current) => ({
        ...current,
        [nodeId]: { kind: "none", mode: "value" },
      }));
      setNodes((currentNodes) =>
        patchNodeTree(currentNodes, nodeId, {
          target: { kind: "none", text: "Ohne Ziel" },
        }),
      );
      return;
    }
    if (kind === "zone") {
      const zone = data?.zone_options.zones[0];
      const editor: TargetEditor = { kind: "zone", mode: "value" };
      setTargetEditors((current) => ({ ...current, [nodeId]: editor }));
      setNodes((currentNodes) =>
        patchNodeTree(currentNodes, nodeId, {
          target: {
            kind: "zone",
            metric: "heartRate",
            zone_id: zone?.id ?? "",
            zone_set_id: data?.zone_options.zone_set_id ?? null,
            text: zone?.label ?? "HF-Zone",
          },
        }),
      );
      return;
    }
    if (kind === "heartRate") {
      setTargetEditors((current) => ({
        ...current,
        [nodeId]: { kind: "heartRate", mode: "value" },
      }));
      return;
    }
    const nextUnit =
      unit ?? (kind === "pace" ? defaultPaceUnit(data?.sport ?? "") : "watts");
    const editor: TargetEditor = { kind, unit: nextUnit, mode: "value" };
    setTargetEditors((current) => ({ ...current, [nodeId]: editor }));
    setNodes((currentNodes) =>
      patchNodeTree(currentNodes, nodeId, {
        target: { kind: "none", text: "Ohne Ziel" },
      }),
    );
    replaceTargetBuffers(nodeId, [
      {
        fieldPath: "target.value",
        kind: kind === "pace" ? "pace" : "decimal",
        raw: "",
        targetKind: kind,
        unit: nextUnit,
      },
    ]);
  };

  const onTargetUnitChange = (nodeId: string, unit: TargetEditorUnit) => {
    const node = nodeById(nodes, nodeId);
    const editor = targetEditors[nodeId] ?? (node ? targetEditorForNode(node) : null);
    if (!node || node.kind !== "step" || !editor) return;
    setUndo(null);
    if (editor.kind === "pace" && node.target?.kind === "pace" && node.target.values) {
      const currentTarget = node.target;
      const values = currentTarget.values;
      if (!values) return;
      setNodes((currentNodes) =>
        patchNodeTree(currentNodes, nodeId, {
          target: {
            kind: "pace",
            metric: "pace",
            unit,
            values:
              values.kind === "range"
                ? {
                    kind: "range",
                    min: convertPace(values.min, editor.unit ?? "secondsPerKm", unit),
                    max: convertPace(values.max, editor.unit ?? "secondsPerKm", unit),
                  }
                : {
                    kind: "value",
                    value: convertPace(
                      values.value ?? values.min,
                      editor.unit ?? "secondsPerKm",
                      unit,
                    ),
                    min: convertPace(
                      values.value ?? values.min,
                      editor.unit ?? "secondsPerKm",
                      unit,
                    ),
                    max: convertPace(
                      values.value ?? values.min,
                      editor.unit ?? "secondsPerKm",
                      unit,
                    ),
                  },
            text: currentTarget.text,
          },
        }),
      );
      replaceTargetBuffers(nodeId, []);
      setTargetEditors((current) => ({
        ...current,
        [nodeId]: { ...editor, unit },
      }));
      return;
    }
    // Watt ↔ % FTP ist keine Umrechnung: die alte Zahl wird bewusst gelöscht.
    const nextEditor: TargetEditor = { ...editor, unit };
    setTargetEditors((current) => ({ ...current, [nodeId]: nextEditor }));
    setNodes((currentNodes) =>
      patchNodeTree(currentNodes, nodeId, {
        target: { kind: "none", text: "Ohne Ziel" },
      }),
    );
    replaceTargetBuffers(
      nodeId,
      nextEditor.mode === "range"
        ? [
            {
              fieldPath: "target.min",
              kind: editor.kind === "pace" ? "pace" : "decimal",
              raw: "",
              targetKind: editor.kind,
              unit,
            },
            {
              fieldPath: "target.max",
              kind: editor.kind === "pace" ? "pace" : "decimal",
              raw: "",
              targetKind: editor.kind,
              unit,
            },
          ]
        : [
            {
              fieldPath: "target.value",
              kind: editor.kind === "pace" ? "pace" : "decimal",
              raw: "",
              targetKind: editor.kind,
              unit,
            },
          ],
    );
  };

  const onTargetModeChange = (nodeId: string, mode: "value" | "range") => {
    const node = nodeById(nodes, nodeId);
    const editor = targetEditors[nodeId] ?? (node ? targetEditorForNode(node) : null);
    if (!node || node.kind !== "step" || !editor || editor.mode === mode) return;
    setUndo(null);
    const fieldKind: DraftFieldKind = editor.kind === "pace" ? "pace" : "decimal";
    if (mode === "range") {
      const first =
        buffers[fieldKey(nodeId, "target.value")]?.raw ??
        targetValueText(node, editor);
      setTargetEditors((current) => ({
        ...current,
        [nodeId]: { ...editor, mode: "range" },
      }));
      replaceTargetBuffers(nodeId, [
        {
          fieldPath: "target.min",
          kind: fieldKind,
          raw: first,
          targetKind: editor.kind,
          unit: editor.unit,
        },
        {
          fieldPath: "target.max",
          kind: fieldKind,
          raw: "",
          targetKind: editor.kind,
          unit: editor.unit,
        },
      ]);
      return;
    }
    const first =
      buffers[fieldKey(nodeId, "target.min")]?.raw ??
      targetRangeText(node, editor, "min");
    setTargetEditors((current) => ({
      ...current,
      [nodeId]: { ...editor, mode: "value" },
    }));
    replaceTargetBuffers(nodeId, [
      {
        fieldPath: "target.value",
        kind: fieldKind,
        raw: first,
        targetKind: editor.kind,
        unit: editor.unit,
      },
    ]);
  };

  const snapshot = (message: string): UndoSnapshot => ({
    message,
    nodes,
    buffers,
    endKinds,
    targetEditors,
    selected,
    expanded,
  });

  const addRoot = (kind: "step" | "repeat") => {
    const node = kind === "step" ? createStepNode() : createRepeatNode();
    setUndo(null);
    setAddOpen(false);
    setNodes((currentNodes) => normalizeSkipFinalRecovery([...currentNodes, node]));
    setTargetEditors((current) =>
      kind === "step"
        ? { ...current, [node.node_id]: targetEditorForNode(node) }
        : current,
    );
    setSelected(node.node_id);
    setExpanded(node.node_id);
    window.requestAnimationFrame(() => headScroll.reveal(node.node_id));
  };

  const addChild = (groupId: string) => {
    const node = createStepNode();
    setUndo(null);
    setNodes((currentNodes) =>
      normalizeSkipFinalRecovery(insertChild(currentNodes, groupId, node)),
    );
    setTargetEditors((current) => ({
      ...current,
      [node.node_id]: targetEditorForNode(node),
    }));
    setSelected(node.node_id);
    setExpanded(node.node_id);
    window.requestAnimationFrame(() => headScroll.reveal(node.node_id));
  };

  const remove = (nodeId: string) => {
    const result = removeNode(nodes, nodeId);
    if (!result) return;
    const removed = result.removed;
    const ids = subtreeNodeIds(nodes, nodeId);
    const cleaned = withoutNodeData(buffers, targetEditors, ids);
    setUndo(snapshot(
      removed.kind === "repeat" ? "Wiederholungsblock entfernt" : "Abschnitt entfernt",
    ));
    setNodes(normalizeSkipFinalRecovery(result.nodes));
    setBuffers(cleaned.buffers);
    setTargetEditors(cleaned.targetEditors);
    setEndKinds((current) =>
      Object.fromEntries(Object.entries(current).filter(([key]) => !ids.has(key))),
    );
    setSelected(result.nextSelection);
    setExpanded(result.nextSelection);
    if (result.nextSelection) {
      window.requestAnimationFrame(() => headScroll.reveal(result.nextSelection!));
    }
  };

  const move = (nodeId: string, delta: -1 | 1) => {
    setUndo(null);
    setNodes((currentNodes) =>
      normalizeSkipFinalRecovery(moveNodeInLevel(currentNodes, nodeId, delta)),
    );
    setSelected(nodeId);
  };

  const dissolve = (groupId: string) => {
    const result = dissolveRepeat(nodes, groupId);
    if (!result) return;
    const ids = subtreeNodeIds(nodes, groupId);
    const cleaned = withoutNodeData(buffers, targetEditors, ids);
    setUndo(snapshot("Wiederholungsblock aufgelöst"));
    setNodes(normalizeSkipFinalRecovery(result.nodes));
    setBuffers(cleaned.buffers);
    setTargetEditors({
      ...cleaned.targetEditors,
      ...targetEditorsFromNodes(result.nodes),
    });
    setEndKinds((current) =>
      Object.fromEntries(Object.entries(current).filter(([key]) => !ids.has(key))),
    );
    setSelected(result.firstId);
    setExpanded(result.firstId);
    if (result.firstId) {
      window.requestAnimationFrame(() => headScroll.reveal(result.firstId!));
    }
  };

  const undoAction = () => {
    if (!undo) return;
    setNodes(undo.nodes);
    setBuffers(undo.buffers);
    setEndKinds(undo.endKinds);
    setTargetEditors(undo.targetEditors);
    setSelected(undo.selected);
    setExpanded(undo.expanded);
    setUndo(null);
  };

  return (
    <Sheet
      crumb={
        isNew
          ? "Neue Einheit"
          : editing
            ? "Einheit bearbeiten"
            : "Geplante Einheit"
      }
      label={current ? planName || current.sport_label : "Geplante Einheit"}
      onClose={onClose}
    >
      {error && <p className="sheet-error">{error}</p>}
      {!data && !error && <div className="sheet-loading" />}
      {data && current && (
        <PlanBody
          data={current}
          editing={editing}
          isNew={isNew}
          planName={planName}
          planDate={planDate}
          onPlanName={(value) => {
            setUndo(null);
            setPlanName(value);
          }}
          onPlanDate={(value) => {
            setUndo(null);
            setPlanDate(value);
          }}
          nodes={nodes}
          buffers={buffers}
          endKinds={endKinds}
          targetEditors={targetEditors}
          inputLocked={saving || saveLocked}
          undo={undo}
          addOpen={addOpen}
          projection={projection}
          selected={selected}
          expanded={expanded}
          draftError={draftError}
          onEdit={startEdit}
          onDiscard={discard}
          onSelect={onSelect}
          onToggle={onToggle}
          onBuffer={onBuffer}
          onPatchNode={onPatchNode}
          onEndKindChange={onEndKindChange}
          onTargetKindChange={onTargetKindChange}
          onTargetUnitChange={onTargetUnitChange}
          onTargetModeChange={onTargetModeChange}
          onMove={move}
          onRemove={remove}
          onAddRoot={addRoot}
          onAddChild={addChild}
          onDissolve={dissolve}
          onUndo={undoAction}
          onAddOpen={setAddOpen}
          registerHead={headScroll.register}
          dirty={dirty}
          saving={saving}
          canSave={canSave}
          saveLocked={saveLocked}
          saveMessage={saveMessage}
          saveError={saveError}
          conflict={conflict}
          remoteOpen={remoteOpen}
          online={online}
          deleteOpen={deleteOpen}
          deleting={deleting}
          deleteError={deleteError}
          onDeleteOpen={() => {
            setDeleteError(null);
            setDeleteOpen(true);
          }}
          onDeleteCancel={() => {
            setDeleteError(null);
            setDeleteOpen(false);
          }}
          onConfirmDelete={() => void removePlan()}
          recovery={recovery}
          onRestoreRecovery={restoreRecovery}
          onDiscardRecovery={discardRecovery}
          onFocusIssue={focusIssue}
          onSave={() => void save()}
          onViewRemote={() => setRemoteOpen(true)}
          onReturnToDraft={() => {
            setConflict(null);
            setRemoteOpen(false);
          }}
          onAdoptRemote={() => void adoptRemote()}
        />
      )}
    </Sheet>
  );
}

function PlanBody({
  data,
  editing,
  isNew,
  planName,
  planDate,
  onPlanName,
  onPlanDate,
  nodes,
  buffers,
  endKinds,
  targetEditors,
  inputLocked,
  undo,
  addOpen,
  projection,
  selected,
  expanded,
  draftError,
  onEdit,
  onDiscard,
  onSelect,
  onToggle,
  onBuffer,
  onPatchNode,
  onEndKindChange,
  onTargetKindChange,
  onTargetUnitChange,
  onTargetModeChange,
  onMove,
  onRemove,
  onAddRoot,
  onAddChild,
  onDissolve,
  onUndo,
  onAddOpen,
  registerHead,
  dirty,
  saving,
  canSave,
  saveLocked,
  saveMessage,
  saveError,
  conflict,
  remoteOpen,
  online,
  deleteOpen,
  deleting,
  deleteError,
  onDeleteOpen,
  onDeleteCancel,
  onConfirmDelete,
  recovery,
  onRestoreRecovery,
  onDiscardRecovery,
  onFocusIssue,
  onSave,
  onViewRemote,
  onReturnToDraft,
  onAdoptRemote,
}: {
  data: PlanDetail;
  editing: boolean;
  isNew: boolean;
  planName: string;
  planDate: string;
  onPlanName: (value: string) => void;
  onPlanDate: (value: string) => void;
  nodes: PlanNode[];
  buffers: DraftFieldBuffers;
  endKinds: Record<string, "time" | "distance">;
  targetEditors: Record<string, TargetEditor>;
  inputLocked: boolean;
  undo: UndoSnapshot | null;
  addOpen: boolean;
  projection: PlanDraftProjection | null;
  selected: string | null;
  expanded: string | null;
  draftError: string | null;
  onEdit: () => void;
  onDiscard: () => void;
  onSelect: (nodeId: string) => void;
  onToggle: (nodeId: string) => void;
  onBuffer: (
    nodeId: string,
    fieldPath: string,
    kind: DraftFieldKind,
    raw: string,
    options?: { targetKind?: TargetEditorKind; unit?: TargetEditorUnit },
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
  onAddRoot: (kind: "step" | "repeat") => void;
  onAddChild: (groupId: string) => void;
  onDissolve: (groupId: string) => void;
  onUndo: () => void;
  onAddOpen: (open: boolean) => void;
  registerHead: (nodeId: string, element: HTMLButtonElement | null) => void;
  dirty: boolean;
  saving: boolean;
  canSave: boolean;
  saveLocked: boolean;
  saveMessage: string | null;
  saveError: string | null;
  conflict: PlannerConflict | null;
  remoteOpen: boolean;
  online: boolean;
  deleteOpen: boolean;
  deleting: boolean;
  deleteError: string | null;
  onDeleteOpen: () => void;
  onDeleteCancel: () => void;
  onConfirmDelete: () => void;
  recovery: StoredPlannerDraft | null;
  onRestoreRecovery: () => void;
  onDiscardRecovery: () => void;
  onFocusIssue: (nodeId: string | null, fieldPath: string | null) => void;
  onSave: () => void;
  onViewRemote: () => void;
  onReturnToDraft: () => void;
  onAdoptRemote: () => void;
}) {
  const date = fmtDateLong(planDate || data.date);
  const repetitions = data.graph.repetition_groups.reduce(
    (sum, group) => sum + group.repetitions,
    0,
  );
  const targetCount = data.graph.tracks.filter((track) => track.kind !== "none").length;
  const incompleteCount = projection
    ? projection.draft.issues.filter((issue) => issue.code === "open_end").length
    : 0;
  const fieldErrors = projection
    ? Object.entries(projection.draft.field_states)
        .filter(([, state]) => state.validity !== "valid")
        .map(([key, state]) => {
          const split = key.lastIndexOf(":");
          const nodeId = key.slice(0, split);
          const fieldPath = key.slice(split + 1);
          const node = nodeById(nodes, nodeId);
          return {
            key,
            nodeId,
            fieldPath,
            title: node ? nodeTitle(node) : "Abschnitt",
            message: state.message || "Feld unvollständig.",
          };
        })
    : [];
  const structuralErrors = projection
    ? projection.draft.issues
        .filter(
          (issue) =>
            !["incomplete_field", "invalid_field"].includes(issue.code) &&
            issue.code !== "open_end",
        )
        .map((issue, index) => ({
          key: `issue-${issue.code}-${issue.node_id ?? index}`,
          nodeId: issue.node_id,
          fieldPath:
            issue.code === "empty_repeat"
              ? "repetitions"
              : issue.code === "no_executed_steps"
                ? "end.value"
                : issue.field,
          title: issue.node_id
            ? nodeTitle(nodeById(nodes, issue.node_id) ?? {
                kind: "step",
                node_id: issue.node_id,
                name: "",
              })
            : "Aufbau",
          message: issue.message,
        }))
    : [];
  const errorEntries = [...fieldErrors, ...structuralErrors];

  return (
    <>
      <h1 className="sheet-title">{planName || data.sport_label}</h1>
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
        {editing && <span className="plan-draft-badge">Entwurf lokal</span>}
      </div>

      {recovery && !editing && (
        <section
          className="plan-recovery"
          aria-labelledby="plan-recovery-title"
          aria-describedby="plan-recovery-text"
        >
          <h2 id="plan-recovery-title">Lokaler Entwurf gefunden</h2>
          <p id="plan-recovery-text">
            Für diese Einheit liegt ein nicht gespeicherter Entwurf vom{" "}
            {new Date(recovery.saved_at).toLocaleString("de-AT")}. Es wird nichts
            automatisch übernommen oder geschrieben.
          </p>
          {recovery.name !== data.name || recovery.date !== data.date ? (
            <p className="plan-recovery__diff">
              Gespeicherter Stand: {data.name || "ohne Namen"} ·{" "}
              {fmtDateLong(data.date)}. Entwurf: {recovery.name || "ohne Namen"} ·{" "}
              {fmtDateLong(recovery.date)}.
            </p>
          ) : null}
          <div className="plan-recovery__actions">
            <button type="button" className="btn btn--primary" onClick={onRestoreRecovery}>
              Entwurf wiederherstellen
            </button>
            <button type="button" className="btn btn--ghost" onClick={onDiscardRecovery}>
              Aktuellen Stand verwenden
            </button>
          </div>
        </section>
      )}

      {!editing &&
        !recovery &&
        (data.rights.can_edit_structure || data.rights.can_edit_metadata) && (
          <div className="plan-editbar">
            <button type="button" className="btn btn--primary" onClick={onEdit}>
              {data.rights.can_edit_structure
                ? "Bearbeiten"
                : "Name & Termin bearbeiten"}
            </button>
            <span className="plan-note plan-note--muted">
              {data.rights.can_edit_structure
                ? "Öffnet den lokalen Entwurf. Es wird nichts gespeichert."
                : "Der Aufbau bleibt unverändert; nur Name und Termin sind bearbeitbar."}
            </span>
          </div>
        )}

      <div className="plan-hero">
        <div>
          <strong>{data.known.text}</strong>
          {data.known.has_unknown && (
            <span className="plan-hero__hint">
              Offene Abschnitte sind nicht in der Summe enthalten.
            </span>
          )}
        </div>
        <span className="plan-hero__side">
          {repetitions > 0
            ? `${repetitions} ${repetitions === 1 ? "Wiederholung" : "Wiederholungen"}`
            : `${data.known.executions} ${data.known.executions === 1 ? "Abschnitt" : "Abschnitte"}`}
          {targetCount > 1 ? ` · ${targetCount} Zielarten` : ""}
        </span>
      </div>

      {draftError && (
        <p className="plan-draft-error" role="alert">
          {draftError}
        </p>
      )}

      {incompleteCount > 0 && (
        <p className="plan-incomplete-note" role="status">
          {incompleteCount === 1
            ? "Ein Abschnitt hat noch kein gültiges Ende."
            : `${incompleteCount} Abschnitte haben noch kein gültiges Ende.`}{" "}
          Die Summe zeigt nur den bekannten Teil.
        </p>
      )}

      {editing && errorEntries.length > 0 && (
        <section className="plan-errors" aria-labelledby="plan-errors-title">
          <h2 id="plan-errors-title">
            {errorEntries.length === 1
              ? "Eine Eingabe braucht Aufmerksamkeit"
              : `${errorEntries.length} Eingaben brauchen Aufmerksamkeit`}
          </h2>
          <p className="plan-errors__hint">
            Öffnet den betroffenen Block und setzt den Fokus auf das erste
            relevante Feld. Speichern bleibt bis zur Korrektur gesperrt.
          </p>
          <ol className="plan-errors__list">
            {errorEntries.map((entry) => (
              <li key={entry.key}>
                <button
                  type="button"
                  className="plan-errors__item"
                  onClick={() => onFocusIssue(entry.nodeId, entry.fieldPath)}
                >
                  <strong>{entry.title}</strong>
                  <span>{entry.message}</span>
                </button>
              </li>
            ))}
          </ol>
        </section>
      )}

      <WorkoutProfile graph={data.graph} selected={selected} onSelect={onSelect} />

      <section className="sheet-sec plan-structure" aria-label="Aufbau der Planung">
        <h2>Aufbau</h2>
        {nodes.length === 0 && (
          <p className="plan-note">
            {editing
              ? "Der Aufbau ist leer. Du kannst einen Einzelabschnitt oder einen Wiederholungsblock hinzufügen; Speichern bleibt gesperrt."
              : "Für diese Planung liegt kein Aufbau vor."}
          </p>
        )}
        {undo && (
          <div className="plan-undo" role="status">
            <span>{undo.message}</span>
            <button
              type="button"
              className="btn btn--ghost"
              disabled={inputLocked}
              onClick={onUndo}
            >
              Rückgängig
            </button>
          </div>
        )}
        {editing && !data.rights.can_edit_structure && (
          <p className="plan-note plan-note--muted">
            Der Aufbau ist bei dieser Planung nur lesbar. Nicht abbildbare
            Inhalte bleiben unverändert; bearbeitbar sind Name und Termin.
          </p>
        )}
        {editing && data.rights.can_edit_structure ? (
          <fieldset className="plan-lock" disabled={inputLocked}>
            <PlanEditor
              detail={data}
              projection={projection}
              nodes={nodes}
              buffers={buffers}
              endKinds={endKinds}
              targetEditors={targetEditors}
              selectedNodeId={selected}
              expandedNodeId={expanded}
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
          </fieldset>
        ) : (
          <PlanNodeList nodes={nodes} selected={selected} onSelect={onSelect} />
        )}
        {editing && data.rights.can_edit_structure && (
          <div className="plan-add">
            {!addOpen ? (
              <button
                type="button"
                id="plan-add-trigger"
                className="plan-add__trigger"
                aria-expanded={false}
                disabled={inputLocked}
                onClick={() => onAddOpen(true)}
              >
                <span aria-hidden="true">+</span> Baustein hinzufügen
              </button>
            ) : (
              <div className="plan-add__choices" role="group" aria-label="Baustein hinzufügen">
                <button
                  type="button"
                  className="plan-add__choice"
                  disabled={inputLocked}
                  onClick={() => onAddRoot("step")}
                >
                  <strong>Einzelabschnitt</strong>
                  <span>Ein eigener Schritt am Ende des Aufbaus.</span>
                </button>
                <button
                  type="button"
                  className="plan-add__choice"
                  disabled={inputLocked}
                  onClick={() => onAddRoot("repeat")}
                >
                  <strong>Wiederholungsblock</strong>
                  <span>Mehrere Schritte mit einer gemeinsamen Wiederholungszahl.</span>
                </button>
                <button
                  type="button"
                  className="plan-add__cancel"
                  disabled={inputLocked}
                  onClick={() => onAddOpen(false)}
                >
                  Abbrechen
                </button>
              </div>
            )}
          </div>
        )}
      </section>

      <details className="plan-meta" open={editing || isNew || undefined}>
        <summary>Name &amp; Termin</summary>
        <div className="plan-meta__body">
          {editing ? (
            <>
              <div className="plan-field-row">
                <div className="plan-field">
                  <label htmlFor="plan-meta-name">Name</label>
                  <input
                    id="plan-meta-name"
                    className="plan-input"
                    type="text"
                    value={planName}
                    disabled={inputLocked}
                    placeholder="Name der Einheit"
                    onChange={(event) => onPlanName(event.target.value)}
                  />
                </div>
                <div className="plan-field">
                  <label htmlFor="plan-meta-date">Termin</label>
                  <input
                    id="plan-meta-date"
                    className="plan-input"
                    type="date"
                    value={planDate}
                    disabled={inputLocked}
                    onChange={(event) => {
                      if (event.target.value) onPlanDate(event.target.value);
                    }}
                  />
                </div>
              </div>
              <p className="plan-meta__readonly">
                Sportart: {data.sport_label}. Ein Sportartwechsel bestehender
                Einheiten bleibt bewusst gesperrt.
              </p>
            </>
          ) : (
            <p className="plan-meta__static">
              <span>{planName || data.sport_label}</span>
              <span>{fmtDateLong(data.date)}</span>
              <span>{data.sport_label}</span>
            </p>
          )}
        </div>
      </details>

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
          {editing
            ? "Lokaler Entwurf."
            : "Leseansicht."}{" "}
          {data.rights.reason ?? "Die Quelle meldet keine Einschränkung."}
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

      {!editing && !isNew && (
        <section className="plan-delete" aria-labelledby="plan-delete-title">
          {!deleteOpen ? (
            <>
              <div className="plan-delete__row">
                <div>
                  <h2 id="plan-delete-title">Einheit löschen</h2>
                  <p>
                    Entfernt die Planung aus dem Trainingskalender und aus
                    intervals.icu. Eine aufgezeichnete Einheit bleibt erhalten.
                  </p>
                </div>
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={onDeleteOpen}
                  disabled={!online}
                >
                  Löschen
                </button>
              </div>
              {!online && (
                <p className="plan-delete__hint" role="status">
                  Offline – Löschen ist erst wieder mit Verbindung möglich.
                </p>
              )}
            </>
          ) : (
            <>
              <h2 id="plan-delete-title">Einheit endgültig löschen?</h2>
              <p>
                „{planName || data.sport_label}“ am {date} wird aus dem
                Trainingskalender entfernt. Ist die Einheit in intervals.icu
                noch vorhanden, wird sie dort ebenfalls gelöscht. Das lässt
                sich nicht rückgängig machen.
              </p>
              {!online && (
                <p className="plan-delete__hint" role="status">
                  Offline – die Einheit wurde nicht gelöscht.
                </p>
              )}
              {deleteError && (
                <p className="plan-delete__error" role="alert">
                  {deleteError}
                </p>
              )}
              <div className="plan-delete__actions">
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={onDeleteCancel}
                  disabled={deleting}
                >
                  Abbrechen
                </button>
                <button
                  type="button"
                  className="btn plan-delete__confirm"
                  onClick={onConfirmDelete}
                  disabled={deleting || !online}
                >
                  {deleting ? "Wird gelöscht…" : "Endgültig löschen"}
                </button>
              </div>
            </>
          )}
        </section>
      )}

      {editing && conflict && (
        <section className="plan-conflict" aria-label="Remote-Konflikt">
          <h2>Remote wurde zwischenzeitlich geändert</h2>
          <p>{conflict.reason}</p>
          <p className="plan-conflict__fields">
            Betroffen: {conflict.changed_fields.join(", ") || "unbekannt"}
          </p>
          {conflict.remote ? (
            <div className="plan-conflict__versions">
              <div>
                <span>Eigener Entwurf</span>
                <strong>{conflict.baseline?.name || planName || "Ohne Namen"}</strong>
                <span>{conflict.baseline?.date ?? planDate}</span>
              </div>
              <div>
                <span>Remote</span>
                <strong>{conflict.remote.name || "Ohne Namen"}</strong>
                <span>{conflict.remote.date}</span>
              </div>
            </div>
          ) : (
            <p className="plan-conflict__deleted">
              Die Einheit existiert remote nicht mehr. Sie wird nicht automatisch
              neu angelegt.
            </p>
          )}
          {remoteOpen && conflict.remote && (
            <div className="plan-conflict__remote" role="region" aria-label="Remoteversion">
              <p>
                {conflict.remote.sport} · {conflict.remote.date}
                {conflict.remote.local_time ? ` · ${conflict.remote.local_time}` : ""}
              </p>
              <p>{conflict.remote.nodes.length} Abschnitte in der Remote-Fassung.</p>
            </div>
          )}
          <div className="plan-conflict__actions">
            {conflict.remote && (
              <button type="button" className="btn btn--ghost" onClick={onViewRemote}>
                Remote ansehen
              </button>
            )}
            <button type="button" className="btn btn--ghost" onClick={onReturnToDraft}>
              Zum Entwurf
            </button>
            <button type="button" className="btn btn--ghost" onClick={onAdoptRemote}>
              {conflict.remote && !isNew
                ? "Entwurf verwerfen, Remote übernehmen"
                : "Entwurf verwerfen und schließen"}
            </button>
          </div>
        </section>
      )}

      {editing && (
        <DraftStatus
          projection={projection}
          buffers={buffers}
          dirty={dirty}
          nodes={nodes}
          onDiscard={onDiscard}
          saving={saving}
          canSave={canSave}
          saveLocked={saveLocked}
          saveMessage={saveMessage}
          saveError={saveError}
          onSave={onSave}
        />
      )}

      <p className="sheet-src">
        Plan aus {data.source.name}
        {data.source.remote_id ? ` · Event ${data.source.remote_id}` : ""} ·{" "}
        {editing ? "lokaler Entwurf, nicht gespeichert" : "nur lesend"}
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
