"""Gemeinsamer Klon-Dienst für Vorlagen und spätere Wochenkopien.

Der Dienst arbeitet ausschließlich auf dem fachlichen Planungsmodell. Er liest
keine Datenbank, ruft keinen Adapter und schreibt nichts. Jede Verwendung
erzeugt neue Knoten-, Plan-, Entwurfs- und Vorgangsidentitäten; Quellreferenzen
und Notizen werden nicht mitgenommen.

Die Serializer-Grenze :func:`prepare_write` entscheidet, ob der geklonte
Aufbau als neues Training sicher schreibbar wäre. Damit gelten für den Klon
genau dieselben Fähigkeitsgrenzen wie für eine Neuanlage.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from enum import StrEnum

from .identities import DraftId, NodeId, OperationId, PlanId
from .model import (
    Editability,
    HeartRateTarget,
    OpenEnd,
    PlannedWorkout,
    RepeatNode,
    StepNode,
    UnsupportedNode,
    WorkoutDraft,
    WorkoutNode,
    ZoneMetric,
    ZoneTarget,
    iter_nodes,
)
from .primitives import require_local_date, require_text, require_time_zone
from .serializer import prepare_write


class CloneCode(StrEnum):
    """Stabile Fehlercodes; unabhängig vom Wortlaut einer Meldung."""

    EMPTY_STRUCTURE = "empty_structure"
    NOTES = "notes"
    UNSUPPORTED_NODE = "unsupported_node"
    NESTED_REPEAT = "nested_repeat"
    SKIP_FINAL_RECOVERY = "skip_final_recovery"
    ABSOLUTE_HR = "absolute_hr"
    POWER_ZONE = "power_zone"
    OPEN_END = "open_end"
    EMPTY_REPEAT = "empty_repeat"
    INVALID_DATE = "invalid_date"
    INVALID_TIME_ZONE = "invalid_time_zone"
    INVALID_IDENTITY = "invalid_identity"
    SERIALIZATION_FAILED = "serialization_failed"


class CloneError(ValueError):
    """Ein Aufbau lässt sich nicht verlustfrei als neues Training klonen."""

    def __init__(self, code: CloneCode, reason: str) -> None:
        if not isinstance(code, CloneCode):
            raise TypeError("code muss ein CloneCode sein.")
        text = str(reason or "").strip()
        if not text:
            text = "Der Aufbau lässt sich nicht klonen."
        super().__init__(text)
        self.code = code
        self.reason = text


def _assert_cloneable(source: PlannedWorkout) -> None:
    """Prüft die bekannten, konkret benennbaren Ablehnungsgründe."""
    if not source.nodes:
        raise CloneError(
            CloneCode.EMPTY_STRUCTURE,
            "Der Aufbau enthält keine Wurzelbausteine.",
        )
    if source.notes:
        raise CloneError(
            CloneCode.NOTES,
            "Planungsnotizen lassen sich nicht verlustfrei in einen neuen Plan übernehmen.",
        )
    for node in iter_nodes(source.nodes):
        if isinstance(node, UnsupportedNode):
            raise CloneError(
                CloneCode.UNSUPPORTED_NODE,
                f"Unbekannter Inhalt {node.source_ref!r} kann nicht geklont werden.",
            )
        if isinstance(node, StepNode):
            if node.notes:
                raise CloneError(
                    CloneCode.NOTES,
                    "Schrittnotizen lassen sich nicht verlustfrei in einen neuen Plan übernehmen.",
                )
            if isinstance(node.end, OpenEnd):
                raise CloneError(
                    CloneCode.OPEN_END,
                    "Ein Abschnitt ohne gültiges Ende ist nicht speicherbar.",
                )
            if isinstance(node.target, HeartRateTarget):
                raise CloneError(
                    CloneCode.ABSOLUTE_HR,
                    "Absolute bpm-Werte haben keinen belegten Schreibvertrag.",
                )
            if (
                isinstance(node.target, ZoneTarget)
                and node.target.metric is ZoneMetric.POWER
            ):
                raise CloneError(
                    CloneCode.POWER_ZONE,
                    "Leistungszonen sind nicht als Schreibweg belegt.",
                )
        if isinstance(node, RepeatNode):
            if node.skip_final_recovery:
                raise CloneError(
                    CloneCode.SKIP_FINAL_RECOVERY,
                    "„Letzte Erholung auslassen“ ist nicht verlustfrei darstellbar.",
                )
            if not node.children:
                raise CloneError(
                    CloneCode.EMPTY_REPEAT,
                    "Eine Wiederholungsgruppe ohne Kinder führt nichts aus.",
                )
            if any(isinstance(child, RepeatNode) for child in node.children):
                raise CloneError(
                    CloneCode.NESTED_REPEAT,
                    "Verschachtelte Wiederholungen sind nicht unterstützt.",
                )


def _rekey_node(node: WorkoutNode) -> WorkoutNode:
    if isinstance(node, StepNode):
        return replace(
            node,
            id=NodeId.new(),
            notes=None,
            source_ref=None,
        )
    if isinstance(node, RepeatNode):
        return replace(
            node,
            id=NodeId.new(),
            children=tuple(_rekey_node(child) for child in node.children),
            source_ref=None,
        )
    raise CloneError(
        CloneCode.UNSUPPORTED_NODE,
        "Unbekannter Inhalt kann nicht geklont werden.",
    )


def rekey_nodes(nodes: Iterable[WorkoutNode]) -> tuple[WorkoutNode, ...]:
    """Kopiert Knoten mit neuen IDs, ohne Notizen oder Quellreferenzen."""
    return tuple(_rekey_node(node) for node in nodes)


def clone_for_new_plan(
    source: PlannedWorkout,
    *,
    target_date: object,
    time_zone: object,
    account_id: str,
    athlete_id: str,
    keep_time: bool = False,
    draft_id: str | None = None,
    local_id: str | None = None,
    operation_id: str | None = None,
) -> tuple[PlannedWorkout, WorkoutDraft]:
    """Bereitet einen unabhängigen neuen Plan samt lokalem Entwurf vor.

    Es gibt keinen DB- und keinen Netzwerkzugriff. Die Funktion liefert den
    neuen Plan und den Entwurf; der Aufrufer entscheidet, ob er daraus eine
    Vorlage speichert oder später über den bestehenden Save-Pfad schreibt.
    """
    if not isinstance(source, PlannedWorkout):
        raise TypeError("source muss ein PlannedWorkout sein.")
    if not isinstance(keep_time, bool):
        raise TypeError("keep_time muss ein Boolean sein.")

    try:
        day = require_local_date(target_date, "target_date")
    except ValueError as exc:
        raise CloneError(CloneCode.INVALID_DATE, str(exc)) from exc
    try:
        zone = require_time_zone(time_zone)
    except ValueError as exc:
        raise CloneError(CloneCode.INVALID_TIME_ZONE, str(exc)) from exc
    try:
        account = require_text(account_id, "account_id")
        athlete = require_text(athlete_id, "athlete_id")
    except ValueError as exc:
        raise CloneError(CloneCode.INVALID_IDENTITY, str(exc)) from exc

    _assert_cloneable(source)

    try:
        draft_identity = DraftId(draft_id) if draft_id is not None else DraftId.new()
        operation_identity = (
            OperationId(operation_id) if operation_id is not None else None
        )
        if local_id is not None:
            plan_identity = PlanId(local_id)
        elif draft_id is not None:
            plan_identity = PlanId(f"plan:{draft_identity.value}")
        else:
            plan_identity = PlanId.new()
    except ValueError as exc:
        raise CloneError(CloneCode.INVALID_IDENTITY, str(exc)) from exc

    plan = PlannedWorkout(
        local_id=plan_identity,
        remote_id=None,
        external_id=None,
        name=source.name,
        sport=source.sport,
        date=day,
        local_time=source.local_time if keep_time else None,
        time_zone=zone,
        nodes=rekey_nodes(source.nodes),
        notes=None,
        editability=Editability.FULL,
    )
    if operation_identity is None:
        draft = WorkoutDraft.new(plan, draft_id=draft_identity)
    else:
        draft = WorkoutDraft.new(
            plan,
            draft_id=draft_identity,
            operation_id=operation_identity,
        )

    try:
        prepare_write(draft, account_id=account, athlete_id=athlete)
    except (TypeError, ValueError) as exc:
        # Bewusst nur der stabile Code; die Meldung ist Erklärung, nicht Logik.
        raise CloneError(CloneCode.SERIALIZATION_FAILED, str(exc)) from exc
    return plan, draft


__all__ = [
    "CloneCode",
    "CloneError",
    "clone_for_new_plan",
    "rekey_nodes",
]
