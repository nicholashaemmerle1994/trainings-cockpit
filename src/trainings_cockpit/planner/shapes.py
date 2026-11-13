"""Gemeinsame fachliche Vergleichsprojektion eines geplanten Workouts.

Die Projektion enthält nur Inhalte, die der Editor tatsächlich beeinflusst:
Name, Sport, Termin, Uhrzeit, Notizen und den Aufbau. Abgeleitete Remote-
Felder, Abrufzeitpunkte, interne Knoten-IDs und lokale Plan-IDs bleiben
draußen. Konfliktvergleich und Rundlaufprüfung verwenden damit dieselbe
Normalisierung; es gibt keine zweite Baumvergleichslogik.
"""

from __future__ import annotations

from typing import Any

from .model import (
    DistanceEnd,
    NoTarget,
    PaceTarget,
    PlannedWorkout,
    PowerTarget,
    RepeatNode,
    StepNode,
    StepRole,
    TimeEnd,
    UnsupportedNode,
    Value,
    WorkoutNode,
    ZoneTarget,
    repeat_group_name,
    role_from_name,
)


def _num(value: float) -> float:
    return round(float(value), 6)


def _target_shape(target: Any) -> tuple[Any, ...]:
    if isinstance(target, NoTarget):
        return ("none",)
    if isinstance(target, ZoneTarget):
        return ("zone", target.metric.value, target.zone_id)
    if isinstance(target, PowerTarget):
        values = target.values
        if isinstance(values, Value):
            return ("power", target.unit.value, "value", _num(values.value))
        return ("power", target.unit.value, "range", _num(values.min), _num(values.max))
    if isinstance(target, PaceTarget):
        values = target.values
        if isinstance(values, Value):
            return ("pace", target.unit.value, "value", _num(values.value))
        return ("pace", target.unit.value, "range", _num(values.min), _num(values.max))
    # Absolute bpm und andere nicht serialisierbare Ziele sind kein
    # bestätigter Schreibfall; der Vergleich meldet sie ausdrücklich.
    return ("unsupported", type(target).__name__)


def _node_shape(node: WorkoutNode) -> tuple[Any, ...]:
    if isinstance(node, UnsupportedNode):
        return ("unsupported", node.source_ref)
    if isinstance(node, StepNode):
        end = node.end
        if isinstance(end, TimeEnd):
            end_shape = ("time", _num(end.seconds))
        elif isinstance(end, DistanceEnd):
            end_shape = ("distance", _num(end.metres))
        else:
            end_shape = ("open",)
        role = node.role
        if role is StepRole.STEADY:
            role = role_from_name(node.name)
        return (
            "step",
            node.name,
            role.value,
            end_shape,
            _target_shape(node.target),
            node.notes,
        )
    if isinstance(node, RepeatNode):
        return (
            "repeat",
            repeat_group_name(node.name),
            node.repetitions,
            node.skip_final_recovery,
            tuple(_node_shape(child) for child in node.children),
        )
    raise TypeError(f"Unbekannter Knoten: {type(node).__name__}")


def plan_shape(plan: PlannedWorkout) -> dict[str, Any]:
    """Vergleichsprojektion ohne Renderzustand, lokale IDs oder Abrufzeiten."""
    return {
        "name": plan.name,
        "sport": plan.sport,
        "date": plan.date,
        "local_time": plan.local_time,
        "notes": plan.notes,
        "nodes": tuple(_node_shape(node) for node in plan.nodes),
    }


def node_shape(node: WorkoutNode) -> tuple[Any, ...]:
    """Einzelner Knoten in derselben Normalisierung wie :func:`plan_shape`."""
    return _node_shape(node)


__all__ = ["node_shape", "plan_shape"]
