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
    OpenEnd,
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
from .profile import build_workout_profile_data, heart_rate_zone_options
from .remote import read_remote_event
from .validation import (
    calculate_known_totals,
    format_distance,
    format_duration,
    format_target_label,
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
    if isinstance(node.end, DistanceEnd):
        return {
            "kind": "distance",
            "metres": node.end.metres,
            "text": format_distance(node.end.metres),
        }
    assert isinstance(node.end, OpenEnd)
    return {"kind": "open", "text": "Ende offen"}


def _target_data(target: Any) -> dict[str, Any]:
    if isinstance(target, NoTarget):
        return {"kind": "none", "text": "Ohne Ziel"}
    if isinstance(target, ZoneTarget):
        return {
            "kind": "zone",
            "metric": target.metric.value,
            "zone_id": target.zone_id,
            "zone_set_id": target.zone_set_id,
            "text": format_target_label(target),
        }
    if isinstance(target, HeartRateTarget):
        return {
            "kind": "heartRate",
            "unit": "bpm",
            "values": _values_data(target.values),
            "text": format_target_label(target),
        }
    if isinstance(target, PowerTarget):
        return {
            "kind": "power",
            "unit": target.unit.value,
            "values": _values_data(target.values),
            "text": format_target_label(target),
        }
    if isinstance(target, PaceTarget):
        return {
            "kind": "pace",
            "unit": target.unit.value,
            "values": _values_data(target.values),
            "text": format_target_label(target),
        }
    return {"kind": "none", "text": format_target_label(target)}


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


def _source_data(source: Any | None) -> dict[str, Any] | None:
    if source is None:
        return None
    return {
        "remote_id": str(source.remote_id),
        "fetched_at": source.fetched_at,
        "relevant_content_hash": source.relevant_content_hash,
        "remote_updated_at": source.remote_updated_at,
        "remote_version": source.remote_version,
        "raw_workout_text": source.raw_workout_text,
    }


def _capabilities(plan: PlannedWorkout) -> dict[str, Any]:
    """Lokale Modellfähigkeit und belegter Remote-Schreibweg getrennt.

    P12/P13 dürfen HF-Zonen, Pace und Leistung lokal bearbeiten. Absolute bpm
    und Leistungszonen bleiben hinter der Fähigkeitsmatrix gesperrt; die
    Remote-Schreibfähigkeit ist davon getrennt.
    """
    editable = plan.is_structure_editable
    return {
        "write": {
            "available": plan.is_metadata_editable,
            "reason": (
                plan.editability_reason
                or "Planung ist über den vorhandenen Update-Pfad speicherbar."
            ),
        },
        "targets": {
            "heartRateZone": {
                "local": True,
                "editable": editable,
                "synchronizable": False,
                "reason": "Schreibbeleg für Zonenreferenzen folgt mit dem Serializer.",
            },
            "heartRateBpm": {
                "local": True,
                "editable": False,
                "synchronizable": False,
                "gate": "absolute_hr",
                "reason": "Kein belegter Schreibvertrag für absolute bpm-Werte.",
            },
            "pace": {
                "local": True,
                "editable": editable,
                "synchronizable": False,
                "reason": "Lokaler Entwurf; der Serializer-Rundlauf folgt in P17.",
            },
            "powerWatts": {
                "local": True,
                "editable": editable,
                "synchronizable": False,
                "reason": "Lokaler Entwurf; der Serializer-Rundlauf folgt in P17.",
            },
            "powerPercentFtp": {
                "local": True,
                "editable": editable,
                "synchronizable": False,
                "reason": "Relative Semantik bleibt lokal erhalten; Schreibbeleg folgt.",
            },
            "powerZone": {
                "local": False,
                "editable": False,
                "synchronizable": False,
                "gate": "power_zone",
                "reason": (
                    "Leistungszonen sind laut Fähigkeitsmatrix weder gelesen "
                    "noch geschrieben belegt."
                ),
            },
            "none": {
                "local": True,
                "editable": editable,
                "synchronizable": False,
            },
        },
    }


def _plan_payload(
    plan: PlannedWorkout,
    source: Any | None,
    event: Mapping[str, Any],
    row: Mapping[str, Any] | None,
    *,
    zone_profiles: Mapping[str, Any] | None,
    account_id: str = "default",
    athlete_id: str = "default",
    fetched_at: str | None = None,
) -> dict[str, Any]:
    graph = build_workout_profile_data(
        plan,
        zone_profiles=zone_profiles,
        max_executions=160,
    )
    reference = PlanReference(
        PlanId(plan.local_id),
        account_id,
        athlete_id,
    )
    remote_id = str(plan.remote_id) if plan.remote_id is not None else None
    return {
        "kind": "planned",
        "id": int(row["id"]) if row is not None else None,
        "remote_id": remote_id,
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
        "graph": graph,
        "zone_options": heart_rate_zone_options(plan.sport, zone_profiles),
        "capabilities": _capabilities(plan),
        "source_snapshot": _source_data(source),
        "source": {
            "name": "intervals.icu" if source is not None else "Lokaler Entwurf",
            "remote_id": remote_id,
            "read_only": source is not None,
        },
        "fetched_at": fetched_at or (source.fetched_at if source is not None else None),
    }


def build_plan_payload(
    plan: PlannedWorkout,
    source: Any,
    event: Mapping[str, Any],
    row: Mapping[str, Any],
    *,
    zone_profiles: Mapping[str, Any] | None = None,
    account_id: str = "default",
    athlete_id: str = "default",
) -> dict[str, Any]:
    """Gemeinsame Darstellung für Leseansicht und lokalen Entwurf."""
    return _plan_payload(
        plan,
        source,
        event,
        row,
        zone_profiles=zone_profiles,
        account_id=account_id,
        athlete_id=athlete_id,
    )


def build_local_plan_payload(
    plan: PlannedWorkout,
    *,
    fetched_at: str,
    time_zone: str | None = None,
    zone_profiles: Mapping[str, Any] | None = None,
    account_id: str = "default",
    athlete_id: str = "default",
) -> dict[str, Any]:
    """Darstellung eines noch nicht gespeicherten lokalen Entwurfs.

    Es gibt bewusst keinen ``SourceSnapshot`` und keine Remote-ID. Der
    Aufrufer sieht damit klar, dass dieses Objekt nur lokal existiert.
    """
    del time_zone  # Die Zeitzone ist bereits kanonisch am Plan hinterlegt.
    return _plan_payload(
        plan,
        None,
        {},
        None,
        zone_profiles=zone_profiles,
        account_id=account_id,
        athlete_id=athlete_id,
        fetched_at=fetched_at,
    )


def build_plan_detail(
    row: Mapping[str, Any],
    *,
    time_zone: str,
    account_id: str = "default",
    athlete_id: str = "default",
    zone_profiles: Mapping[str, Any] | None = None,
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
    return build_plan_payload(
        remote.plan,
        remote.source,
        event,
        row,
        zone_profiles=zone_profiles,
        account_id=account_id,
        athlete_id=athlete_id,
    )


def _sport_label(sport: str | None) -> str:
    from ..plan import SPORT_LABELS

    return SPORT_LABELS.get(sport or "", sport or "Andere Sportart")


__all__ = ["build_local_plan_payload", "build_plan_detail", "build_plan_payload"]
