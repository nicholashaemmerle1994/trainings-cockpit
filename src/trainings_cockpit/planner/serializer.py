"""Geprüfter Serializer für Planungsentwürfe — ohne produktives Schreiben.

Der Editor kontrolliert ausschließlich diese Remote-Felder:

=================  ====================================================
Feld               Wann
=================  ====================================================
``name``           Update, wenn der Name geändert wurde; Create immer
``start_date_local`` Update, wenn der Termin geändert wurde; Create immer
``description``    Update nur bei einer Strukturänderung; Create immer
``type``           ausschließlich Create (Sportart)
``category``       ausschließlich Create, immer ``WORKOUT``
``external_id``    ausschließlich Create, stabil aus lokaler Identität
=================  ====================================================

Alles andere bleibt beim Update unangetastet: ``id``, ``external_id``,
``workout_doc``, ``moving_time``, ``distance``, ``icu_training_load``,
``icu_intensity``, Event-Notizen und fremde Schlüssel werden weder erzeugt
noch überschrieben. Bei reinen Name-/Datumsänderungen bleibt der vorhandene
Workouttext byte-for-byte unverändert, weil ``description`` dann gar nicht im
Payload steht.

Der Text-Serializer deckt Einzelabschnitte mit Zeit oder Distanz, HF-Zonen,
Pace, Watt, ``% FTP`` und einfache Wiederholungen ab. Rollen werden auf die
belegten Intervals-Kennzeichnungen ``intensity=warmup``, ``intensity=active``,
``intensity=rest`` und ``intensity=cooldown`` abgebildet. Nicht belegte oder
nicht verlustfrei abbildbare Fälle werden vor der Payload-Erzeugung mit einem
konkreten Grund abgelehnt, darunter absolute bpm, Leistungszonen,
benutzerdefinierte Zonen, verschachtelte Wiederholungen, ``skip_final_recovery``
sowie Workout-Dokumentnotizen bei Strukturänderungen.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Literal

from .identities import stable_external_id
from .model import (
    DistanceEnd,
    HeartRateTarget,
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
)
from .validation import validate_draft, validate_workout

CONTROLLED_REMOTE_FIELDS = ("name", "start_date_local", "description")
CREATE_ONLY_REMOTE_FIELDS = ("type", "category", "external_id")
PRESERVED_REMOTE_FIELDS = (
    "id",
    "external_id",
    "workout_doc",
    "moving_time",
    "distance",
    "icu_training_load",
    "icu_intensity",
    "notes",
)

_ROLE_TAGS = {
    StepRole.WARMUP: "intensity=warmup",
    StepRole.WORK: "intensity=active",
    StepRole.RECOVERY: "intensity=rest",
    StepRole.COOLDOWN: "intensity=cooldown",
}
_FORBIDDEN_NAME_TOKENS = (
    "intensity=",
    "<!>",
    "press lap",
    "freeride",
    "ramp ",
)
_DURATION_TOKEN = re.compile(
    r"(?i)(?:^|\s)\d+(?:[.,]\d+)?\s*(?:h|std|stunden?|m|min|minuten?|s|sek|sekunden?|km|mtr|meter|metres?)(?:\s|$)"
)
_REPEAT_SUFFIX = re.compile(r"\s*\d+\s*[x×]\s*$", re.IGNORECASE)
_ZONE_NUMBER = re.compile(r"-(\d+)$")


class SerializationError(ValueError):
    """Der Entwurf ist fachlich nicht sicher serialisierbar."""


class SerializationBoundaryError(TypeError):
    """An der Serializergrenze kam kein geplanter Workoutentwurf an."""


class NoWriteNeeded(SerializationError):
    """Der Entwurf enthält keine schreibrelevante Änderung."""


@dataclass(frozen=True, slots=True)
class PreparedWrite:
    """Ein unveränderlicher Schreibauftrag, noch ohne Netzwerkaufruf."""

    kind: Literal["create", "update"]
    mode: Literal["create", "metadata", "structure"]
    local_id: str
    remote_id: str | None
    payload: dict[str, Any]
    workout_text: str | None
    external_id: str | None = None
    controlled_fields: tuple[str, ...] = CONTROLLED_REMOTE_FIELDS

    @property
    def uses_remote_id(self) -> bool:
        return self.remote_id is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "mode": self.mode,
            "local_id": self.local_id,
            "remote_id": self.remote_id,
            "payload": dict(self.payload),
            "workout_text": self.workout_text,
            "external_id": self.external_id,
            "controlled_fields": list(self.controlled_fields),
        }


def _fail(message: str) -> None:
    raise SerializationError(message)


def _number_text(value: float) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SerializationError("Ein Zielwert muss eine Zahl sein.")
    if not math.isfinite(float(value)):
        raise SerializationError("Ein Zielwert muss endlich sein.")
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _duration_text(seconds: float) -> str:
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise SerializationError("Eine Dauer muss eine Zahl sein.")
    total = float(seconds)
    if not math.isfinite(total) or total <= 0:
        raise SerializationError("Eine Dauer muss größer als 0 sein.")
    if not total.is_integer():
        raise SerializationError(
            "Die Dauer lässt sich nicht ohne Präzisionsverlust als Workouttext ausgeben."
        )
    value = int(total)
    hours, rest = divmod(value, 3600)
    minutes, secs = divmod(rest, 60)
    text = ""
    if hours:
        text += f"{hours}h"
    if minutes:
        text += f"{minutes}m"
    if secs:
        text += f"{secs}s"
    return text or "0s"


def _distance_text(metres: float) -> str:
    if isinstance(metres, bool) or not isinstance(metres, (int, float)):
        raise SerializationError("Eine Distanz muss eine Zahl sein.")
    value = float(metres)
    if not math.isfinite(value) or value <= 0:
        raise SerializationError("Eine Distanz muss größer als 0 sein.")
    if not value.is_integer():
        raise SerializationError(
            "Die Distanz muss in ganzen Metern vorliegen; Bruchteile von Metern "
            "sind im belegten Workouttext nicht sicher darstellbar."
        )
    # `m` bedeutet im Workouttext Minuten. Meter schreibt das geprüfte Format
    # ausschließlich als `mtr`; 400 Meter werden deshalb nie zu 400 Minuten.
    return f"{int(value)}mtr"


def _pace_text(seconds: float) -> str:
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise SerializationError("Eine Pace muss eine Zahl sein.")
    value = float(seconds)
    if not math.isfinite(value) or value <= 0:
        raise SerializationError("Eine Pace muss größer als 0 sein.")
    if not value.is_integer():
        raise SerializationError(
            "Die Pace lässt sich nicht ohne Präzisionsverlust als Minuten:Sekunden ausgeben."
        )
    total = int(value)
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"


def _value_text(values: Value | ValueRange, suffix: str) -> str:
    if isinstance(values, Value):
        return f"{_number_text(values.value)}{suffix}"
    return (
        f"{_number_text(values.min)}-{_number_text(values.max)}{suffix}"
    )


def _zone_number(zone_id: str) -> int:
    match = _ZONE_NUMBER.search(zone_id)
    if match is None:
        raise SerializationError(
            f"Die Zonenreferenz {zone_id!r} ist keine belegte Standardzone. "
            "Benutzerdefinierte Zonen bleiben lesbar, werden aber nicht neu geschrieben."
        )
    return int(match.group(1))


def _target_text(target: Any) -> str:
    if isinstance(target, NoTarget):
        return ""
    if isinstance(target, ZoneTarget):
        number = _zone_number(target.zone_id)
        if target.metric is ZoneMetric.HEART_RATE:
            return f"Z{number} HR"
        if target.metric is ZoneMetric.PACE:
            return f"Z{number} Pace"
        raise SerializationError(
            "Leistungszonen sind laut Fähigkeitsmatrix nicht als Schreibweg belegt."
        )
    if isinstance(target, HeartRateTarget):
        raise SerializationError(
            "Absolute bpm-Werte haben keinen belegten Schreibvertrag und werden nicht erfunden."
        )
    if isinstance(target, PowerTarget):
        if target.unit is PowerUnit.WATTS:
            return _value_text(target.values, "w")
        if target.unit is PowerUnit.PERCENT_FTP:
            return _value_text(target.values, "%")
        raise SerializationError("Unbekannte Leistungseinheit.")
    if isinstance(target, PaceTarget):
        values = target.values
        if isinstance(values, Value):
            text = _pace_text(values.value)
        else:
            text = f"{_pace_text(values.min)}-{_pace_text(values.max)}"
        if target.unit is PaceUnit.SECONDS_PER_KM:
            return f"{text}/km Pace"
        if target.unit is PaceUnit.SECONDS_PER_100M:
            return f"{text}/100m Pace"
        raise SerializationError("Unbekannte Paceeinheit.")
    raise SerializationError("Unbekannte Zielart.")


def _safe_name(raw: str, *, kind: str, allow_measurements: bool = False) -> str:
    if not isinstance(raw, str):
        raise SerializationError(f"{kind} muss Text sein.")
    name = raw.strip()
    if "\n" in name or "\r" in name or "\t" in name:
        raise SerializationError(
            f"{kind} darf keine Zeilenumbrüche oder Tabulatoren enthalten."
        )
    lowered = name.lower()
    if name.startswith("-"):
        raise SerializationError(f"{kind} darf nicht mit einem Bindestrich beginnen.")
    if any(token in lowered for token in _FORBIDDEN_NAME_TOKENS):
        raise SerializationError(
            f"{kind} enthält ein reserviertes Workout-Konstrukt."
        )
    if not allow_measurements and _DURATION_TOKEN.search(name):
        raise SerializationError(
            f"{kind} enthält eine Zeit-, Distanz- oder Paceangabe, die der "
            "Workoutparser als Feld lesen würde. Bitte den Namen eindeutig halten."
        )
    return name


def _step_text(node: StepNode) -> str:
    name = _safe_name(node.name, kind="Abschnittsname")
    if isinstance(node.end, TimeEnd):
        end = _duration_text(node.end.seconds)
    elif isinstance(node.end, DistanceEnd):
        end = _distance_text(node.end.metres)
    else:
        assert isinstance(node.end, OpenEnd)
        raise SerializationError("Ein Abschnitt ohne gültiges Ende ist nicht speicherbar.")
    if node.notes:
        raise SerializationError(
            "Schrittnotizen lassen sich im belegten Workouttext nicht verlustfrei erhalten."
        )
    target = _target_text(node.target)
    parts = ["-"]
    if name:
        parts.append(name)
    parts.append(end)
    if target:
        parts.append(target)
    role_tag = _ROLE_TAGS.get(node.role)
    if role_tag is not None:
        parts.append(role_tag)
    return " ".join(parts)


def _repeat_header(node: RepeatNode) -> str:
    # Ein Gruppenkopf ist keine Prompt-Zeile; Zeit- und Distanzangaben darin
    # werden nicht als Schrittfeld gelesen. Zeilenumbrüche und reservierte
    # Konstrukte bleiben trotzdem gesperrt.
    name = _safe_name(node.name, kind="Gruppenname", allow_measurements=True)
    name = _REPEAT_SUFFIX.sub("", name).strip()
    if not name:
        return f"{node.repetitions}x"
    return f"{name} {node.repetitions}x"


def _node_lines(node: WorkoutNode) -> list[str]:
    if isinstance(node, UnsupportedNode):
        raise SerializationError(
            f"Unbekannter Inhalt {node.source_ref!r} kann nicht neu geschrieben werden."
        )
    if isinstance(node, StepNode):
        return [_step_text(node)]
    if node.skip_final_recovery:
        raise SerializationError(
            "„Letzte Erholung auslassen“ ist im belegten Workouttext nicht "
            "verlustfrei darstellbar."
        )
    if not node.children:
        raise SerializationError("Eine Wiederholungsgruppe ohne Kinder ist nicht speicherbar.")
    child_lines: list[str] = []
    for child in node.children:
        if isinstance(child, RepeatNode):
            raise SerializationError(
                "Verschachtelte Wiederholungen sind im belegten Schreibformat nicht unterstützt."
            )
        if not isinstance(child, StepNode):
            raise SerializationError("Eine Wiederholungsgruppe darf nur Abschnitte enthalten.")
        child_lines.append(_step_text(child))
    return [_repeat_header(node), *child_lines]


def serialize_workout_text(plan: PlannedWorkout) -> str:
    """Kanonischer Workouttext aus einem vollständig unterstützten Plan.

    ``plan.notes`` sind Event-/Dokumentnotizen und kein Bestandteil dieses
    Textes. :func:`prepare_write` prüft separat, ob sie beim Schreiben erhalten
    bleiben können.
    """
    if not isinstance(plan, PlannedWorkout):
        raise SerializationBoundaryError(
            "serialize_workout_text akzeptiert nur ein PlannedWorkout."
        )
    validation = validate_workout(plan)
    if not validation.valid:
        raise SerializationError(
            "Der Plan ist nicht serialisierbar: "
            + "; ".join(issue.message for issue in validation.issues)
        )

    blocks: list[str] = []
    current_steps: list[str] = []

    def flush() -> None:
        if current_steps:
            blocks.append("\n".join(current_steps))
            current_steps.clear()

    for node in plan.nodes:
        if isinstance(node, StepNode):
            current_steps.append(_step_text(node))
            continue
        flush()
        if isinstance(node, RepeatNode):
            blocks.append("\n".join(_node_lines(node)))
            continue
        assert isinstance(node, UnsupportedNode)
        raise SerializationError(
            f"Unbekannter Inhalt {node.source_ref!r} kann nicht neu geschrieben werden."
        )
    flush()
    text = "\n\n".join(blocks).strip()
    if not text:
        raise SerializationError("Ein leerer Aufbau hat keinen speicherbaren Workouttext.")
    return text


def _start_date_local(plan: PlannedWorkout) -> str:
    # Der Termin bleibt ein lokaler Kalendertag. Eine vorhandene Uhrzeit wird
    # unverändert übernommen; ohne Uhrzeit entsteht keine erfundene Zeit.
    if plan.local_time is not None:
        return f"{plan.date}T{plan.local_time}:00"
    return f"{plan.date}T00:00:00"


def _require_draft(candidate: object) -> WorkoutDraft:
    if type(candidate) is not WorkoutDraft:
        raise SerializationBoundaryError(
            "Der Serializer akzeptiert ausschließlich einen WorkoutDraft; "
            f"erhalten: {type(candidate).__name__}."
        )
    draft = candidate
    if type(draft.current) is not PlannedWorkout:
        raise SerializationBoundaryError("current muss ein geplantes Workout sein.")
    if draft.base is not None and type(draft.base) is not PlannedWorkout:
        raise SerializationBoundaryError("base muss ein geplantes Workout oder None sein.")
    # Eine gleiche numerische Plan-/Aktivitäts-ID erlaubt keinen Typwechsel:
    # Aktivitätsreferenzen, Listeneinträge und Roh-Dicts scheitern bereits an
    # der exakten Typgrenze oben.
    return draft


def _assert_plan_notes_preservable(plan: PlannedWorkout, source: Any | None) -> None:
    """Event-Notizen bleiben unberührt; Workout-Dokumentnotizen nicht.

    Der Payload kontrolliert ``description``, nicht das Event-Feld ``notes``.
    Stehen die Notizen jedoch im ``workout_doc``, würde eine neue Beschreibung
    sie verlieren. Dann wird die Strukturänderung abgelehnt.
    """
    if plan.notes is None:
        return
    if source is None:
        raise SerializationError(
            "Eine lokale Plannotiz hat im belegten Workouttext keinen sicheren Platz."
        )
    raw = source.raw if isinstance(source.raw, dict) else {}
    doc = raw.get("workout_doc")
    doc_notes = doc.get("notes") if isinstance(doc, dict) else None
    if isinstance(doc_notes, str) and doc_notes.strip():
        raise SerializationError(
            "Die Notiz steht im Workout-Dokument und würde beim Neuschreiben "
            "der Beschreibung verloren gehen."
        )


def _assert_structure_supported(plan: PlannedWorkout, source: Any | None = None) -> None:
    _assert_plan_notes_preservable(plan, source)
    for node in plan.nodes:
        if isinstance(node, UnsupportedNode):
            raise SerializationError(
                f"Unbekannter Inhalt {node.source_ref!r} verhindert eine Strukturänderung."
            )
    # Die Detailprüfung passiert beim eigentlichen Serialisieren der Knoten;
    # hier wird vorab nur der häufige, klar benannte Fall geprüft.
    if not validate_workout(plan).valid:
        raise SerializationError("Der Aufbau ist nicht vollständig speicherbar.")


def prepare_write(
    candidate: object,
    *,
    account_id: str = "default",
    athlete_id: str = "default",
) -> PreparedWrite:
    """Erzeugt einen zulässigen Schreibauftrag oder lehnt ihn begründet ab.

    Es gibt keinen Netzwerkaufruf. ``NoWriteNeeded`` bedeutet, dass der
    Entwurf keine fachliche Änderung gegenüber der Basis trägt. Beim Create
    gehört die stabile externe Identität vor dem ersten Request zum Payload;
    sie wird aus lokaler Plan-ID und Account/Athlet abgeleitet.
    """
    draft = _require_draft(candidate)
    current = draft.current
    base = draft.base

    validation = validate_draft(draft)
    if not validation.valid:
        raise SerializationError(
            "Der Entwurf ist nicht speicherbar: "
            + "; ".join(issue.message for issue in validation.issues)
        )

    if base is None:
        if current.remote_id is not None:
            raise SerializationError(
                "Ein neuer Entwurf darf keine bestehende Remote-ID tragen."
            )
        _assert_structure_supported(current, draft.base_source)
        workout_text = serialize_workout_text(current)
        external_id = (
            current.external_id
            or stable_external_id(
                current.local_id,
                account_id=account_id,
                athlete_id=athlete_id,
            )
        )
        payload = {
            "category": "WORKOUT",
            "type": current.sport,
            "name": current.name,
            "start_date_local": _start_date_local(current),
            "description": workout_text,
            "external_id": external_id,
        }
        return PreparedWrite(
            kind="create",
            mode="create",
            local_id=str(current.local_id),
            remote_id=None,
            payload=payload,
            workout_text=workout_text,
            external_id=external_id,
            controlled_fields=CONTROLLED_REMOTE_FIELDS + CREATE_ONLY_REMOTE_FIELDS,
        )

    if current.remote_id is None or base.remote_id is None:
        raise SerializationError("Ein bestehender Entwurf braucht seine Remote-ID.")
    if current.remote_id != base.remote_id:
        raise SerializationError(
            "Die Remote-ID darf beim Bearbeiten nicht gewechselt werden."
        )
    if current.sport != base.sport:
        raise SerializationError(
            "Die Sportart einer bestehenden Einheit ist in dieser Version nicht editierbar."
        )

    name_changed = current.name != base.name
    date_changed = current.date != base.date
    structure_changed = current.nodes != base.nodes
    if not name_changed and not date_changed and not structure_changed:
        raise NoWriteNeeded("Der Entwurf enthält keine schreibrelevante Änderung.")

    payload: dict[str, Any] = {}
    if name_changed:
        payload["name"] = current.name
    if date_changed:
        payload["start_date_local"] = _start_date_local(current)
    workout_text: str | None = None
    if structure_changed:
        _assert_structure_supported(current, draft.base_source)
        workout_text = serialize_workout_text(current)
        payload["description"] = workout_text

    return PreparedWrite(
        kind="update",
        mode="structure" if structure_changed else "metadata",
        local_id=str(current.local_id),
        remote_id=str(current.remote_id),
        payload=payload,
        workout_text=workout_text,
    )


# Sprechender Alias für Aufrufer, die den Payload ausdrücklich nennen wollen.
build_write_payload = prepare_write


__all__ = [
    "CONTROLLED_REMOTE_FIELDS",
    "CREATE_ONLY_REMOTE_FIELDS",
    "NoWriteNeeded",
    "PRESERVED_REMOTE_FIELDS",
    "PreparedWrite",
    "SerializationBoundaryError",
    "SerializationError",
    "build_write_payload",
    "prepare_write",
    "serialize_workout_text",
]
