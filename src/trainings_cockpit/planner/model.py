"""UI-unabhängiges Fachmodell für geplante Trainings.

Das Modell trennt vier Dinge, die in der Oberfläche leicht zusammenrutschen:

* Rohdaten bleiben im :class:`SourceSnapshot` unverändert erhalten.
* :class:`PlannedWorkout` beschreibt den fachlichen Aufbau.
* :class:`WorkoutDraft` hält lokale Änderungen und unfertige Feldpuffer.
* Abgeleitete Summen, Diagramme und Beschriftungen entstehen erst im Consumer.

Zeiten stehen intern in Sekunden, Distanzen in Metern. Zonenreferenzen sind
eigene Objekte mit String-ID; ein aufgelöster bpm- oder Wattbereich ersetzt
die relative Vorgabe nicht.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, ClassVar

from .identities import (
    DraftId,
    NodeId,
    OperationId,
    PlanId,
    RemoteEventId,
)
from .primitives import (
    LocalDate,
    require_local_date,
    require_local_time,
    require_text,
    require_time_zone,
    require_timestamp,
)


class StepRole(StrEnum):
    STEADY = "steady"
    WARMUP = "warmup"
    WORK = "work"
    RECOVERY = "recovery"
    COOLDOWN = "cooldown"


class ZoneMetric(StrEnum):
    HEART_RATE = "heartRate"
    POWER = "power"
    PACE = "pace"


class PowerUnit(StrEnum):
    WATTS = "watts"
    PERCENT_FTP = "percentFtp"


class PaceUnit(StrEnum):
    SECONDS_PER_KM = "secondsPerKm"
    SECONDS_PER_100M = "secondsPer100m"


class Editability(StrEnum):
    FULL = "full"
    METADATA_ONLY = "metadataOnly"
    READ_ONLY = "readOnly"


class RestrictionCode(StrEnum):
    UNKNOWN_CONTENT = "unknown_content"
    MULTIPLE_TARGETS = "multiple_targets"
    RAMP_OR_SPECIAL_STEP = "ramp_or_special_step"
    REMOTE_READ_ONLY = "remote_read_only"
    MISSING_PERMISSION = "missing_permission"


class FieldValidity(StrEnum):
    VALID = "valid"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} muss eine Zahl sein.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} muss endlich sein.")
    return number


def _positive(value: object, field: str) -> float:
    number = _number(value, field)
    if number <= 0:
        raise ValueError(f"{field} muss größer als 0 sein.")
    return number


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    return require_text(value, field)


# ------------------------------------------------------------------ Werte


@dataclass(frozen=True, slots=True)
class Value:
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _number(self.value, "value"))


@dataclass(frozen=True, slots=True)
class ValueRange:
    min: float
    max: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "min", _number(self.min, "min"))
        object.__setattr__(self, "max", _number(self.max, "max"))
        if self.min > self.max:
            raise ValueError("min darf nicht größer als max sein.")


type ValueSpec = Value | ValueRange


# ------------------------------------------------------------------ Ende


@dataclass(frozen=True, slots=True)
class TimeEnd:
    kind: ClassVar[str] = "time"
    seconds: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "seconds", _positive(self.seconds, "seconds"))


@dataclass(frozen=True, slots=True)
class DistanceEnd:
    kind: ClassVar[str] = "distance"
    metres: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "metres", _positive(self.metres, "metres"))


@dataclass(frozen=True, slots=True)
class OpenEnd:
    """Ein Entwurfsabschnitt, dessen Ende noch nicht gültig gesetzt ist.

    Der Wert existiert nur im lokalen Entwurf. Er hält die Stelle sichtbar,
    statt eine leere Eingabe in ``0`` oder eine erfundene Dauer zu verwandeln;
    gespeichert werden kann ein solcher Abschnitt nicht.
    """

    kind: ClassVar[str] = "open"


type StepEnd = TimeEnd | DistanceEnd | OpenEnd


# ------------------------------------------------------------------ Ziele


@dataclass(frozen=True, slots=True)
class NoTarget:
    kind: ClassVar[str] = "none"


@dataclass(frozen=True, slots=True)
class ZoneTarget:
    kind: ClassVar[str] = "zone"
    metric: ZoneMetric
    zone_id: str
    zone_set_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.metric, ZoneMetric):
            object.__setattr__(self, "metric", ZoneMetric(self.metric))
        object.__setattr__(self, "zone_id", require_text(self.zone_id, "zone_id"))
        object.__setattr__(self, "zone_set_id", _optional_text(self.zone_set_id, "zone_set_id"))


@dataclass(frozen=True, slots=True)
class HeartRateTarget:
    kind: ClassVar[str] = "heartRate"
    values: ValueSpec
    unit: str = "bpm"

    def __post_init__(self) -> None:
        if self.unit != "bpm":
            raise ValueError("Absolute Herzfrequenz braucht die Einheit bpm.")
        _validate_value_spec(self.values, "values")


@dataclass(frozen=True, slots=True)
class PowerTarget:
    kind: ClassVar[str] = "power"
    unit: PowerUnit
    values: ValueSpec

    def __post_init__(self) -> None:
        if not isinstance(self.unit, PowerUnit):
            object.__setattr__(self, "unit", PowerUnit(self.unit))
        _validate_value_spec(self.values, "values")


@dataclass(frozen=True, slots=True)
class PaceTarget:
    kind: ClassVar[str] = "pace"
    unit: PaceUnit
    values: ValueSpec

    def __post_init__(self) -> None:
        if not isinstance(self.unit, PaceUnit):
            object.__setattr__(self, "unit", PaceUnit(self.unit))
        _validate_value_spec(self.values, "values")


type StepTarget = NoTarget | ZoneTarget | HeartRateTarget | PowerTarget | PaceTarget
_TARGET_TYPES = (NoTarget, ZoneTarget, HeartRateTarget, PowerTarget, PaceTarget)


def _validate_value_spec(values: object, field: str) -> None:
    if not isinstance(values, (Value, ValueRange)):
        raise ValueError(f"{field} muss Value oder ValueRange sein.")


# ------------------------------------------------------------------ Knoten


@dataclass(frozen=True, slots=True)
class StepNode:
    kind: ClassVar[str] = "step"
    id: NodeId
    name: str
    end: StepEnd
    role: StepRole = StepRole.STEADY
    target: StepTarget = field(default_factory=NoTarget)
    notes: str | None = None
    source_ref: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, NodeId):
            object.__setattr__(self, "id", NodeId(self.id))
        if not isinstance(self.role, StepRole):
            object.__setattr__(self, "role", StepRole(self.role))
        if not isinstance(self.end, (TimeEnd, DistanceEnd, OpenEnd)):
            raise ValueError("end muss TimeEnd, DistanceEnd oder OpenEnd sein.")
        if not isinstance(self.target, _TARGET_TYPES):
            raise ValueError("target muss ein unterstütztes Ziel sein.")
        object.__setattr__(self, "notes", _optional_text(self.notes, "notes"))
        object.__setattr__(self, "source_ref", _optional_text(self.source_ref, "source_ref"))


_REPEAT_NAME_SUFFIX = re.compile(r"\s*\d+\s*[x×]\s*$", re.IGNORECASE)


def repeat_group_name(name: str) -> str:
    """Der Gruppenname ohne mitgeschriebene Wiederholungszahl.

    Die Anzahl kommt ausschließlich aus :attr:`RepeatNode.repetitions`; der
    Serializer schreibt sie selbst und entfernt deshalb eine Zahl im Namen
    („Hauptteil 4x“ wird mit sechs Wiederholungen zu „Hauptteil 6x“). Für
    Schreibpfad, Rundlauf und Konfliktvergleich ist derselbe Name maßgeblich.
    """
    return _REPEAT_NAME_SUFFIX.sub("", str(name)).strip()


@dataclass(frozen=True, slots=True)
class RepeatNode:
    kind: ClassVar[str] = "repeat"
    id: NodeId
    name: str
    repetitions: int
    children: tuple[WorkoutNode, ...]
    skip_final_recovery: bool = False
    source_ref: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, NodeId):
            object.__setattr__(self, "id", NodeId(self.id))
        if isinstance(self.repetitions, bool) or not isinstance(self.repetitions, int):
            raise ValueError("repetitions muss eine ganze Zahl sein.")
        if self.repetitions < 1:
            raise ValueError("repetitions muss mindestens 1 sein.")
        children = tuple(self.children)
        node_types = (StepNode, RepeatNode, UnsupportedNode)
        if any(not isinstance(child, node_types) for child in children):
            raise ValueError("children dürfen nur Workout-Knoten enthalten.")
        object.__setattr__(self, "children", children)
        object.__setattr__(self, "source_ref", _optional_text(self.source_ref, "source_ref"))


@dataclass(frozen=True, slots=True)
class UnsupportedNode:
    kind: ClassVar[str] = "unsupported"
    id: NodeId
    label: str
    reason: str
    source_ref: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, NodeId):
            object.__setattr__(self, "id", NodeId(self.id))
        object.__setattr__(self, "label", require_text(self.label, "label"))
        object.__setattr__(self, "reason", require_text(self.reason, "reason"))
        object.__setattr__(self, "source_ref", require_text(self.source_ref, "source_ref"))


type WorkoutNode = StepNode | RepeatNode | UnsupportedNode
_NODE_TYPES = (StepNode, RepeatNode, UnsupportedNode)


def iter_nodes(nodes: tuple[WorkoutNode, ...]) -> tuple[WorkoutNode, ...]:
    """Alle Knoten in Dokumentreihenfolge, inklusive Gruppenkindern."""
    out: list[WorkoutNode] = []
    for node in nodes:
        out.append(node)
        if isinstance(node, RepeatNode):
            out.extend(iter_nodes(node.children))
    return tuple(out)


# ------------------------------------------------------------------ Herkunft


def content_hash(raw: object) -> str:
    """Stabiler Hash über den erhaltenen Rohinhalt, nicht über abgeleitete Werte."""
    encoded = json.dumps(
        raw,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    remote_id: RemoteEventId
    fetched_at: str
    relevant_content_hash: str
    raw: Any
    remote_updated_at: str | None = None
    remote_version: str | None = None
    raw_workout_text: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.remote_id, RemoteEventId):
            object.__setattr__(self, "remote_id", RemoteEventId(self.remote_id))
        object.__setattr__(self, "fetched_at", require_timestamp(self.fetched_at, "fetched_at"))
        object.__setattr__(
            self,
            "relevant_content_hash",
            require_text(self.relevant_content_hash, "relevant_content_hash"),
        )
        if self.remote_updated_at is not None:
            object.__setattr__(
                self,
                "remote_updated_at",
                require_timestamp(self.remote_updated_at, "remote_updated_at"),
            )
        if self.remote_version is not None:
            object.__setattr__(
                self, "remote_version", require_text(self.remote_version, "remote_version")
            )
        if self.raw_workout_text is not None:
            if not isinstance(self.raw_workout_text, str):
                raise ValueError("raw_workout_text muss Text oder None sein.")
        if self.raw is None:
            raise ValueError("raw muss den erhaltenen Remote-Inhalt tragen.")
        object.__setattr__(self, "raw", copy.deepcopy(self.raw))

    @classmethod
    def capture(
        cls,
        remote_id: str | int,
        raw: Any,
        *,
        fetched_at: str,
        remote_updated_at: str | None = None,
        remote_version: str | None = None,
        raw_workout_text: str | None = None,
    ) -> SourceSnapshot:
        if raw_workout_text is None and isinstance(raw, dict):
            description = raw.get("description")
            if isinstance(description, str):
                raw_workout_text = description
        return cls(
            remote_id=RemoteEventId(remote_id),
            fetched_at=fetched_at,
            relevant_content_hash=content_hash(raw),
            raw=raw,
            remote_updated_at=remote_updated_at,
            remote_version=remote_version,
            raw_workout_text=raw_workout_text,
        )

    @property
    def raw_event(self) -> dict[str, Any]:
        return self.raw if isinstance(self.raw, dict) else {}


# ------------------------------------------------------------------ Planung


@dataclass(frozen=True, slots=True)
class PlannedWorkout:
    local_id: PlanId
    name: str
    sport: str
    date: LocalDate
    time_zone: str
    nodes: tuple[WorkoutNode, ...]
    remote_id: RemoteEventId | None = None
    external_id: str | None = None
    local_time: str | None = None
    notes: str | None = None
    editability: Editability = Editability.FULL
    editability_reason: str | None = None
    restriction_codes: tuple[RestrictionCode, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.local_id, PlanId):
            object.__setattr__(self, "local_id", PlanId(self.local_id))
        if self.remote_id is not None and not isinstance(self.remote_id, RemoteEventId):
            object.__setattr__(self, "remote_id", RemoteEventId(self.remote_id))
        object.__setattr__(self, "name", str(self.name or ""))
        object.__setattr__(self, "sport", require_text(self.sport, "sport"))
        object.__setattr__(self, "date", require_local_date(self.date))
        object.__setattr__(self, "time_zone", require_time_zone(self.time_zone))
        if self.local_time is not None:
            object.__setattr__(self, "local_time", require_local_time(self.local_time))
        object.__setattr__(self, "external_id", _optional_text(self.external_id, "external_id"))
        object.__setattr__(self, "notes", _optional_text(self.notes, "notes"))

        nodes = tuple(self.nodes)
        if any(not isinstance(node, _NODE_TYPES) for node in nodes):
            raise ValueError("nodes dürfen nur Workout-Knoten enthalten.")
        ids = [node.id for node in iter_nodes(nodes)]
        if len(ids) != len(set(ids)):
            raise ValueError("Knoten-IDs müssen innerhalb eines Plans eindeutig sein.")
        object.__setattr__(self, "nodes", nodes)

        if not isinstance(self.editability, Editability):
            object.__setattr__(self, "editability", Editability(self.editability))
        codes = tuple(
            code if isinstance(code, RestrictionCode) else RestrictionCode(code)
            for code in self.restriction_codes
        )
        if len(codes) != len(set(codes)):
            raise ValueError("restriction_codes dürfen sich nicht wiederholen.")
        object.__setattr__(self, "restriction_codes", codes)
        object.__setattr__(
            self,
            "editability_reason",
            _optional_text(self.editability_reason, "editability_reason"),
        )
        if self.editability is not Editability.FULL and not self.editability_reason:
            raise ValueError("Eine eingeschränkte Planung braucht einen konkreten Grund.")
        if self.editability is Editability.FULL and (
            self.editability_reason or self.restriction_codes
        ):
            raise ValueError("Volle Editierbarkeit trägt keinen Einschränkungsgrund.")

    @property
    def is_structure_editable(self) -> bool:
        return self.editability is Editability.FULL

    @property
    def is_metadata_editable(self) -> bool:
        return self.editability in (Editability.FULL, Editability.METADATA_ONLY)

    @property
    def has_unsupported_content(self) -> bool:
        return any(isinstance(node, UnsupportedNode) for node in iter_nodes(self.nodes))

    def find_node(self, node_id: NodeId | str) -> WorkoutNode | None:
        wanted = node_id if isinstance(node_id, NodeId) else NodeId(node_id)
        return next((node for node in iter_nodes(self.nodes) if node.id == wanted), None)

    def move_node(self, node_id: NodeId | str, target_index: int) -> PlannedWorkout:
        """Verschiebt einen Knoten innerhalb seiner Ebene; IDs bleiben unverändert."""
        moved = _move_in_level(self.nodes, NodeId(node_id), target_index)
        if moved is None:
            raise KeyError(f"Knoten {node_id!r} nicht gefunden.")
        return replace(self, nodes=moved)

    def reschedule(self, new_date: LocalDate) -> PlannedWorkout:
        """Verschiebt nur den lokalen Kalendertag, nicht die lokale Uhrzeit.

        Die Uhrzeit bleibt als lokaler Wert erhalten; eine UTC-Umrechnung würde
        sie an Zeitumstellungen verschieben. Remote-ID, Knoten-IDs und
        Zeitzone bleiben unverändert.
        """
        return replace(self, date=require_local_date(new_date))


def _move_in_level(
    nodes: tuple[WorkoutNode, ...],
    node_id: NodeId,
    target_index: int,
) -> tuple[WorkoutNode, ...] | None:
    values = list(nodes)
    for index, node in enumerate(values):
        if node.id == node_id:
            if not 0 <= target_index < len(values):
                raise IndexError(
                    f"Zielindex {target_index} liegt außerhalb von 0…{len(values) - 1}."
                )
            if target_index == index:
                return tuple(values)
            moved = values.pop(index)
            values.insert(target_index, moved)
            return tuple(values)

    for index, node in enumerate(values):
        if not isinstance(node, RepeatNode):
            continue
        moved_children = _move_in_level(node.children, node_id, target_index)
        if moved_children is not None:
            values[index] = replace(node, children=moved_children)
            return tuple(values)
    return None


# ------------------------------------------------------------------ Entwurf


@dataclass(frozen=True, slots=True)
class FieldBuffer:
    raw: str
    parsed: Any
    validity: FieldValidity
    message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.raw, str):
            raise ValueError("raw muss der unveränderte Feldtext sein.")
        if not isinstance(self.validity, FieldValidity):
            object.__setattr__(self, "validity", FieldValidity(self.validity))
        object.__setattr__(self, "message", _optional_text(self.message, "message"))


def field_buffer_key(node_id: NodeId | str, field_path: str) -> str:
    node = node_id if isinstance(node_id, NodeId) else NodeId(node_id)
    return f"{node}:{require_text(field_path, 'field_path')}"


@dataclass(slots=True)
class WorkoutDraft:
    current: PlannedWorkout
    draft_id: DraftId = field(default_factory=DraftId.new)
    operation_id: OperationId = field(default_factory=OperationId.new)
    base: PlannedWorkout | None = None
    base_source: SourceSnapshot | None = None
    field_buffers: dict[str, FieldBuffer] = field(default_factory=dict)
    selected_node_id: NodeId | None = None
    expanded_node_id: NodeId | None = None
    local_revision: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.current, PlannedWorkout):
            raise TypeError("current muss ein PlannedWorkout sein.")
        if self.base is not None and not isinstance(self.base, PlannedWorkout):
            raise TypeError("base muss ein PlannedWorkout oder None sein.")
        if self.base_source is not None and not isinstance(self.base_source, SourceSnapshot):
            raise TypeError("base_source muss ein SourceSnapshot oder None sein.")
        if not isinstance(self.draft_id, DraftId):
            object.__setattr__(self, "draft_id", DraftId(self.draft_id))
        if not isinstance(self.operation_id, OperationId):
            object.__setattr__(self, "operation_id", OperationId(self.operation_id))

        if self.base_source is not None and self.base is None:
            raise ValueError("Ein Basissnapshot braucht eine Basisplanung.")
        if self.base is not None:
            if self.base.local_id != self.current.local_id:
                raise ValueError("Basis und Entwurf müssen dieselbe lokale Plan-ID tragen.")
            if self.base_source is not None:
                if self.base.remote_id is None:
                    raise ValueError("Ein Basissnapshot braucht eine Remote-ID der Basis.")
                if self.base.remote_id != self.base_source.remote_id:
                    raise ValueError(
                        "Basissnapshot und Basisplanung tragen verschiedene Remote-IDs."
                    )

        if any(not isinstance(key, str) or not isinstance(value, FieldBuffer)
               for key, value in self.field_buffers.items()):
            raise TypeError("field_buffers müssen FieldBuffer unter Textschlüsseln tragen.")
        for name in ("selected_node_id", "expanded_node_id"):
            value = getattr(self, name)
            if value is None:
                continue
            node_id = value if isinstance(value, NodeId) else NodeId(value)
            if self.current.find_node(node_id) is None:
                raise ValueError(f"{name} verweist auf keinen Knoten des Entwurfs.")
            object.__setattr__(self, name, node_id)
        if isinstance(self.local_revision, bool) or not isinstance(self.local_revision, int):
            raise ValueError("local_revision muss eine ganze Zahl sein.")
        if self.local_revision < 0:
            raise ValueError("local_revision darf nicht negativ sein.")

    @classmethod
    def start(
        cls,
        base: PlannedWorkout,
        source: SourceSnapshot | None = None,
        *,
        draft_id: DraftId | str | None = None,
        operation_id: OperationId | str | None = None,
    ) -> WorkoutDraft:
        """Beginnt einen Entwurf, ohne die gespeicherte Basisplanung zu verändern."""
        return cls(
            current=copy.deepcopy(base),
            base=base,
            base_source=source,
            draft_id=DraftId(draft_id) if draft_id is not None else DraftId.new(),
            operation_id=(
                OperationId(operation_id) if operation_id is not None else OperationId.new()
            ),
        )

    @classmethod
    def new(
        cls,
        current: PlannedWorkout,
        *,
        draft_id: DraftId | str | None = None,
        operation_id: OperationId | str | None = None,
    ) -> WorkoutDraft:
        """Beginnt einen neuen lokalen Entwurf ohne Remote-Basis."""
        return cls(
            current=current,
            base=None,
            base_source=None,
            draft_id=DraftId(draft_id) if draft_id is not None else DraftId.new(),
            operation_id=(
                OperationId(operation_id) if operation_id is not None else OperationId.new()
            ),
        )

    @property
    def incomplete_fields(self) -> tuple[str, ...]:
        return tuple(
            key
            for key, buffer in self.field_buffers.items()
            if buffer.validity is not FieldValidity.VALID
        )

    @property
    def has_unsaved_changes(self) -> bool:
        return self.base is None or self.current != self.base or bool(self.field_buffers)

    def set_field_buffer(
        self,
        node_id: NodeId | str,
        field_path: str,
        buffer: FieldBuffer,
    ) -> WorkoutDraft:
        node = node_id if isinstance(node_id, NodeId) else NodeId(node_id)
        if self.current.find_node(node) is None:
            raise KeyError(f"Knoten {node!r} nicht gefunden.")
        if not isinstance(buffer, FieldBuffer):
            raise TypeError("buffer muss ein FieldBuffer sein.")
        self.field_buffers[field_buffer_key(node, field_path)] = buffer
        self.local_revision += 1
        return self

    def clear_field_buffer(self, node_id: NodeId | str, field_path: str) -> WorkoutDraft:
        self.field_buffers.pop(field_buffer_key(node_id, field_path), None)
        self.local_revision += 1
        return self

    def select(self, node_id: NodeId | str | None) -> WorkoutDraft:
        selected = None if node_id is None else (
            node_id if isinstance(node_id, NodeId) else NodeId(node_id)
        )
        if selected is not None and self.current.find_node(selected) is None:
            raise KeyError(f"Knoten {node_id!r} nicht gefunden.")
        self.selected_node_id = selected
        self.local_revision += 1
        return self

    def expand(self, node_id: NodeId | str | None) -> WorkoutDraft:
        expanded = None if node_id is None else (
            node_id if isinstance(node_id, NodeId) else NodeId(node_id)
        )
        if expanded is not None and self.current.find_node(expanded) is None:
            raise KeyError(f"Knoten {node_id!r} nicht gefunden.")
        self.expanded_node_id = expanded
        self.local_revision += 1
        return self

    def move_node(self, node_id: NodeId | str, target_index: int) -> WorkoutDraft:
        self.current = self.current.move_node(node_id, target_index)
        self.local_revision += 1
        return self
