"""Dauerhafte Vorgangszuordnung des Trainingsplaners.

Ein Write beginnt erst, wenn Identität, Snapshot und Account-/Athletenzuordnung
gespeichert sind. Die Persistenz hält außerdem die tatsächliche Remote-ID, die
stabile externe Identität und den Zustand zusammen. Nach einem Reload kann der
Vorgang lesend fortgesetzt werden, ohne einen zweiten Create auszulösen.

Die Editorform (``EditorShapeMetadata``) wird nur mitgesichert, wenn der
Aufrufer sie tatsächlich braucht. Sie bleibt bis zu einem bestätigten Rundlauf
``prepared`` und wird erst danach als ``confirmed`` veröffentlicht.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from .. import db
from .model import (
    DistanceEnd,
    Editability,
    HeartRateTarget,
    NoTarget,
    OpenEnd,
    PaceTarget,
    PaceUnit,
    PlannedWorkout,
    PowerTarget,
    PowerUnit,
    RepeatNode,
    RestrictionCode,
    StepNode,
    StepRole,
    TimeEnd,
    UnsupportedNode,
    Value,
    ValueRange,
    ZoneMetric,
    ZoneTarget,
)
from .save import SaveSnapshot, SaveState

#: Endgültig abgeschlossen; nur diese Zustände werden nach der
#: Aufbewahrungsfrist bereinigt.
TERMINAL_STATES = (
    SaveState.SAVED.value,
    SaveState.FAILED.value,
    SaveState.CONFLICT.value,
)

#: Offene Zustände, die einen Reload überleben und weiter abgeglichen werden.
OPEN_STATES = (
    SaveState.SAVING.value,
    SaveState.UNKNOWN.value,
    SaveState.SAVED_UNVERIFIED.value,
)

#: Kurze Aufbewahrung abgeschlossener Vorgänge. Offene Vorgänge bleiben
#: unabhängig vom Alter erhalten.
RETENTION_DAYS = 7


# ------------------------------------------------------------ Plan-JSON


def _value_to_json(value: Value | ValueRange) -> dict[str, Any]:
    if isinstance(value, Value):
        return {"kind": "value", "value": value.value}
    return {"kind": "range", "min": value.min, "max": value.max}


def _value_from_json(raw: Mapping[str, Any]) -> Value | ValueRange:
    kind = raw.get("kind")
    if kind == "value":
        return Value(raw["value"])
    if kind == "range":
        return ValueRange(raw["min"], raw["max"])
    raise ValueError(f"Unbekannte Wertart: {kind!r}")


def _target_to_json(target: Any) -> dict[str, Any]:
    if isinstance(target, NoTarget):
        return {"kind": "none"}
    if isinstance(target, ZoneTarget):
        return {
            "kind": "zone",
            "metric": target.metric.value,
            "zone_id": target.zone_id,
            "zone_set_id": target.zone_set_id,
        }
    if isinstance(target, HeartRateTarget):
        return {
            "kind": "heartRate",
            "unit": target.unit,
            "values": _value_to_json(target.values),
        }
    if isinstance(target, PowerTarget):
        return {
            "kind": "power",
            "unit": target.unit.value,
            "values": _value_to_json(target.values),
        }
    if isinstance(target, PaceTarget):
        return {
            "kind": "pace",
            "unit": target.unit.value,
            "values": _value_to_json(target.values),
        }
    raise TypeError(f"Unbekanntes Ziel: {type(target).__name__}")


def _target_from_json(raw: Mapping[str, Any]) -> Any:
    kind = raw.get("kind")
    if kind == "none":
        return NoTarget()
    if kind == "zone":
        return ZoneTarget(
            metric=ZoneMetric(raw["metric"]),
            zone_id=raw["zone_id"],
            zone_set_id=raw.get("zone_set_id"),
        )
    if kind == "heartRate":
        return HeartRateTarget(values=_value_from_json(raw["values"]), unit=raw.get("unit", "bpm"))
    if kind == "power":
        return PowerTarget(unit=PowerUnit(raw["unit"]), values=_value_from_json(raw["values"]))
    if kind == "pace":
        return PaceTarget(unit=PaceUnit(raw["unit"]), values=_value_from_json(raw["values"]))
    raise ValueError(f"Unbekanntes Ziel: {kind!r}")


def _end_to_json(end: Any) -> dict[str, Any]:
    if isinstance(end, TimeEnd):
        return {"kind": "time", "seconds": end.seconds}
    if isinstance(end, DistanceEnd):
        return {"kind": "distance", "metres": end.metres}
    if isinstance(end, OpenEnd):
        return {"kind": "open"}
    raise TypeError(f"Unbekanntes Ende: {type(end).__name__}")


def _end_from_json(raw: Mapping[str, Any]) -> Any:
    kind = raw.get("kind")
    if kind == "time":
        return TimeEnd(raw["seconds"])
    if kind == "distance":
        return DistanceEnd(raw["metres"])
    if kind == "open":
        return OpenEnd()
    raise ValueError(f"Unbekanntes Ende: {kind!r}")


def _node_to_json(node: Any) -> dict[str, Any]:
    if isinstance(node, StepNode):
        return {
            "kind": "step",
            "id": str(node.id),
            "name": node.name,
            "role": node.role.value,
            "end": _end_to_json(node.end),
            "target": _target_to_json(node.target),
            "notes": node.notes,
            "source_ref": node.source_ref,
        }
    if isinstance(node, RepeatNode):
        return {
            "kind": "repeat",
            "id": str(node.id),
            "name": node.name,
            "repetitions": node.repetitions,
            "children": [_node_to_json(child) for child in node.children],
            "skip_final_recovery": node.skip_final_recovery,
            "source_ref": node.source_ref,
        }
    if isinstance(node, UnsupportedNode):
        return {
            "kind": "unsupported",
            "id": str(node.id),
            "label": node.label,
            "reason": node.reason,
            "source_ref": node.source_ref,
        }
    raise TypeError(f"Unbekannter Knoten: {type(node).__name__}")


def _node_from_json(raw: Mapping[str, Any]) -> Any:
    kind = raw.get("kind")
    if kind == "step":
        return StepNode(
            id=raw["id"],
            name=raw.get("name", ""),
            end=_end_from_json(raw["end"]),
            role=StepRole(raw.get("role", "steady")),
            target=_target_from_json(raw["target"]),
            notes=raw.get("notes"),
            source_ref=raw.get("source_ref"),
        )
    if kind == "repeat":
        return RepeatNode(
            id=raw["id"],
            name=raw.get("name", ""),
            repetitions=raw["repetitions"],
            children=tuple(_node_from_json(child) for child in raw.get("children", [])),
            skip_final_recovery=raw.get("skip_final_recovery", False),
            source_ref=raw.get("source_ref"),
        )
    if kind == "unsupported":
        return UnsupportedNode(
            id=raw["id"],
            label=raw["label"],
            reason=raw["reason"],
            source_ref=raw["source_ref"],
        )
    raise ValueError(f"Unbekannter Knoten: {kind!r}")


def plan_to_json(plan: PlannedWorkout) -> dict[str, Any]:
    """Verlustfreie, JSON-nahe Form der gespeicherten Planung."""
    return {
        "local_id": str(plan.local_id),
        "remote_id": str(plan.remote_id) if plan.remote_id is not None else None,
        "external_id": plan.external_id,
        "name": plan.name,
        "sport": plan.sport,
        "date": plan.date,
        "local_time": plan.local_time,
        "time_zone": plan.time_zone,
        "notes": plan.notes,
        "editability": plan.editability.value,
        "editability_reason": plan.editability_reason,
        "restriction_codes": [code.value for code in plan.restriction_codes],
        "nodes": [_node_to_json(node) for node in plan.nodes],
    }


def plan_from_json(raw: Mapping[str, Any]) -> PlannedWorkout:
    """Rekonstruiert die Planung aus dem gesicherten Vorgang."""
    return PlannedWorkout(
        local_id=raw["local_id"],
        remote_id=raw.get("remote_id"),
        external_id=raw.get("external_id"),
        name=raw.get("name", ""),
        sport=raw["sport"],
        date=raw["date"],
        local_time=raw.get("local_time"),
        time_zone=raw["time_zone"],
        nodes=tuple(_node_from_json(node) for node in raw.get("nodes", [])),
        notes=raw.get("notes"),
        editability=Editability(raw.get("editability", "full")),
        editability_reason=raw.get("editability_reason"),
        restriction_codes=tuple(
            RestrictionCode(code) for code in raw.get("restriction_codes", [])
        ),
    )


def snapshot_to_json(snapshot: SaveSnapshot) -> dict[str, Any]:
    return {
        "operation_id": str(snapshot.operation_id),
        "draft_id": str(snapshot.draft_id),
        "local_id": str(snapshot.local_id),
        "remote_id": str(snapshot.remote_id) if snapshot.remote_id is not None else None,
        "account_id": snapshot.account_id,
        "athlete_id": snapshot.athlete_id,
        "mode": snapshot.mode,
        "kind": snapshot.kind,
        "payload_json": snapshot.payload_json,
        "workout_text": snapshot.workout_text,
        "external_id": snapshot.external_id,
        "base_hash": snapshot.base_hash,
        "local_revision": snapshot.local_revision,
        "writable": snapshot.writable,
        "writable_reason": snapshot.writable_reason,
        "intended": plan_to_json(snapshot.intended),
        "base": None if snapshot.base is None else plan_to_json(snapshot.base),
        "base_notes": snapshot.base_notes,
        "created_at": snapshot.created_at,
        "editor_shape": snapshot.editor_shape,
    }


def snapshot_from_json(raw: Mapping[str, Any]) -> SaveSnapshot:
    base = raw.get("base")
    return SaveSnapshot(
        operation_id=raw["operation_id"],
        draft_id=raw["draft_id"],
        local_id=raw["local_id"],
        remote_id=raw.get("remote_id"),
        account_id=raw["account_id"],
        athlete_id=raw["athlete_id"],
        mode=raw["mode"],
        kind=raw["kind"],
        payload_json=raw["payload_json"],
        workout_text=raw.get("workout_text"),
        external_id=raw.get("external_id"),
        base_hash=raw.get("base_hash"),
        local_revision=int(raw.get("local_revision", 0)),
        writable=bool(raw.get("writable", True)),
        writable_reason=raw.get("writable_reason"),
        intended=plan_from_json(raw["intended"]),
        base=None if base is None else plan_from_json(base),
        base_notes=raw.get("base_notes"),
        created_at=raw["created_at"],
        editor_shape=raw.get("editor_shape"),
    )


# ------------------------------------------------------------ Persistenz


@dataclass(frozen=True, slots=True)
class StoredOperation:
    snapshot: SaveSnapshot
    state: SaveState
    record: Mapping[str, Any]


class SqliteOperationStore:
    """Bestehende SQLite-Persistenz; kein zweiter Sync- oder Store-Dienst."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def save(self, snapshot: SaveSnapshot, state: SaveState) -> None:
        if not isinstance(snapshot, SaveSnapshot):
            raise TypeError("save akzeptiert nur einen SaveSnapshot.")
        db.upsert_planner_operation(
            self._conn,
            operation_id=str(snapshot.operation_id),
            account_id=snapshot.account_id,
            athlete_id=snapshot.athlete_id,
            local_id=str(snapshot.local_id),
            draft_id=str(snapshot.draft_id),
            remote_id=str(snapshot.remote_id) if snapshot.remote_id is not None else None,
            external_id=snapshot.external_id,
            mode=snapshot.mode,
            kind=snapshot.kind,
            state=SaveState(state).value,
            payload_json=snapshot.payload_json,
            snapshot_json=json.dumps(
                snapshot_to_json(snapshot), sort_keys=True, ensure_ascii=False
            ),
            editor_shape_json=(
                json.dumps(snapshot.editor_shape, sort_keys=True, ensure_ascii=False)
                if snapshot.editor_shape is not None
                else None
            ),
            editor_shape_state="prepared",
            created_at=snapshot.created_at,
        )

    def update(
        self,
        snapshot: SaveSnapshot,
        state: SaveState,
        *,
        confirmed: bool = False,
        remote_id: str | None = None,
        external_id: str | None = None,
    ) -> None:
        """Aktualisiert den Zustand; eine Editorform wird nur bestätigt publiziert."""
        state = SaveState(state)
        if remote_id is not None or external_id is not None:
            snapshot = replace(
                snapshot,
                remote_id=remote_id if remote_id is not None else snapshot.remote_id,
                external_id=(
                    external_id if external_id is not None else snapshot.external_id
                ),
            )
        self.save(snapshot, state)
        if confirmed and snapshot.editor_shape is not None:
            self._conn.execute(
                "UPDATE planner_operation SET editor_shape_state = 'confirmed', "
                "updated_at = ? WHERE operation_id = ?",
                (
                    datetime.now().isoformat(timespec="seconds"),
                    str(snapshot.operation_id),
                ),
            )
            self._conn.commit()

    def open_operations(self, *, account_id: str, athlete_id: str) -> list[StoredOperation]:
        rows = db.planner_operations(
            self._conn,
            account_id=account_id,
            athlete_id=athlete_id,
            states=OPEN_STATES,
        )
        result: list[StoredOperation] = []
        for row in rows:
            try:
                snapshot = snapshot_from_json(json.loads(row["snapshot_json"]))
            except (TypeError, ValueError, KeyError):
                continue
            result.append(StoredOperation(snapshot, SaveState(row["state"]), row))
        return result

    def record(self, operation_id: str) -> StoredOperation | None:
        row = db.planner_operation(self._conn, operation_id)
        if row is None:
            return None
        try:
            snapshot = snapshot_from_json(json.loads(row["snapshot_json"]))
        except (TypeError, ValueError, KeyError):
            return None
        return StoredOperation(snapshot, SaveState(row["state"]), row)

    def records(
        self,
        *,
        account_id: str,
        athlete_id: str,
        open_only: bool = True,
    ) -> list[StoredOperation]:
        rows = db.planner_operations(
            self._conn,
            account_id=account_id,
            athlete_id=athlete_id,
            states=OPEN_STATES if open_only else None,
        )
        result: list[StoredOperation] = []
        for row in rows:
            try:
                snapshot = snapshot_from_json(json.loads(row["snapshot_json"]))
            except (TypeError, ValueError, KeyError):
                continue
            result.append(StoredOperation(snapshot, SaveState(row["state"]), row))
        return result

    def purge_completed(self, *, now: str) -> int:
        return db.purge_planner_operations(
            self._conn,
            older_than=now,
            terminal_states=TERMINAL_STATES,
        )


def retention_cutoff(now_iso: str, *, days: int = RETENTION_DAYS) -> str:
    """Der Zeitpunkt, vor dem abgeschlossene Vorgänge gelöscht werden."""
    from datetime import timedelta

    moment = datetime.fromisoformat(now_iso)
    return (moment - timedelta(days=days)).isoformat(timespec="seconds")


__all__ = [
    "OPEN_STATES",
    "RETENTION_DAYS",
    "SqliteOperationStore",
    "StoredOperation",
    "TERMINAL_STATES",
    "plan_from_json",
    "plan_to_json",
    "retention_cutoff",
    "snapshot_from_json",
    "snapshot_to_json",
]
