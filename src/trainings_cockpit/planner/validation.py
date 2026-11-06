"""Gemeinsame Parser, Validierung, Ausführungsfolge und Mengen.

Diese Datei ist die eine fachliche Wahrheit für Editor, Diagramm, Speicherung
und Serializer. Sie trennt bewusst:

* Feldvalidierung (:func:`parse_field_input`) von Workoutvalidierung
  (:func:`validate_workout`), weil ein unfertiges Feld noch kein ungültiges
  Workout ist.
* strukturelle Ausführungen (:func:`derive_execution_sequence`) von bekannten
  Gesamtmengen (:func:`calculate_known_totals`). Große Wiederholungen werden
  für Summen algebraisch gerechnet und für die Darstellung ausdrücklich
  komprimiert, nie still abgeschnitten.
* exakte Speicherwerte (Sekunden, Meter) von der Formatierung an der
  Oberflächengrenze. Es wird nicht bei jedem Render gerundet.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .model import (
    DistanceEnd,
    FieldBuffer,
    FieldValidity,
    HeartRateTarget,
    NoTarget,
    OpenEnd,
    PaceTarget,
    PaceUnit,
    PlannedWorkout,
    PowerTarget,
    PowerUnit,
    RepeatNode,
    StepEnd,
    StepNode,
    StepRole,
    StepTarget,
    TimeEnd,
    UnsupportedNode,
    Value,
    ValueRange,
    WorkoutNode,
    ZoneMetric,
    ZoneTarget,
)

# ------------------------------------------------------------------ Parser

_NUMBER_RE = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")
_DURATION_TOKEN_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(h|std|stunden?|m|min|minuten?|s|sek|sekunden?)",
    re.IGNORECASE,
)
_CLOCK_RE = re.compile(r"^(\d+):([0-5]\d)(?::([0-5]\d))?$")
_DISTANCE_RE = re.compile(
    r"^(\d+(?:[.,]\d+)?)\s*(km|kilometer|m|mtr|meter|metres?|metre)?$",
    re.IGNORECASE,
)
_RANGE_SPLIT_RE = re.compile(r"\s*(?:-|–|bis|to)\s*", re.IGNORECASE)


class FieldKind(StrEnum):
    DURATION = "duration"
    DISTANCE = "distance"
    DECIMAL = "decimal"
    PACE = "pace"
    PACE_RANGE = "paceRange"
    VALUE_RANGE = "valueRange"
    INTEGER = "integer"


def parse_decimal(text: str) -> float:
    """Dezimalzahl mit Punkt oder deutschem Komma, ohne stilles Abschneiden."""
    raw = text.strip()
    if not _NUMBER_RE.fullmatch(raw):
        raise ValueError(f"{text!r} ist keine Dezimalzahl.")
    number = float(raw.replace(",", "."))
    if not math.isfinite(number):
        raise ValueError("Die Zahl muss endlich sein.")
    return number


def parse_duration(text: str) -> float:
    """Dauer als Sekunden.

    Unterstützt ``45`` (Minuten als Feldstandard), ``45m``, ``1h 30m``,
    ``1:30``, ``1:30:00`` und Sekundenangaben. Die Rückgabe ist exakt; die
    Anzeige rundet erst an der Formatierungsgrenze.
    """
    raw = text.strip()
    if not raw:
        raise ValueError("Die Dauer fehlt.")
    clock = _CLOCK_RE.fullmatch(raw)
    if clock:
        first, second, third = clock.groups()
        if third is None:
            # Dauerfelder schreiben ``1:30`` für eine Stunde dreißig, nicht für
            # eine Minute dreißig. Pace verwendet dagegen :func:`parse_pace`.
            seconds = int(first) * 3600 + int(second) * 60
        else:
            seconds = int(first) * 3600 + int(second) * 60 + int(third)
        _require_positive(seconds, "Die Dauer")
        return float(seconds)
    if _NUMBER_RE.fullmatch(raw):
        seconds = parse_decimal(raw) * 60
        _require_positive(seconds, "Die Dauer")
        return seconds

    position = 0
    total = 0.0
    found = False
    for match in _DURATION_TOKEN_RE.finditer(raw):
        between = raw[position : match.start()]
        if between.strip():
            raise ValueError(f"{text!r} enthält einen unlesbaren Dauerteil.")
        factor = _duration_factor(match.group(2))
        total += parse_decimal(match.group(1)) * factor
        position = match.end()
        found = True
    if not found or raw[position:].strip():
        raise ValueError(f"{text!r} ist keine Dauer.")
    _require_positive(total, "Die Dauer")
    return total


def parse_distance(text: str) -> float:
    """Distanz als Meter; ohne Einheit gilt Meter als Feldstandard."""
    raw = text.strip()
    if not raw:
        raise ValueError("Die Distanz fehlt.")
    match = _DISTANCE_RE.fullmatch(raw)
    if not match:
        raise ValueError(f"{text!r} ist keine Distanz.")
    number_text, unit = match.groups()
    unit = (unit or "m").lower()
    # „1.000 m“ ist im Sporttext eine Tausenderangabe, „1.5 km“ dagegen
    # dezimal. Komma bleibt immer dezimal.
    if "." in number_text and "," not in number_text:
        groups = number_text.split(".")
        if len(groups) > 1 and all(len(group) == 3 for group in groups[1:]):
            number_text = "".join(groups)
    number = parse_decimal(number_text)
    metres = number * 1000 if unit.startswith(("km", "kilometer")) else number
    _require_positive(metres, "Die Distanz")
    return metres


def parse_pace(text: str, unit: PaceUnit | str = PaceUnit.SECONDS_PER_KM) -> float:
    """Pace als Sekunden pro Referenzstrecke.

    ``5:30`` und ``5,5`` bedeuten beide 330 s/km; ``2:00 /100 m`` bleibt 120
    Sekunden pro 100 Meter und wird nicht als Sekunden pro Kilometer gedeutet.
    """
    pace_unit = unit if isinstance(unit, PaceUnit) else PaceUnit(unit)
    raw = text.strip()
    if not raw:
        raise ValueError("Die Pace fehlt.")
    suffix = _pace_suffix(pace_unit)
    for candidate in (suffix, suffix.replace(" ", ""), "min/km", "min/100m", "/km", "/100m"):
        if candidate and raw.lower().endswith(candidate.lower()):
            raw = raw[: -len(candidate)].strip()
            break
    if _NUMBER_RE.fullmatch(raw):
        seconds = parse_decimal(raw) * 60
    else:
        clock = _CLOCK_RE.fullmatch(raw)
        if not clock:
            invalid_clock = re.fullmatch(r"(\d+):(\d{2,})", raw)
            if invalid_clock and int(invalid_clock.group(2)) > 59:
                raise ValueError(
                    f"{text!r} ist keine gültige Pace: Sekunden müssen 00–59 "
                    "sein, zum Beispiel 6:15."
                )
            raise ValueError(f"{text!r} ist keine Pace.")
        first, second, third = clock.groups()
        seconds = int(first) * 60 + int(second)
        if third is not None:
            seconds += int(third) / 60
    _require_positive(seconds, "Die Pace")
    return seconds


def parse_pace_range(
    text: str,
    unit: PaceUnit | str = PaceUnit.SECONDS_PER_KM,
) -> Value | ValueRange:
    """Pace als Einzelwert oder Bereich, ohne /km und /100 m zu verwechseln."""
    raw = text.strip()
    if not raw:
        raise ValueError("Die Pace fehlt.")
    parts = [part for part in _RANGE_SPLIT_RE.split(raw) if part.strip()]
    if not 1 <= len(parts) <= 2:
        raise ValueError(f"{text!r} ist keine Pace oder kein Pacebereich.")
    values = [parse_pace(part, unit) for part in parts]
    if len(values) == 1:
        return Value(values[0])
    low, high = values
    if low > high:
        raise ValueError(
            "Die erste Pacegrenze ist langsamer als die zweite. Bitte den "
            "schnelleren Wert zuerst nennen."
        )
    if low == high:
        return Value(low)
    return ValueRange(low, high)


def parse_value_range(
    text: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> Value | ValueRange:
    """Ein Einzelwert oder Bereich; ``0`` ist ein gültiger Einzelwert.

    Der fehlende Wert ist ausdrücklich ``None``/ein unvollständiger
    :class:`FieldBuffer`, nicht ``0``. Ein Bereich darf nicht vertauscht
    werden.
    """
    raw = text.strip()
    if not raw:
        raise ValueError("Der Wert fehlt.")
    for suffix in ("%ftp", "%", "w", "bpm", "ftp"):
        if raw.lower().endswith(suffix):
            raw = raw[: -len(suffix)].strip()
            break
    if _NUMBER_RE.fullmatch(raw):
        parts = [raw]
    else:
        parts = [part for part in _RANGE_SPLIT_RE.split(raw) if part != ""]
    if not 1 <= len(parts) <= 2:
        raise ValueError(f"{text!r} ist kein Einzelwert oder Bereich.")
    numbers = [parse_decimal(part) for part in parts]
    if len(numbers) == 2 and numbers[0] > numbers[1]:
        raise ValueError("Der Minimalwert darf nicht größer als der Maximalwert sein.")
    for number in numbers:
        if minimum is not None and number < minimum:
            raise ValueError(f"Der Wert muss mindestens {minimum:g} sein.")
        if maximum is not None and number > maximum:
            raise ValueError(f"Der Wert darf höchstens {maximum:g} sein.")
    if len(numbers) == 1:
        return Value(numbers[0])
    return ValueRange(numbers[0], numbers[1])


def parse_field_input(
    text: str,
    kind: FieldKind | str,
    *,
    unit: PaceUnit | str | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
) -> FieldBuffer:
    """Validiert genau ein Feld und lässt unfertige Eingaben stehen.

    Ein leerer Text ist ``incomplete``, kein Fehler und kein Nullwert. Erst die
    Workoutvalidierung entscheidet, ob das Speichern insgesamt erlaubt ist.
    """
    field_kind = kind if isinstance(kind, FieldKind) else FieldKind(kind)
    raw = text if isinstance(text, str) else str(text)
    if not raw.strip():
        return FieldBuffer(
            raw=raw,
            parsed=None,
            validity=FieldValidity.INCOMPLETE,
            message="Wert fehlt.",
        )
    try:
        if field_kind is FieldKind.DURATION:
            parsed: Any = parse_duration(raw)
            _check_bounds(parsed, minimum if minimum is not None else 0.000001, maximum)
        elif field_kind is FieldKind.DISTANCE:
            parsed = parse_distance(raw)
            _check_bounds(parsed, minimum if minimum is not None else 0.000001, maximum)
        elif field_kind is FieldKind.DECIMAL:
            parsed = parse_decimal(raw)
            _check_bounds(parsed, minimum, maximum)
        elif field_kind is FieldKind.PACE:
            parsed = parse_pace(raw, unit or PaceUnit.SECONDS_PER_KM)
            _check_bounds(parsed, minimum if minimum is not None else 0.000001, maximum)
        elif field_kind is FieldKind.PACE_RANGE:
            parsed = parse_pace_range(raw, unit or PaceUnit.SECONDS_PER_KM)
        elif field_kind is FieldKind.VALUE_RANGE:
            parsed = parse_value_range(raw, minimum=minimum, maximum=maximum)
        elif field_kind is FieldKind.INTEGER:
            number = parse_decimal(raw)
            if not number.is_integer():
                raise ValueError("Der Wert muss eine ganze Zahl sein.")
            parsed = int(number)
            _check_bounds(parsed, minimum, maximum)
        else:  # pragma: no cover - Enum ist vollständig
            raise ValueError("Unbekannte Feldart.")
    except ValueError as exc:
        return FieldBuffer(
            raw=raw,
            parsed=None,
            validity=FieldValidity.INVALID,
            message=str(exc),
        )
    return FieldBuffer(raw=raw, parsed=parsed, validity=FieldValidity.VALID)


# ------------------------------------------------------------------ Ausführungen


@dataclass(frozen=True, slots=True)
class Execution:
    """Eine tatsächlich auszuführende Einzelvorgabe mit stabiler Herkunft."""

    node_id: Any
    group_id: Any | None
    repeat_group_ids: tuple[Any, ...]
    repetition_index: int | None
    repetition_path: tuple[int, ...]
    position: int
    name: str
    role: StepRole
    target: StepTarget
    end: StepEnd


@dataclass(frozen=True, slots=True)
class ExecutionCompression:
    """Ausdrücklich benannte Verdichtung statt stiller Kürzung."""

    node_id: Any
    parent_group_id: Any | None
    first_position: int
    omitted_executions: int
    omitted_repetitions: int
    reason: str = "Segmentbudget erreicht"


@dataclass(frozen=True, slots=True)
class ExecutionSequence:
    executions: tuple[Execution, ...]
    compressions: tuple[ExecutionCompression, ...]
    total_executions: int
    has_unknown: bool = False

    @property
    def complete(self) -> bool:
        return not self.compressions

    @property
    def executed_count(self) -> int:
        return self.total_executions


@dataclass(frozen=True, slots=True)
class KnownTotals:
    """Bekannte Mengen ohne Schätzungen; ``0`` ist nicht „unbekannt“."""

    duration_seconds: float
    distance_metres: float
    executions: int
    has_unknown: bool = False
    first_end: str | None = None

    @property
    def is_mixed(self) -> bool:
        return self.duration_seconds > 0 and self.distance_metres > 0


def calculate_known_totals(plan: PlannedWorkout | Sequence[WorkoutNode]) -> KnownTotals:
    """Summen algebraisch, also auch für sehr große Wiederholungszahlen."""
    nodes = plan.nodes if isinstance(plan, PlannedWorkout) else tuple(plan)
    return _totals_nodes(nodes)


def _totals_nodes(nodes: Sequence[WorkoutNode]) -> KnownTotals:
    duration = 0.0
    distance = 0.0
    executions = 0
    unknown = False
    first: str | None = None
    for node in nodes:
        if isinstance(node, StepNode):
            if first is None:
                first = node.end.kind
            if isinstance(node.end, TimeEnd):
                duration += node.end.seconds
            elif isinstance(node.end, DistanceEnd):
                distance += node.end.metres
            else:
                unknown = True
            executions += 1
            continue
        if isinstance(node, UnsupportedNode):
            unknown = True
            continue
        child = _totals_nodes(node.children)
        skipped = _skipped_recovery(node)
        skipped_totals = _totals_nodes((skipped,)) if skipped is not None else None
        # Die letzte Erholung wird nur in der letzten Wiederholung ausgelassen,
        # nicht in jeder. Deshalb einmal subtrahieren, dann multiplizieren.
        duration += child.duration_seconds * node.repetitions
        distance += child.distance_metres * node.repetitions
        executions += child.executions * node.repetitions
        if skipped_totals is not None:
            duration -= skipped_totals.duration_seconds
            distance -= skipped_totals.distance_metres
            executions -= 1
        unknown = unknown or child.has_unknown
        if first is None and child.executions > 0:
            first = child.first_end
    return KnownTotals(duration, distance, executions, unknown, first)


def execution_count(plan: PlannedWorkout | Sequence[WorkoutNode]) -> int:
    return calculate_known_totals(plan).executions


def derive_execution_sequence(
    plan: PlannedWorkout | Sequence[WorkoutNode],
    *,
    max_executions: int = 500,
) -> ExecutionSequence:
    """Leitet Ausführungen mit Knoten-ID und Wiederholungsindex ab.

    Bis ``max_executions`` wird exakt expandiert. Danach entsteht eine
    :class:`ExecutionCompression` mit der verbleibenden Anzahl; die Summen
    bleiben trotzdem exakt, weil sie nicht aus dieser Liste stammen.
    """
    if isinstance(max_executions, bool) or not isinstance(max_executions, int):
        raise ValueError("max_executions muss eine ganze Zahl sein.")
    if max_executions < 1:
        raise ValueError("max_executions muss mindestens 1 sein.")
    nodes = plan.nodes if isinstance(plan, PlannedWorkout) else tuple(plan)
    totals = _totals_nodes(nodes)
    executions: list[Execution] = []
    compressions: list[ExecutionCompression] = []
    budget = [max_executions]
    _walk(
        nodes,
        executions,
        compressions,
        budget,
        parent_group=None,
        repeat_groups=(),
        repetition_index=None,
        repetition_path=(),
    )
    return ExecutionSequence(
        executions=tuple(executions),
        compressions=tuple(compressions),
        total_executions=totals.executions,
        has_unknown=totals.has_unknown,
    )


def _walk(
    nodes: Sequence[WorkoutNode],
    out: list[Execution],
    compressions: list[ExecutionCompression],
    budget: list[int],
    *,
    parent_group: Any | None,
    repeat_groups: tuple[Any, ...],
    repetition_index: int | None,
    repetition_path: tuple[int, ...],
) -> None:
    for index, node in enumerate(nodes):
        if isinstance(node, StepNode):
            if budget[0] <= 0:
                _compress_remaining(nodes[index:], out, compressions, parent_group)
                return
            out.append(
                Execution(
                    node_id=node.id,
                    group_id=parent_group,
                    repeat_group_ids=repeat_groups,
                    repetition_index=repetition_index,
                    repetition_path=repetition_path,
                    position=len(out),
                    name=node.name,
                    role=node.role,
                    target=node.target,
                    end=node.end,
                )
            )
            budget[0] -= 1
            continue
        if isinstance(node, UnsupportedNode):
            continue

        children = node.children
        skipped = _skipped_recovery(node)
        child_count = _totals_nodes(children).executions
        if child_count <= 0:
            continue
        # Die letzte Erholung fehlt nur in der letzten Wiederholung. Davor
        # laufen alle Wiederholungen vollständig; das Segmentbudget wird nicht
        # durch eine falsche Pro-Wiederholung-Rechnung verbraucht.
        regular_repetitions = (
            node.repetitions - 1 if skipped is not None else node.repetitions
        )
        full_regular = min(regular_repetitions, budget[0] // child_count)
        for repetition in range(1, full_regular + 1):
            _walk(
                children,
                out,
                compressions,
                budget,
                parent_group=node.id,
                repeat_groups=(*repeat_groups, node.id),
                repetition_index=repetition,
                repetition_path=(*repetition_path, repetition),
            )
        remaining_regular = regular_repetitions - full_regular
        last_count = child_count - 1 if skipped is not None else 0
        if remaining_regular > 0:
            omitted = remaining_regular * child_count + last_count
            compressions.append(
                ExecutionCompression(
                    node_id=node.id,
                    parent_group_id=parent_group,
                    first_position=len(out),
                    omitted_executions=omitted,
                    omitted_repetitions=remaining_regular
                    + (1 if skipped is not None else 0),
                )
            )
            budget[0] = 0
        elif skipped is not None:
            last_children = tuple(child for child in children if child is not skipped)
            if last_count == 0:
                continue
            if budget[0] < last_count:
                compressions.append(
                    ExecutionCompression(
                        node_id=node.id,
                        parent_group_id=parent_group,
                        first_position=len(out),
                        omitted_executions=last_count,
                        omitted_repetitions=1,
                    )
                )
                budget[0] = 0
            else:
                _walk(
                    last_children,
                    out,
                    compressions,
                    budget,
                    parent_group=node.id,
                    repeat_groups=(*repeat_groups, node.id),
                    repetition_index=node.repetitions,
                    repetition_path=(*repetition_path, node.repetitions),
                )


def _compress_remaining(
    nodes: Sequence[WorkoutNode],
    out: list[Execution],
    compressions: list[ExecutionCompression],
    parent_group: Any | None,
) -> None:
    totals = _totals_nodes(nodes)
    if totals.executions <= 0:
        return
    first = next(
        (node for node in nodes if not isinstance(node, UnsupportedNode)),
        None,
    )
    if first is None:
        return
    compressions.append(
        ExecutionCompression(
            node_id=first.id,
            parent_group_id=parent_group,
            first_position=len(out),
            omitted_executions=totals.executions,
            omitted_repetitions=0,
        )
    )


def _skipped_recovery(node: RepeatNode) -> StepNode | None:
    """Nur eine letzte Erholung als direktes Kind wird ausgelassen."""
    if not node.skip_final_recovery or not node.children:
        return None
    last = node.children[-1]
    return last if isinstance(last, StepNode) and last.role is StepRole.RECOVERY else None


# ------------------------------------------------------------------ Validierung


class ValidationMode(StrEnum):
    STRUCTURE = "structure"
    METADATA = "metadata"


class ValidationCode(StrEnum):
    EMPTY_WORKOUT = "empty_workout"
    EMPTY_REPEAT = "empty_repeat"
    NO_EXECUTED_STEPS = "no_executed_steps"
    UNSUPPORTED_CONTENT = "unsupported_content"
    READ_ONLY = "read_only"
    METADATA_WITHOUT_BASE = "metadata_without_base"
    STRUCTURE_CHANGED = "structure_changed"
    INVALID_FIELD = "invalid_field"
    INCOMPLETE_FIELD = "incomplete_field"
    OPEN_END = "open_end"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: ValidationCode
    message: str
    node_id: Any | None = None
    field: str | None = None


@dataclass(frozen=True, slots=True)
class WorkoutValidation:
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.issues

    @property
    def codes(self) -> tuple[ValidationCode, ...]:
        return tuple(issue.code for issue in self.issues)


def validate_workout(
    plan: PlannedWorkout,
    *,
    mode: ValidationMode | str = ValidationMode.STRUCTURE,
) -> WorkoutValidation:
    """Prüft den Aufbau, getrennt von einzelnen Feldpuffern.

    ``structure`` verlangt zusätzlich, dass unbekannte Inhalte nicht in einen
    verlustbehafteten Schreibvorgang geraten. ``metadata`` erlaubt eine sichere
    Namensänderung, solange die Struktur unangetastet bleibt; die Prüfung der
    Basisgleichheit erfolgt in :func:`validate_draft`.
    """
    validation_mode = mode if isinstance(mode, ValidationMode) else ValidationMode(mode)
    issues: list[ValidationIssue] = []
    if not plan.nodes:
        issues.append(
            ValidationIssue(
                ValidationCode.EMPTY_WORKOUT,
                "Der Aufbau enthält keine Wurzelbausteine.",
            )
        )
    for node in _iter_all(plan.nodes):
        if isinstance(node, RepeatNode) and not node.children:
            issues.append(
                ValidationIssue(
                    ValidationCode.EMPTY_REPEAT,
                    "Eine Wiederholungsgruppe ohne Kinder führt nichts aus.",
                    node_id=node.id,
                )
            )
        if isinstance(node, StepNode) and isinstance(node.end, OpenEnd):
            issues.append(
                ValidationIssue(
                    ValidationCode.OPEN_END,
                    "Der Abschnitt hat noch kein gültiges Ende.",
                    node_id=node.id,
                )
            )
    totals = calculate_known_totals(plan)
    if plan.nodes and totals.executions == 0:
        issues.append(
            ValidationIssue(
                ValidationCode.NO_EXECUTED_STEPS,
                "Der Aufbau ist strukturell vorhanden, führt aber null Abschnitte aus.",
            )
        )
    if validation_mode is ValidationMode.STRUCTURE:
        unsupported = [node for node in _iter_all(plan.nodes) if isinstance(node, UnsupportedNode)]
        if unsupported:
            issues.append(
                ValidationIssue(
                    ValidationCode.UNSUPPORTED_CONTENT,
                    "Unbekannte Inhalte verhindern eine verlustfreie Strukturbearbeitung.",
                    node_id=unsupported[0].id,
                )
            )
    return WorkoutValidation(tuple(issues))


def validate_draft(
    draft: Any,
    *,
    mode: ValidationMode | str | None = None,
) -> WorkoutValidation:
    """Feldpuffer und Workout gemeinsam, aber mit getrennten Befunden."""
    from .model import Editability, WorkoutDraft

    if not isinstance(draft, WorkoutDraft):
        raise TypeError("draft muss ein WorkoutDraft sein.")
    current = draft.current
    validation_mode = (
        mode
        if mode is not None
        else (
            ValidationMode.METADATA
            if current.editability is Editability.METADATA_ONLY
            else ValidationMode.STRUCTURE
        )
    )
    if isinstance(validation_mode, str):
        validation_mode = ValidationMode(validation_mode)
    base_validation = validate_workout(current, mode=validation_mode)
    issues = list(base_validation.issues)

    for key, buffer in sorted(draft.field_buffers.items()):
        if buffer.validity is FieldValidity.INCOMPLETE:
            issues.append(
                ValidationIssue(
                    ValidationCode.INCOMPLETE_FIELD,
                    buffer.message or "Feld ist unvollständig.",
                    field=key,
                )
            )
        elif buffer.validity is FieldValidity.INVALID:
            issues.append(
                ValidationIssue(
                    ValidationCode.INVALID_FIELD,
                    buffer.message or "Feld ist ungültig.",
                    field=key,
                )
            )

    if current.editability is Editability.READ_ONLY:
        issues.append(
            ValidationIssue(
                ValidationCode.READ_ONLY,
                current.editability_reason or "Die Planung ist schreibgeschützt.",
            )
        )
    if current.editability is Editability.METADATA_ONLY:
        if draft.base is None:
            issues.append(
                ValidationIssue(
                    ValidationCode.METADATA_WITHOUT_BASE,
                    "Eine eingeschränkte Struktur braucht eine gespeicherte Basis.",
                )
            )
        elif current.nodes != draft.base.nodes or current.sport != draft.base.sport:
            issues.append(
                ValidationIssue(
                    ValidationCode.STRUCTURE_CHANGED,
                    "Bei eingeschränkter Editierbarkeit darf nur Metadaten geändert werden.",
                )
            )
    return WorkoutValidation(tuple(issues))


def _iter_all(nodes: Sequence[WorkoutNode]) -> Iterator[WorkoutNode]:
    for node in nodes:
        yield node
        if isinstance(node, RepeatNode):
            yield from _iter_all(node.children)


# ------------------------------------------------------------------ Formatierung


def format_duration(seconds: float) -> str:
    """Exakte Dauer, erst hier auf ganze Sekunden gerundet."""
    total = int(round(seconds))
    if total <= 0:
        return "0 min"
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} h")
    if minutes:
        parts.append(f"{minutes} min")
    if secs:
        parts.append(f"{secs} s")
    return " ".join(parts)


def format_distance(metres: float) -> str:
    """Exakte Distanz, erst hier lesbar gerundet."""
    if metres <= 0:
        return "0 m"
    if metres >= 1000:
        km = metres / 1000
        text = f"{km:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        return f"{text} km"
    return f"{int(round(metres))} m"


def format_pace(seconds: float, unit: PaceUnit | str = PaceUnit.SECONDS_PER_KM) -> str:
    pace_unit = unit if isinstance(unit, PaceUnit) else PaceUnit(unit)
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    suffix = "min/km" if pace_unit is PaceUnit.SECONDS_PER_KM else "/100 m"
    return f"{minutes}:{secs:02d} {suffix}"


def _pace_number(seconds: float, unit: PaceUnit) -> str:
    del unit
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"


def format_target(target: StepTarget | None) -> str:
    """Unterscheidet ausdrücklich ``0 W``, fehlenden Wert und ``Ohne Ziel``."""
    if target is None:
        return "Wert fehlt"
    if isinstance(target, NoTarget):
        return "Ohne Ziel"
    if isinstance(target, ZoneTarget):
        match = re.search(r"-(\d+)$", target.zone_id)
        return f"Zone {match.group(1)}" if match else f"Zone {target.zone_id}"
    if isinstance(target, HeartRateTarget):
        return _format_value(target.values, "bpm")
    if isinstance(target, PowerTarget):
        suffix = "W" if target.unit is PowerUnit.WATTS else "% FTP"
        return _format_value(target.values, suffix)
    if isinstance(target, PaceTarget):
        if isinstance(target.values, Value):
            return format_pace(target.values.value, target.unit)
        low = _pace_number(target.values.min, target.unit)
        high = _pace_number(target.values.max, target.unit)
        suffix = "min/km" if target.unit is PaceUnit.SECONDS_PER_KM else "/100 m"
        return f"{low}–{high} {suffix}"
    return "Ohne Ziel"


def _format_value(values: Value | ValueRange, suffix: str) -> str:
    if isinstance(values, Value):
        return f"{_number_text(values.value)} {suffix}"
    return f"{_number_text(values.min)}–{_number_text(values.max)} {suffix}"


def _number_text(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if "," not in text else text


def format_target_label(target: StepTarget | None) -> str:
    """Eine gemeinsame Zielbeschriftung für Kopfzeile, Graph und Validierung.

    ``format_target`` bleibt die reine Wertdarstellung (``0 W``,
    ``5:30 min/km``); diese Funktion ergänzt genau einmal die Zielart. Damit
    zeigen Listenzeile und Diagrammsegment denselben Text.
    """
    if target is None:
        return "Wert fehlt"
    if isinstance(target, NoTarget):
        return "Ohne Ziel"
    if isinstance(target, ZoneTarget):
        prefix = {
            ZoneMetric.HEART_RATE: "HF",
            ZoneMetric.POWER: "Leistung",
            ZoneMetric.PACE: "Pace",
        }.get(target.metric, "")
    elif isinstance(target, HeartRateTarget):
        prefix = "HF"
    elif isinstance(target, PowerTarget):
        prefix = "Leistung"
    elif isinstance(target, PaceTarget):
        prefix = "Pace"
    else:
        prefix = ""
    return f"{prefix} {format_target(target)}".strip()


def format_totals(totals: KnownTotals) -> str:
    """Bekannte Teil Mengen, ausdrücklich ohne Schätzung."""
    parts: list[str] = []
    duration = format_duration(totals.duration_seconds)
    distance = format_distance(totals.distance_metres)
    if totals.first_end == "distance":
        if totals.distance_metres > 0:
            parts.append(distance)
        if totals.duration_seconds > 0:
            parts.append(duration)
    else:
        if totals.duration_seconds > 0:
            parts.append(duration)
        if totals.distance_metres > 0:
            parts.append(distance)
    if totals.has_unknown:
        parts.append("offene Abschnitte")
    return " + ".join(parts) if parts else "Keine Vorgaben"


def _duration_factor(unit: str) -> float:
    lowered = unit.lower()
    if lowered.startswith(("h", "std", "stunde")):
        return 3600.0
    if lowered.startswith(("m", "min", "minute")):
        return 60.0
    return 1.0


def _pace_suffix(unit: PaceUnit) -> str:
    return "min/km" if unit is PaceUnit.SECONDS_PER_KM else "/100 m"


def _require_positive(value: float, field: str) -> None:
    if value <= 0:
        raise ValueError(f"{field} muss größer als 0 sein.")


def _check_bounds(
    value: float | int,
    minimum: float | None,
    maximum: float | None,
) -> None:
    if minimum is not None and value < minimum:
        raise ValueError(f"Der Wert muss mindestens {minimum:g} sein.")
    if maximum is not None and value > maximum:
        raise ValueError(f"Der Wert darf höchstens {maximum:g} sein.")


__all__ = [
    "Execution",
    "ExecutionCompression",
    "ExecutionSequence",
    "FieldKind",
    "KnownTotals",
    "ValidationCode",
    "ValidationIssue",
    "ValidationMode",
    "WorkoutValidation",
    "calculate_known_totals",
    "derive_execution_sequence",
    "execution_count",
    "format_distance",
    "format_duration",
    "format_pace",
    "format_target",
    "format_target_label",
    "format_totals",
    "parse_decimal",
    "parse_distance",
    "parse_duration",
    "parse_field_input",
    "parse_pace",
    "parse_pace_range",
    "parse_value_range",
    "validate_draft",
    "validate_workout",
]
