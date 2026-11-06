"""Lesende Detailprojektion einer Planung.

Die Detailansicht öffnet ein Event über seine vorhandene Event-Identität. Sie
liest den bereits gespeicherten Rohinhalt mit dem P04-Adapter, zeigt
Berechtigungen und Notizen und erzeugt den Trainingsverlauf aus derselben
Ausführungsfolge wie Summen und spätere Bearbeitung.

Hier gibt es keinen Schreibpfad: Öffnen, Auswählen und Darstellen verändern
weder Event noch Entwurf.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from .identities import PlanId, PlanReference
from .model import (
    DistanceEnd,
    Editability,
    HeartRateTarget,
    NoTarget,
    PaceTarget,
    PlannedWorkout,
    PowerTarget,
    RepeatNode,
    StepNode,
    TimeEnd,
    UnsupportedNode,
    WorkoutNode,
    ZoneTarget,
)
from .remote import read_remote_event
from .validation import (
    calculate_known_totals,
    format_distance,
    format_duration,
    format_target,
    format_totals,
)

_RIGHTS = {
    Editability.FULL: "Quelle erlaubt Bearbeitung",
    Editability.METADATA_ONLY: "Quelle erlaubt Metadaten",
    Editability.READ_ONLY: "Nur lesbar",
}


def _event_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    import json

    raw: Any = row.get("raw")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            parsed = {}
    elif isinstance(raw, Mapping):
        parsed = dict(raw)
    else:
        parsed = {}
    event = dict(parsed) if isinstance(parsed, dict) else {}
    event.setdefault("id", row.get("id"))
    event.setdefault("start_date_local", row.get("date"))
    event.setdefault("type", row.get("sport"))
    event.setdefault("category", row.get("category") or "WORKOUT")
    event.setdefault("name", row.get("name"))
    event.setdefault("moving_time", row.get("duration_s"))
    event.setdefault("duration_s", row.get("duration_s"))
    event.setdefault("distance", row.get("distance_m"))
    event.setdefault("distance_m", row.get("distance_m"))
    event.setdefault("icu_training_load", row.get("load"))
    event.setdefault("icu_intensity", row.get("intensity"))
    return event


def _end_data(node: StepNode) -> dict[str, Any]:
    if isinstance(node.end, TimeEnd):
        return {
            "kind": "time",
            "seconds": node.end.seconds,
            "text": format_duration(node.end.seconds),
        }
    assert isinstance(node.end, DistanceEnd)
    return {
        "kind": "distance",
        "metres": node.end.metres,
        "text": format_distance(node.end.metres),
    }


def _target_data(target: Any) -> dict[str, Any]:
    if isinstance(target, NoTarget):
        return {"kind": "none", "text": "Ohne Ziel"}
    if isinstance(target, ZoneTarget):
        return {
            "kind": "zone",
            "metric": target.metric.value,
            "zone_id": target.zone_id,
            "zone_set_id": target.zone_set_id,
            "text": format_target(target),
        }
    if isinstance(target, HeartRateTarget):
        return {
            "kind": "heartRate",
            "unit": "bpm",
            "values": _values_data(target.values),
            "text": format_target(target),
        }
    if isinstance(target, PowerTarget):
        return {
            "kind": "power",
            "unit": target.unit.value,
            "values": _values_data(target.values),
            "text": format_target(target),
        }
    if isinstance(target, PaceTarget):
        return {
            "kind": "pace",
            "unit": target.unit.value,
            "values": _values_data(target.values),
            "text": format_target(target),
        }
    return {"kind": "none", "text": format_target(target)}


def _values_data(values: Any) -> dict[str, Any]:
    from .model import Value

    if isinstance(values, Value):
        return {"kind": "value", "value": values.value}
    return {"kind": "range", "min": values.min, "max": values.max}


def _node_data(node: WorkoutNode) -> dict[str, Any]:
    if isinstance(node, StepNode):
        return {
            "kind": "step",
            "node_id": str(node.id),
            "name": node.name,
            "role": node.role.value,
            "end": _end_data(node),
            "target": _target_data(node.target),
            "notes": node.notes,
            "source_ref": node.source_ref,
        }
    if isinstance(node, RepeatNode):
        return {
            "kind": "repeat",
            "node_id": str(node.id),
            "name": node.name,
            "repetitions": node.repetitions,
            "skip_final_recovery": node.skip_final_recovery,
            "children": [_node_data(child) for child in node.children],
            "source_ref": node.source_ref,
        }
    assert isinstance(node, UnsupportedNode)
    return {
        "kind": "unsupported",
        "node_id": str(node.id),
        "label": node.label,
        "reason": node.reason,
        "source_ref": node.source_ref,
    }


def _rights(plan: PlannedWorkout) -> dict[str, Any]:
    return {
        "editability": plan.editability.value,
        "label": _RIGHTS[plan.editability],
        "reason": plan.editability_reason,
        "restriction_codes": [code.value for code in plan.restriction_codes],
        "can_edit_structure": plan.is_structure_editable,
        "can_edit_metadata": plan.is_metadata_editable,
        "can_write": plan.is_metadata_editable,
        "writes_on_open": False,
    }


def _known_summary(plan: PlannedWorkout) -> dict[str, Any]:
    totals = calculate_known_totals(plan)
    return {
        "seconds": totals.duration_seconds,
        "metres": totals.distance_metres,
        "executions": totals.executions,
        "has_unknown": totals.has_unknown,
        "first_end": totals.first_end,
        "duration_text": (
            format_duration(totals.duration_seconds) if totals.duration_seconds else None
        ),
        "distance_text": (
            format_distance(totals.distance_metres) if totals.distance_metres else None
        ),
        "text": format_totals(totals),
    }


def _notes(plan: PlannedWorkout, event: Mapping[str, Any]) -> str | None:
    for value in (
        plan.notes,
        event.get("notes"),
        event.get("description"),
        (event.get("workout_doc") or {}).get("notes")
        if isinstance(event.get("workout_doc"), Mapping)
        else None,
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def build_plan_detail(
    row: Mapping[str, Any],
    *,
    time_zone: str,
    account_id: str = "default",
    athlete_id: str = "default",
    now: str | None = None,
) -> dict[str, Any]:
    """Eine planungsseitige Detailantwort ohne Schreibzugriff."""
    event = _event_from_row(row)
    fetched_at = now or datetime.now().astimezone().isoformat(timespec="seconds")
    remote = read_remote_event(
        event,
        fetched_at=fetched_at,
        time_zone=time_zone,
        account_id=account_id,
        athlete_id=athlete_id,
    )
    plan = remote.plan
    reference = PlanReference(
        PlanId(plan.local_id),
        account_id,
        athlete_id,
    )
    return {
        "kind": "planned",
        "id": int(row["id"]),
        "remote_id": str(plan.remote_id) if plan.remote_id is not None else None,
        "local_id": str(plan.local_id),
        "reference": reference.key,
        "name": plan.name,
        "sport": plan.sport,
        "sport_label": _sport_label(plan.sport),
        "date": plan.date,
        "time": plan.local_time,
        "time_zone": plan.time_zone,
        "notes": _notes(plan, event),
        "rights": _rights(plan),
        "known": _known_summary(plan),
        "nodes": [_node_data(node) for node in plan.nodes],
        "source": {
            "name": "intervals.icu",
            "remote_id": str(plan.remote_id) if plan.remote_id is not None else None,
            "read_only": True,
        },
        "fetched_at": fetched_at,
    }


def _sport_label(sport: str | None) -> str:
    from ..plan import SPORT_LABELS

    return SPORT_LABELS.get(sport or "", sport or "Andere Sportart")


__all__ = ["build_plan_detail"]
