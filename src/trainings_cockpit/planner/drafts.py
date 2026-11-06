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
from dataclasses import replace
from datetime import datetime
from typing import Any

from .details import build_local_plan_payload, build_plan_payload
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
    PlanId,
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
from .primitives import require_local_date
from .profile import heart_rate_zone_options
from .remote import read_remote_event
from .validation import (
    FieldKind,
    parse_field_input,
    validate_draft,
)


class DraftProjectionError(ValueError):
    """Der übergebene Entwurf passt nicht zur gespeicherten Basis."""


SUPPORTED_NEW_SPORTS = ("Run", "Ride", "Swim")
START_TEMPLATES = ("simple", "repeat", "empty")
_DEFAULT_NAMES = {
    ("Run", "simple"): "Dauerlauf",
    ("Ride", "simple"): "Radeinheit",
    ("Swim", "simple"): "Schwimmeinheit",
    ("Run", "repeat"): "Intervalle",
    ("Ride", "repeat"): "Intervalle",
    ("Swim", "repeat"): "Intervalle",
}
_SIMPLE_STEP_NAMES = {
    "Run": "Dauerlauf",
    "Ride": "Radeinheit",
    "Swim": "Schwimmeinheit",
}


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
    raw_date = body.get("date")
    try:
        date = base.date if raw_date is None else require_local_date(raw_date)
    except ValueError as exc:
        raise DraftProjectionError(f"Das Datum ist ungültig: {exc}") from exc
    return PlannedWorkout(
        local_id=base.local_id,
        remote_id=base.remote_id,
        external_id=base.external_id,
        name=base.name if name is None else str(name),
        sport=base.sport,
        date=date,
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
    field_path = str(raw.get("field_path") or "")
    unit = raw.get("unit")
    minimum = 1 if field_kind is FieldKind.INTEGER and field_path == "repetitions" else None
    maximum = (
        2**53 - 1
        if field_kind is FieldKind.INTEGER and field_path == "repetitions"
        else None
    )
    return parse_field_input(
        text,
        field_kind,
        unit=(
            PaceUnit(str(unit))
            if unit and field_kind is FieldKind.PACE
            else None
        ),
        minimum=minimum,
        maximum=maximum,
    )


def _target_values(parsed: object) -> Value | ValueRange | None:
    if isinstance(parsed, (Value, ValueRange)):
        return parsed
    if isinstance(parsed, (int, float)) and not isinstance(parsed, bool):
        return Value(float(parsed))
    return None


def _build_target(
    kind: str,
    unit: str | None,
    values: Value | ValueRange,
    node: StepNode,
):
    if kind == "pace":
        current = getattr(node.target, "unit", None)
        pace_unit = (
            PaceUnit(unit)
            if unit
            else current if isinstance(current, PaceUnit) else PaceUnit.SECONDS_PER_KM
        )
        return PaceTarget(unit=pace_unit, values=values)
    if kind == "power":
        current = getattr(node.target, "unit", None)
        power_unit = (
            PowerUnit(unit)
            if unit
            else current if isinstance(current, PowerUnit) else PowerUnit.WATTS
        )
        return PowerTarget(unit=power_unit, values=values)
    if kind == "heartRate":
        return HeartRateTarget(values=values, unit="bpm")
    return None


def _target_entries(
    entries: list[tuple[str, FieldBuffer, Mapping[str, Any]]],
) -> tuple[str, str | None, Value | ValueRange] | None:
    """Ein Zielwert entsteht nur aus vollständigen, gültigen Feldern."""
    kind = "none"
    unit: str | None = None
    for path, buffer, spec in entries:
        if spec.get("target_kind"):
            kind = str(spec.get("target_kind"))
        if spec.get("unit"):
            unit = str(spec.get("unit"))
        if buffer.validity is FieldValidity.VALID and path == "target.value":
            values = _target_values(buffer.parsed)
            if values is not None:
                return kind, unit, values
    minimum: float | None = None
    maximum: float | None = None
    for path, buffer, _ in entries:
        if buffer.validity is not FieldValidity.VALID:
            return None
        if not isinstance(buffer.parsed, (int, float)) or isinstance(buffer.parsed, bool):
            return None
        if path == "target.min":
            minimum = float(buffer.parsed)
        elif path == "target.max":
            maximum = float(buffer.parsed)
    if minimum is None or maximum is None or minimum > maximum:
        return None
    return kind, unit, ValueRange(minimum, maximum)


def _apply_target(
    nodes: tuple[WorkoutNode, ...],
    node_id: NodeId,
    entries: list[tuple[str, FieldBuffer, Mapping[str, Any]]],
) -> tuple[WorkoutNode, ...] | None:
    values = list(nodes)
    for index, node in enumerate(nodes):
        if node.id == node_id:
            if not isinstance(node, StepNode):
                return None
            if any(buffer.validity is not FieldValidity.VALID for _, buffer, _ in entries):
                # Ein unfertiger oder ungültiger Zielwert lässt bewusst keinen
                # alten gültigen Wert derselben Einheit stehen (Abschnitt 6.4/6.5).
                values[index] = replace(node, target=NoTarget())
                return tuple(values)
            built = _target_entries(entries)
            if built is None:
                values[index] = replace(node, target=NoTarget())
                return tuple(values)
            kind, unit, values_spec = built
            if kind == "none":
                kind = str(getattr(node.target, "kind", "none"))
            target = _build_target(kind, unit, values_spec, node)
            if target is None:
                return tuple(values)
            values[index] = replace(node, target=target)
            return tuple(values)
        if isinstance(node, RepeatNode):
            replaced = _apply_target(node.children, node_id, entries)
            if replaced is not None:
                values[index] = replace(node, children=replaced)
                return tuple(values)
    return None


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
            if buffer.validity is not FieldValidity.VALID:
                return tuple(values)
            if isinstance(node, StepNode):
                if field_path == "name":
                    values[index] = replace(node, name=str(buffer.parsed))
                elif field_path == "end.value":
                    if isinstance(buffer.parsed, (int, float)) and not isinstance(
                        buffer.parsed, bool
                    ):
                        end = (
                            TimeEnd(float(buffer.parsed))
                            if kind == "duration"
                            else DistanceEnd(float(buffer.parsed))
                        )
                        values[index] = replace(node, end=end)
                return tuple(values)
            if isinstance(node, RepeatNode):
                if field_path == "name":
                    values[index] = replace(node, name=str(buffer.parsed))
                elif field_path == "repetitions":
                    if isinstance(buffer.parsed, int) and not isinstance(buffer.parsed, bool):
                        values[index] = replace(node, repetitions=buffer.parsed)
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
                values[index] = replace(node, children=replaced)
                return tuple(values)
    return None


def _validate_target_ranges(
    buffers: dict[str, FieldBuffer],
    specs: Mapping[str, Mapping[str, Any]],
) -> None:
    """Erklärt vertauschte Grenzen am Obergrenzenfeld statt sie still zu sortieren."""
    for key, buffer in list(buffers.items()):
        spec = specs.get(key) or {}
        if spec.get("field_path") != "target.min":
            continue
        node_id = str(spec.get("node_id") or "")
        max_key = field_buffer_key(node_id, "target.max")
        maximum = buffers.get(max_key)
        if maximum is None or maximum.validity is not FieldValidity.VALID:
            continue
        if buffer.validity is not FieldValidity.VALID:
            continue
        if not isinstance(buffer.parsed, (int, float)) or not isinstance(
            maximum.parsed, (int, float)
        ):
            continue
        if float(buffer.parsed) <= float(maximum.parsed):
            continue
        kind = str(spec.get("target_kind") or "")
        message = (
            "Die schnellere Pace muss eine kleinere Zeit sein als die langsamere. "
            "Bitte die Grenzen tauschen."
            if kind == "pace"
            else "Der Minimalwert darf nicht größer als der Maximalwert sein."
        )
        buffers[max_key] = FieldBuffer(
            raw=maximum.raw,
            parsed=None,
            validity=FieldValidity.INVALID,
            message=message,
        )


def _apply_buffers(
    plan: PlannedWorkout,
    buffers: dict[str, FieldBuffer],
    specs: Mapping[str, Mapping[str, Any]],
) -> PlannedWorkout:
    nodes = plan.nodes
    target_buffers: dict[str, list[tuple[str, FieldBuffer, Mapping[str, Any]]]] = {}
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
        if field_path.startswith("target."):
            target_buffers.setdefault(node_id, []).append((field_path, buffer, spec))
            continue
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
    for node_id, entries in target_buffers.items():
        try:
            replaced = _apply_target(nodes, NodeId(node_id), entries)
        except (TypeError, ValueError) as exc:
            raise DraftProjectionError(
                f"Zielwert für {node_id!r} ist ungültig."
            ) from exc
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


def _parse_buffers(
    payload: Mapping[str, Any],
    current: PlannedWorkout,
) -> tuple[dict[str, FieldBuffer], Mapping[str, Any]]:
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
    _validate_target_ranges(buffers, specs)
    return buffers, specs


def _draft_meta(
    draft: WorkoutDraft,
    validation: Any,
    *,
    is_new: bool,
    base_source_hash: str | None,
) -> dict[str, Any]:
    base = draft.base
    return {
        "base_local_id": str(base.local_id) if base is not None else None,
        "base_source_hash": base_source_hash,
        "remote_id": str(draft.current.remote_id) if draft.current.remote_id is not None else None,
        "is_new": is_new,
        "dirty": (draft.current != base) if base is not None else True,
        "has_field_input": bool(draft.field_buffers),
        "valid": validation.valid,
        "field_states": {
            key: {
                "validity": buffer.validity.value,
                "message": buffer.message,
                "parsed": buffer.parsed,
            }
            for key, buffer in sorted(draft.field_buffers.items())
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
            "reason": "Die Remote-Speicherung wird in P18 angeschlossen.",
        },
    }


def _start_zone(
    sport: str,
    zone_profiles: Mapping[str, Any] | None,
) -> ZoneTarget | NoTarget:
    options = heart_rate_zone_options(sport, zone_profiles)
    zone = next(
        (entry for entry in options["zones"] if entry.get("level") == 2),
        None,
    )
    if zone is None or not options.get("zone_set_id"):
        return NoTarget()
    return ZoneTarget(
        metric=ZoneMetric.HEART_RATE,
        zone_id=str(zone["id"]),
        zone_set_id=str(options["zone_set_id"]),
    )


def _starter_nodes(
    sport: str,
    template: str,
    zone_profiles: Mapping[str, Any] | None,
) -> tuple[WorkoutNode, ...]:
    if template == "empty":
        return ()
    if template == "simple":
        return (
            StepNode(
                id=NodeId.new(),
                name=_SIMPLE_STEP_NAMES[sport],
                role=StepRole.STEADY,
                end=TimeEnd(45 * 60),
                target=_start_zone(sport, zone_profiles),
            ),
        )
    return (
        RepeatNode(
            id=NodeId.new(),
            name="Hauptteil 4x",
            repetitions=4,
            children=(
                StepNode(
                    id=NodeId.new(),
                    name="Belastung",
                    role=StepRole.WORK,
                    end=TimeEnd(2 * 60),
                    target=NoTarget(),
                ),
                StepNode(
                    id=NodeId.new(),
                    name="Erholung",
                    role=StepRole.RECOVERY,
                    end=TimeEnd(2 * 60),
                    target=NoTarget(),
                ),
            ),
        ),
    )


def build_new_draft_projection(
    body: object,
    *,
    time_zone: str,
    account_id: str = "default",
    athlete_id: str = "default",
    zone_profiles: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Baut einen rein lokalen neuen Entwurf ohne Remote-Event.

    Der Endpunkt ist kein Create: Er liest und schreibt kein Event. Die lokale
    Identität stammt ausschließlich aus ``draft_id``; eine Remote-ID existiert
    erst nach einem späteren bestätigten Speichern.
    """
    payload = _body_mapping(body)
    if payload.get("remote_id") is not None:
        raise DraftProjectionError(
            "Ein neuer lokaler Entwurf darf keine bestehende Remote-ID tragen."
        )
    draft_id = str(payload.get("draft_id") or "").strip()
    if not draft_id:
        raise DraftProjectionError("Ein neuer Entwurf braucht eine stabile draft_id.")
    sport = str(payload.get("sport") or "")
    if sport not in SUPPORTED_NEW_SPORTS:
        raise DraftProjectionError(
            "Sportart muss Run, Ride oder Swim sein."
        )
    try:
        date = require_local_date(payload.get("date"))
    except ValueError as exc:
        raise DraftProjectionError(f"Das Datum ist ungültig: {exc}") from exc
    template = str(payload.get("template") or "simple")
    if template not in START_TEMPLATES:
        raise DraftProjectionError("Startaufbau muss simple, repeat oder empty sein.")
    raw_name = payload.get("name")
    name = "" if raw_name is None else str(raw_name).strip()
    if not name and payload.get("nodes") is None:
        name = _DEFAULT_NAMES.get((sport, template), "Neue Einheit")

    raw_nodes = payload.get("nodes")
    if raw_nodes is None:
        nodes = _starter_nodes(sport, template, zone_profiles)
    elif isinstance(raw_nodes, list):
        nodes = tuple(_node(node, {}) for node in raw_nodes)
    else:
        raise DraftProjectionError("nodes muss eine Liste sein.")

    plan = PlannedWorkout(
        local_id=PlanId(f"plan:{draft_id}"),
        remote_id=None,
        external_id=None,
        name=name,
        sport=sport,
        date=date,
        local_time=None,
        time_zone=time_zone,
        nodes=nodes,
        notes=None,
        editability=Editability.FULL,
    )
    buffers, specs = _parse_buffers(payload, plan)
    current = _apply_buffers(plan, buffers, specs)
    draft = WorkoutDraft.new(current, draft_id=draft_id)
    draft.field_buffers = buffers
    validation = validate_draft(draft)

    projection = build_local_plan_payload(
        current,
        fetched_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        zone_profiles=zone_profiles,
        account_id=account_id,
        athlete_id=athlete_id,
    )
    projection["draft"] = _draft_meta(
        draft,
        validation,
        is_new=True,
        base_source_hash=None,
    )
    return projection


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

    buffers, specs = _parse_buffers(payload, current)
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
    projection["draft"] = _draft_meta(
        draft,
        validation,
        is_new=False,
        base_source_hash=remote.source.relevant_content_hash,
    )
    return projection


__all__ = [
    "DraftProjectionError",
    "START_TEMPLATES",
    "SUPPORTED_NEW_SPORTS",
    "build_draft_projection",
    "build_new_draft_projection",
]
