"""Lokale Entwurfsprojektion für den Inline-Editor.

Der Endpunkt liest die gespeicherte Basis weiterhin über den vorhandenen
Remote-Leser, baut daraus zusammen mit den Feldeingaben des Browsers einen
:class:`WorkoutDraft` und liefert denselben Detailvertrag wie die Leseansicht.
Es gibt keinen Netzwerkaufruf und keinen Schreibvorgang: Der Entwurf lebt nur
in dieser Anfrage.

Feldpuffer werden nach Knoten-ID plus Feldpfad geführt. Ein unfertiger Wert
bleibt als Rohtext und Befund erhalten; das validierte Modell behält den
zuletzt gültigen Wert. Nur ein ausdrücklicher Wechsel auf ein offenes Ende
setzt den Abschnitt im Modell auf :class:`OpenEnd`, damit Diagramm und Summen
die unvollständige Stelle zeigen, statt eine Dauer zu erfinden.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from .details import build_plan_payload
from .model import (
    DistanceEnd,
    Editability,
    FieldBuffer,
    FieldValidity,
    HeartRateTarget,
    NodeId,
    NoTarget,
    OpenEnd,
    PaceTarget,
    PaceUnit,
    PlannedWorkout,
    PowerTarget,
    PowerUnit,
    RepeatNode,
    StepNode,
    StepRole,
    TimeEnd,
    UnsupportedNode,
    Value,
    ValueRange,
    WorkoutDraft,
    WorkoutNode,
    ZoneMetric,
    ZoneTarget,
    field_buffer_key,
)
from .remote import read_remote_event
from .validation import (
    FieldKind,
    parse_field_input,
    validate_draft,
)


class DraftProjectionError(ValueError):
    """Der übergebene Entwurf passt nicht zur gespeicherten Basis."""


def _body_mapping(body: object) -> Mapping[str, Any]:
    if not isinstance(body, Mapping):
        raise DraftProjectionError("Der Entwurf muss ein Objekt sein.")
    return body


def _value_spec(raw: object) -> Value | ValueRange:
    if not isinstance(raw, Mapping):
        raise DraftProjectionError("Ein Zielwert muss ein Objekt sein.")
    kind = str(raw.get("kind") or "")
    try:
        if kind == "value":
            return Value(float(raw["value"]))
        if kind == "range":
            return ValueRange(float(raw["min"]), float(raw["max"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise DraftProjectionError("Der Zielwert ist ungültig.") from exc
    raise DraftProjectionError("Der Zielwert braucht die Art value oder range.")


def _target(raw: object):
    if raw is None:
        return NoTarget()
    if not isinstance(raw, Mapping):
        raise DraftProjectionError("Das Ziel muss ein Objekt sein.")
    kind = str(raw.get("kind") or "none")
    try:
        if kind in {"none", "missing"}:
            return NoTarget()
        if kind == "zone":
            return ZoneTarget(
                metric=ZoneMetric(str(raw.get("metric") or "heartRate")),
                zone_id=str(raw.get("zone_id") or ""),
                zone_set_id=(
                    str(raw["zone_set_id"]) if raw.get("zone_set_id") is not None else None
                ),
            )
        if kind == "heartRate":
            return HeartRateTarget(values=_value_spec(raw.get("values")), unit="bpm")
        if kind == "power":
            return PowerTarget(
                unit=PowerUnit(str(raw.get("unit") or "watts")),
                values=_value_spec(raw.get("values")),
            )
        if kind == "pace":
            return PaceTarget(
                unit=PaceUnit(str(raw.get("unit") or "secondsPerKm")),
                values=_value_spec(raw.get("values")),
            )
    except (TypeError, ValueError) as exc:
        raise DraftProjectionError(f"Das Ziel ist ungültig: {exc}") from exc
    raise DraftProjectionError(f"Unbekannte Zielart {kind!r}.")


def _end(raw: object):
    if not isinstance(raw, Mapping):
        raise DraftProjectionError("Das Ende muss ein Objekt sein.")
    kind = str(raw.get("kind") or "open")
    try:
        if kind == "time":
            return TimeEnd(float(raw["seconds"]))
        if kind == "distance":
            return DistanceEnd(float(raw["metres"]))
        if kind == "open":
            return OpenEnd()
    except (KeyError, TypeError, ValueError) as exc:
        raise DraftProjectionError("Das Ende ist ungültig.") from exc
    raise DraftProjectionError(f"Unbekannte Ende-Bedingung {kind!r}.")


def _base_nodes_by_id(nodes: tuple[WorkoutNode, ...]) -> dict[str, WorkoutNode]:
    out: dict[str, WorkoutNode] = {}
    for node in nodes:
        out[str(node.id)] = node
        if isinstance(node, RepeatNode):
            out.update(_base_nodes_by_id(node.children))
    return out


def _node(raw: object, base_nodes: Mapping[str, WorkoutNode]) -> WorkoutNode:
    if not isinstance(raw, Mapping):
        raise DraftProjectionError("Ein Knoten muss ein Objekt sein.")
    node_id = str(raw.get("node_id") or "").strip()
    if not node_id:
        raise DraftProjectionError("Ein Knoten braucht seine stabile node_id.")
    base = base_nodes.get(node_id)
    kind = str(raw.get("kind") or (base.kind if base is not None else "step"))
    if kind == "step":
        source_ref = raw.get("source_ref")
        notes = raw.get("notes")
        if base is not None:
            source_ref = source_ref if source_ref is not None else base.source_ref
            notes = notes if notes is not None else getattr(base, "notes", None)
        return StepNode(
            id=node_id,
            name=str(raw.get("name") or ""),
            end=_end(raw.get("end")),
            role=StepRole(str(raw.get("role") or "steady")),
            target=_target(raw.get("target")),
            notes=notes,
            source_ref=source_ref,
        )
    if kind == "repeat":
        raw_children = raw.get("children")
        if not isinstance(raw_children, list):
            raise DraftProjectionError("Eine Wiederholungsgruppe braucht Kinder.")
        source_ref = raw.get("source_ref")
        if base is not None and source_ref is None:
            source_ref = getattr(base, "source_ref", None)
        try:
            repetitions = int(raw.get("repetitions") or 1)
        except (TypeError, ValueError) as exc:
            raise DraftProjectionError("Die Wiederholungszahl ist ungültig.") from exc
        return RepeatNode(
            id=node_id,
            name=str(raw.get("name") or ""),
            repetitions=repetitions,
            children=tuple(_node(child, base_nodes) for child in raw_children),
            skip_final_recovery=bool(raw.get("skip_final_recovery")),
            source_ref=source_ref,
        )
    if kind == "unsupported":
        if base is not None and isinstance(base, UnsupportedNode):
            return base
        return UnsupportedNode(
            id=node_id,
            label=str(raw.get("label") or "Nicht unterstützter Abschnitt"),
            reason=str(raw.get("reason") or "Unbekannter Inhalt."),
            source_ref=str(raw.get("source_ref") or f"/draft/{node_id}"),
        )
    raise DraftProjectionError(f"Unbekannte Knotenart {kind!r}.")


def _current_plan(
    base: PlannedWorkout,
    body: Mapping[str, Any],
) -> PlannedWorkout:
    raw_nodes = body.get("nodes")
    if not isinstance(raw_nodes, list):
        raise DraftProjectionError("nodes muss eine Liste sein.")
    base_nodes = _base_nodes_by_id(base.nodes)
    nodes = tuple(_node(node, base_nodes) for node in raw_nodes)
    name = body.get("name")
    return PlannedWorkout(
        local_id=base.local_id,
        remote_id=base.remote_id,
        external_id=base.external_id,
        name=base.name if name is None else str(name),
        sport=base.sport,
        date=base.date,
        local_time=base.local_time,
        time_zone=base.time_zone,
        nodes=nodes,
        notes=base.notes,
        editability=base.editability,
        editability_reason=base.editability_reason,
        restriction_codes=base.restriction_codes,
    )


def _parse_buffer(raw: object) -> FieldBuffer:
    if not isinstance(raw, Mapping):
        raise DraftProjectionError("Ein Feldpuffer muss ein Objekt sein.")
    text = raw.get("raw")
    if not isinstance(text, str):
        raise DraftProjectionError("Ein Feldpuffer braucht den unveränderten Rohtext.")
    kind = str(raw.get("kind") or "text")
    if kind == "text":
        return FieldBuffer(raw=text, parsed=text, validity=FieldValidity.VALID)
    try:
        field_kind = FieldKind(kind)
    except ValueError as exc:
        raise DraftProjectionError(f"Unbekannte Feldart {kind!r}.") from exc
    unit = raw.get("unit")
    return parse_field_input(
        text,
        field_kind,
        unit=PaceUnit(str(unit)) if unit else None,
    )


def _apply_buffer(
    nodes: tuple[WorkoutNode, ...],
    node_id: NodeId,
    field_path: str,
    buffer: FieldBuffer,
    *,
    kind: str,
) -> tuple[WorkoutNode, ...] | None:
    values = list(nodes)
    for index, node in enumerate(values):
        if node.id == node_id:
            if not isinstance(node, StepNode):
                return None
            if buffer.validity is not FieldValidity.VALID:
                return tuple(values)
            if field_path == "name":
                values[index] = StepNode(
                    id=node.id,
                    name=str(buffer.parsed),
                    end=node.end,
                    role=node.role,
                    target=node.target,
                    notes=node.notes,
                    source_ref=node.source_ref,
                )
            elif field_path == "end.value":
                if isinstance(buffer.parsed, (int, float)) and not isinstance(
                    buffer.parsed, bool
                ):
                    end = (
                        TimeEnd(float(buffer.parsed))
                        if kind == "duration"
                        else DistanceEnd(float(buffer.parsed))
                    )
                    values[index] = StepNode(
                        id=node.id,
                        name=node.name,
                        end=end,
                        role=node.role,
                        target=node.target,
                        notes=node.notes,
                        source_ref=node.source_ref,
                    )
                return tuple(values)
            return tuple(values)
        if isinstance(node, RepeatNode):
            replaced = _apply_buffer(
                node.children,
                node_id,
                field_path,
                buffer,
                kind=kind,
            )
            if replaced is not None:
                values[index] = RepeatNode(
                    id=node.id,
                    name=node.name,
                    repetitions=node.repetitions,
                    children=replaced,
                    skip_final_recovery=node.skip_final_recovery,
                    source_ref=node.source_ref,
                )
                return tuple(values)
    return None


def _apply_buffers(
    plan: PlannedWorkout,
    buffers: dict[str, FieldBuffer],
    specs: Mapping[str, Mapping[str, Any]],
) -> PlannedWorkout:
    nodes = plan.nodes
    for key, buffer in buffers.items():
        spec = specs.get(key) or {}
        node_id = spec.get("node_id")
        field_path = spec.get("field_path")
        kind = str(spec.get("kind") or "text")
        if not isinstance(node_id, str) or not isinstance(field_path, str):
            node_id, _, field_path = key.partition(":")
            # field_buffer_key trennt mit dem letzten Doppelpunkt vor dem Pfad.
            if ":" in field_path and node_id.startswith("node"):
                prefix, _, rest = key.rpartition(":")
                if rest and prefix.startswith("node:"):
                    node_id, field_path = prefix, rest
        try:
            replaced = _apply_buffer(
                nodes,
                NodeId(node_id),
                field_path,
                buffer,
                kind=kind,
            )
        except (TypeError, ValueError) as exc:
            raise DraftProjectionError(f"Feldpuffer {key!r} ist ungültig.") from exc
        if replaced is not None:
            nodes = replaced
    return PlannedWorkout(
        local_id=plan.local_id,
        remote_id=plan.remote_id,
        external_id=plan.external_id,
        name=plan.name,
        sport=plan.sport,
        date=plan.date,
        local_time=plan.local_time,
        time_zone=plan.time_zone,
        nodes=nodes,
        notes=plan.notes,
        editability=plan.editability,
        editability_reason=plan.editability_reason,
        restriction_codes=plan.restriction_codes,
    )


def build_draft_projection(
    row: Mapping[str, Any],
    body: object,
    *,
    time_zone: str,
    account_id: str = "default",
    athlete_id: str = "default",
    zone_profiles: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Baut den lokalen Entwurf und liefert seine validierte Darstellung."""
    payload = _body_mapping(body)
    from .details import _event_from_row

    event = _event_from_row(row)
    remote = read_remote_event(
        event,
        fetched_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        time_zone=time_zone,
        account_id=account_id,
        athlete_id=athlete_id,
    )
    base = remote.plan
    if base.editability is Editability.READ_ONLY:
        raise DraftProjectionError("Diese Planung ist schreibgeschützt.")
    current = _current_plan(base, payload)

    specs = payload.get("field_buffers") or {}
    if not isinstance(specs, Mapping):
        raise DraftProjectionError("field_buffers muss ein Objekt sein.")
    buffers: dict[str, FieldBuffer] = {}
    for key, spec in specs.items():
        if not isinstance(key, str) or not isinstance(spec, Mapping):
            raise DraftProjectionError("Ein Feldpuffer braucht Schlüssel und Objekt.")
        node_id = str(spec.get("node_id") or "")
        field_path = str(spec.get("field_path") or "")
        if not node_id or not field_path:
            raise DraftProjectionError("Ein Feldpuffer braucht Knoten-ID und Feldpfad.")
        expected = field_buffer_key(node_id, field_path)
        if key != expected:
            raise DraftProjectionError("Der Feldpuffer-Schlüssel passt nicht zu Knoten und Pfad.")
        if current.find_node(node_id) is None:
            raise DraftProjectionError(f"Knoten {node_id!r} gehört nicht zum Entwurf.")
        buffers[key] = _parse_buffer(spec)

    current = _apply_buffers(current, buffers, specs)
    draft = WorkoutDraft.start(base, remote.source)
    draft.current = current
    draft.field_buffers = buffers
    validation = validate_draft(draft)

    projection = build_plan_payload(
        current,
        remote.source,
        event,
        row,
        zone_profiles=zone_profiles,
        account_id=account_id,
        athlete_id=athlete_id,
    )
    projection["draft"] = {
        "base_local_id": str(base.local_id),
        "base_source_hash": remote.source.relevant_content_hash,
        "dirty": current != base,
        "has_field_input": bool(buffers),
        "valid": validation.valid,
        "field_states": {
            key: {
                "validity": buffer.validity.value,
                "message": buffer.message,
                "parsed": buffer.parsed,
            }
            for key, buffer in sorted(buffers.items())
        },
        "issues": [
            {
                "code": issue.code.value,
                "message": issue.message,
                "node_id": str(issue.node_id) if issue.node_id is not None else None,
                "field": issue.field,
            }
            for issue in validation.issues
        ],
        "write": {
            "available": False,
            "reason": "Der Remote-Schreibpfad wird in P17 aktiviert.",
        },
    }
    return projection


__all__ = ["DraftProjectionError", "build_draft_projection"]
