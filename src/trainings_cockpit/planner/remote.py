"""Lesender Remote-Adapter für intervals.icu-Event-Rohdaten.

Der Adapter liest ausschließlich: Er bekommt das bereits vom vorhandenen
``IntervalsClient.events()`` gelieferte Event-Dict und erzeugt daraus das
Planungsmodell samt unverändertem :class:`SourceSnapshot`. Es gibt hier keinen
Netzwerkaufruf und keinen Schreibpfad.

Grundregeln:

* Eine Distanz plus berechnete Dauer bleibt ein Distanzabschnitt, wenn die
  Quelle die Dauer als Schätzung kennzeichnet.
* Was das Modell nicht eindeutig abbilden kann (Rampe, Lap-Taste, mehrere
  Ziele, Trittfrequenz, unbekannte Dokumentfelder), wird als
  :class:`UnsupportedNode` mit Quellreferenz erhalten. Der Rohinhalt bleibt
  vollständig im Snapshot; die Struktur wird nur noch eingeschränkt editierbar.
* Aufzeichnungen werden hier nie als :class:`PlannedWorkout` dekodiert. Für
  sie gibt es nur die Referenz-/Listeneintrags-Brücke auf den vorhandenen
  Aktivitätslesepfad.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .identities import (
    ActivityId,
    ActivityReference,
    NodeId,
    PlanId,
    RemoteEventId,
    SourceActivityRef,
)
from .model import (
    DistanceEnd,
    Editability,
    NoTarget,
    PaceTarget,
    PaceUnit,
    PlannedWorkout,
    PowerTarget,
    PowerUnit,
    RepeatNode,
    RestrictionCode,
    SourceSnapshot,
    StepNode,
    StepRole,
    TimeEnd,
    UnsupportedNode,
    Value,
    ValueRange,
    ZoneMetric,
    ZoneTarget,
    role_from_name,
)
from .primitives import LocalDate, require_local_date, require_text, require_time_zone
from .projections import RecordedListEntry

#: Bekannte Dokumentfelder, die der Adapter fachlich liest. Alles andere im
#: `workout_doc` bleibt im Snapshot; nur ein Feld außerhalb dieser Menge und
#: außerhalb der berechneten `_DERIVED_DOC_FIELDS` begrenzt die Strukturbearbeitung.
_KNOWN_DOC_FIELDS = {"steps", "notes", "name", "description", "type"}

#: Felder, die intervals.icu selbst bei jedem `workout_doc` **berechnet** und
#: zurückliefert — der Nutzer hat sie nicht verfasst. Es sind Zusammenfassungen
#: über das ganze Workout (Summen aus Dauer/Distanz, Zonenzeiten, Belastungs-
#: und Leistungskennzahlen sowie leere Hüllfelder wie `locales`/`options`), keine
#: Abschnitte und keine Schreibabsicht. Sie stehen nicht im Schreibvertrag: der
#: Serializer sendet nur `name`, `start_date_local`, `description`, `type`,
#: `category` und `external_id` (siehe SERIALIZER-VERTRAG.md, Abschnitt 1).
#: Deshalb dürfen sie die Strukturbearbeitung nicht begrenzen; sie bleiben
#: unverändert im Roh-Snapshot erhalten.
_DERIVED_DOC_FIELDS = frozenset(
    {
        "locales",
        "options",
        "distance",
        "duration",
        "zoneTimes",
        "strain_score",
        "average_watts",
        "normalized_power",
        "variability_index",
        "polarization_index",
    }
)

_SPECIAL_FIELDS = {
    "ramp": "Rampe",
    "lap_button": "Lap-Taste",
    "cadence": "Trittfrequenz",
    "targets": "mehrere Ziele",
    "extra_instruction": "Zusatzanweisung",
}

_SPORT_FAMILY = {
    "Run": "run",
    "VirtualRun": "run",
    "TrailRun": "run",
    "Ride": "ride",
    "VirtualRide": "ride",
    "EBikeRide": "ride",
    "GravelRide": "ride",
    "MountainBikeRide": "ride",
    "Swim": "swim",
    "OpenWaterSwim": "swim",
}

class NotAPlannedWorkout(ValueError):
    """Der Datensatz ist kein geplantes Workout und darf keines werden."""


@dataclass(frozen=True, slots=True)
class RemoteWorkout:
    """Ein gelesenes Event: Fachmodell und unveränderte Herkunft."""

    plan: PlannedWorkout
    source: SourceSnapshot


@dataclass(slots=True)
class _ParseState:
    restrictions: set[RestrictionCode] = field(default_factory=set)
    reasons: list[str] = field(default_factory=list)
    nested_repeat: bool = False

    def restrict(self, code: RestrictionCode, reason: str) -> None:
        self.restrictions.add(code)
        if reason not in self.reasons:
            self.reasons.append(reason)


def sport_label(sport: str | None, labels: Mapping[str, str] | None = None) -> str:
    """Neutrales Label; eine unbekannte Sportart stürzt nicht den Tag ab.

    Die vorhandene Anzeige kennt bereits eine Labeltabelle. Sie wird hier
    wiederverwendet, ohne den unbekannten Rest auf den Rohcode zu reduzieren.
    """
    if not sport:
        return "Andere Sportart"
    if labels is None:
        from ..plan import SPORT_LABELS

        labels = SPORT_LABELS
    return labels.get(sport, "Andere Sportart")


def read_remote_event(
    event: Mapping[str, Any],
    *,
    fetched_at: str,
    time_zone: str,
    account_id: str = "default",
    athlete_id: str = "default",
    zone_sets: Mapping[str, str] | None = None,
    writable: bool | None = None,
) -> RemoteWorkout:
    """Liest ein Event-Dict in das Planungsmodell, ohne es zu verändern.

    ``zone_sets`` bildet eine Sportart auf die String-ID ihres HF-Zonensatzes
    ab (beispielsweise ``{"Run": "run-hr"}``). Fehlt die Zuordnung, entsteht
    eine stabile, aus der Sportfamilie abgeleitete ID; die Rohzahl bleibt im
    Snapshot erhalten. ``writable=False`` bildet ein nachgewiesenes fehlendes
    Remote-Schreibrecht ab.
    """
    if not isinstance(event, Mapping):
        raise ValueError("Ein Event muss ein Mapping sein.")
    category = event.get("category")
    if category is not None and str(category).upper() != "WORKOUT":
        raise NotAPlannedWorkout(
            f"Nur geplante WORKOUT-Events werden gelesen, erhalten: {category!r}."
        )
    zone = require_time_zone(time_zone)
    remote_id = _event_id(event)
    day, local_time = _local_terminus(event)
    source = SourceSnapshot.capture(
        remote_id=remote_id,
        raw=dict(event),
        fetched_at=fetched_at,
        remote_updated_at=_optional_timestamp(event.get("updated") or event.get("updated_at")),
        remote_version=_optional_text(event.get("version")),
    )

    state = _ParseState()
    doc = event.get("workout_doc")
    if doc is None:
        nodes: tuple[Any, ...] = ()
    elif not isinstance(doc, Mapping):
        state.restrict(RestrictionCode.UNKNOWN_CONTENT, "workout_doc ist kein Objekt.")
        nodes = (
            UnsupportedNode(
                id=_node_id(remote_id, "/workout_doc"),
                label="Unbekannter Aufbau",
                reason="workout_doc ist kein Objekt.",
                source_ref="/workout_doc",
            ),
        )
    else:
        steps = doc.get("steps")
        if steps is None:
            nodes = ()
        elif not isinstance(steps, list):
            state.restrict(RestrictionCode.UNKNOWN_CONTENT, "workout_doc.steps ist keine Liste.")
            nodes = (
                UnsupportedNode(
                    id=_node_id(remote_id, "/workout_doc/steps"),
                    label="Unbekannter Aufbau",
                    reason="workout_doc.steps ist keine Liste.",
                    source_ref="/workout_doc/steps",
                ),
            )
        else:
            parsed = [
                _parse_node(
                    step,
                    remote_id,
                    f"/workout_doc/steps/{index}",
                    0,
                    state,
                    event,
                    zone_sets,
                )
                for index, step in enumerate(steps)
            ]
            nodes = tuple(parsed)
        # Nur ein Feld, das weder fachlich gelesen noch von intervals berechnet
        # ist, ist wirklich unbekannt; berechnete Werte begrenzen die
        # Editierbarkeit nicht, sie bleiben nur im Snapshot.
        unknown_doc = sorted(set(doc) - _KNOWN_DOC_FIELDS - _DERIVED_DOC_FIELDS)
        if unknown_doc:
            state.restrict(
                RestrictionCode.UNKNOWN_CONTENT,
                "Unbekannte Dokumentfelder: " + ", ".join(str(key) for key in unknown_doc),
            )

    notes = doc.get("notes") if isinstance(doc, Mapping) else None
    if not isinstance(notes, str):
        notes = event.get("notes") if isinstance(event.get("notes"), str) else None

    sport = _sport(event)
    read_only = writable is False or _truthy(event.get("read_only")) or _falsey(
        event.get("athlete_can_edit")
    )
    editability = Editability.FULL
    reason: str | None = None
    codes = set(state.restrictions)
    if read_only:
        editability = Editability.READ_ONLY
        codes.add(RestrictionCode.REMOTE_READ_ONLY)
        reason = "Die Remote-Quelle meldet kein Schreibrecht für dieses Event."
    elif codes:
        editability = Editability.METADATA_ONLY
        reason = " ".join(state.reasons) or "Der Aufbau enthält nicht sicher abbildbare Inhalte."

    plan = PlannedWorkout(
        local_id=PlanId(f"plan:event:{remote_id}"),
        remote_id=remote_id,
        external_id=_optional_text(event.get("external_id")),
        name=str(event.get("name") or ""),
        sport=sport,
        date=day,
        local_time=local_time,
        time_zone=zone,
        nodes=nodes,
        notes=notes,
        editability=editability,
        editability_reason=reason,
        restriction_codes=tuple(sorted(codes, key=lambda code: code.value)),
    )
    return RemoteWorkout(plan=plan, source=source)


def activity_reference_from_record(
    record: Mapping[str, Any],
    *,
    account_id: str,
    athlete_id: str,
) -> ActivityReference:
    """Brücke auf den vorhandenen Aktivitätslesepfad, kein Plan-Objekt.

    ``activityId`` gewinnt vor der Quell-ID, damit ein bereits kanonisch
    zugeordneter Datensatz nicht über eine zufällige Quelle umbenannt wird.
    Mehrere Quellabbilder bleiben als ``source_refs`` erhalten.
    """
    if not isinstance(record, Mapping):
        raise ValueError("Eine Aufzeichnung muss ein Mapping sein.")
    canonical = record.get("activityId") or record.get("activity_id")
    if canonical is None:
        canonical = record.get("source_id") or record.get("id")
    if canonical is None:
        raise ValueError("Die Aufzeichnung trägt keine kanonische Aktivitäts-ID.")
    refs = _source_refs(record)
    return ActivityReference(
        ActivityId(str(canonical)),
        require_text(account_id, "account_id"),
        require_text(athlete_id, "athlete_id"),
        source_refs=refs,
    )


def activity_date(record: Mapping[str, Any]) -> LocalDate:
    """Der tatsächliche lokale Aktivitätstag, nie der Plantermin."""
    value = record.get("date")
    if value is None:
        start = record.get("start_local") or record.get("start_date_local") or record.get("start")
        if start is None:
            raise ValueError("Die Aufzeichnung trägt kein lokales Datum.")
        value = str(start)[:10]
    return require_local_date(value, "date")


def recorded_entry_from_record(
    record: Mapping[str, Any],
    *,
    account_id: str,
    athlete_id: str,
) -> RecordedListEntry:
    """Ein Anzeigeeintrag am tatsächlichen Datum der Aufzeichnung."""
    return RecordedListEntry(
        activity_date(record),
        activity_reference_from_record(record, account_id=account_id, athlete_id=athlete_id),
    )


def _event_id(event: Mapping[str, Any]) -> RemoteEventId:
    value = event.get("id")
    if value is None or isinstance(value, bool) or str(value).strip() == "":
        raise ValueError("Ein Remote-Event braucht eine nichtleere id.")
    return RemoteEventId(value)


def _local_terminus(event: Mapping[str, Any]) -> tuple[LocalDate, str | None]:
    raw = event.get("start_date_local") or event.get("start_date")
    if raw is None:
        raise ValueError("Ein Remote-Event braucht start_date_local.")
    text = str(raw)
    day = require_local_date(text[:10], "start_date_local")
    local_time: str | None = None
    if "T" in text:
        clock = text.split("T", 1)[1][:8]
        # intervals führt ganzTägige Events als 00:00:00. Daraus darf keine
        # erfundene Uhrzeit werden; eine echte Uhrzeit bleibt erhalten.
        if clock[:5] != "00:00":
            local_time = clock[:5]
    return day, local_time


def _sport(event: Mapping[str, Any]) -> str:
    value = event.get("type") or event.get("sport") or "Other"
    return require_text(value, "sport")


def _parse_node(
    raw: object,
    remote_id: RemoteEventId,
    path: str,
    depth: int,
    state: _ParseState,
    event: Mapping[str, Any],
    zone_sets: Mapping[str, str] | None,
) -> object:
    if not isinstance(raw, Mapping):
        state.restrict(RestrictionCode.UNKNOWN_CONTENT, f"{path} ist kein Objekt.")
        return UnsupportedNode(
            id=_node_id(remote_id, path),
            label="Unbekannter Schritt",
            reason="Der Schritt ist kein Objekt.",
            source_ref=path,
        )

    if isinstance(raw.get("steps"), list):
        return _parse_repeat(raw, remote_id, path, depth, state, event, zone_sets)

    special = [label for key, label in _SPECIAL_FIELDS.items() if _present(raw.get(key))]
    if special:
        labels = ", ".join(special)
        state.restrict(
            RestrictionCode.UNKNOWN_CONTENT,
            f"{path}: nicht abbildbare Angaben ({labels}).",
        )
        if "mehrere Ziele" in labels:
            state.restrict(RestrictionCode.MULTIPLE_TARGETS, f"{path}: mehrere Ziele.")
        if "Rampe" in labels or "Lap-Taste" in labels:
            state.restrict(RestrictionCode.RAMP_OR_SPECIAL_STEP, f"{path}: {labels}.")
        return UnsupportedNode(
            id=_node_id(remote_id, path),
            label=str(raw.get("text") or "Spezialschritt"),
            reason=f"Nicht abbildbare Angaben: {labels}.",
            source_ref=path,
        )

    end = _parse_end(raw, remote_id, path, state)
    if isinstance(end, UnsupportedNode):
        return end
    target = _parse_target(raw, remote_id, path, state, event, zone_sets)
    if isinstance(target, UnsupportedNode):
        return target

    return StepNode(
        id=_node_id(remote_id, path),
        name=str(raw.get("text") or raw.get("name") or ""),
        role=_role(raw),
        end=end,
        target=target,
        notes=_optional_text(raw.get("notes")),
        source_ref=path,
    )


def _parse_repeat(
    raw: Mapping[str, Any],
    remote_id: RemoteEventId,
    path: str,
    depth: int,
    state: _ParseState,
    event: Mapping[str, Any],
    zone_sets: Mapping[str, str] | None,
) -> RepeatNode | UnsupportedNode:
    if depth > 0:
        state.nested_repeat = True
        state.restrict(
            RestrictionCode.UNKNOWN_CONTENT,
            f"{path}: verschachtelte Wiederholung; die erste Editorversion öffnet nur eine Ebene.",
        )
    try:
        repetitions = _positive_int(raw.get("reps", 1))
    except ValueError as exc:
        state.restrict(RestrictionCode.UNKNOWN_CONTENT, f"{path}: {exc}")
        return UnsupportedNode(
            id=_node_id(remote_id, path),
            label=str(raw.get("text") or "Unklare Wiederholung"),
            reason=str(exc),
            source_ref=path,
        )
    children_raw = raw.get("steps")
    children = tuple(
        _parse_node(child, remote_id, f"{path}/steps/{index}", depth + 1, state, event, zone_sets)
        for index, child in enumerate(children_raw if isinstance(children_raw, list) else [])
    )
    skip = _truthy(raw.get("skip_final_recovery")) or _truthy(raw.get("skipFinalRecovery"))
    return RepeatNode(
        id=_node_id(remote_id, path),
        name=str(raw.get("text") or raw.get("name") or "Wiederholung"),
        repetitions=repetitions,
        children=children,
        skip_final_recovery=skip,
        source_ref=path,
    )


def _parse_end(
    raw: Mapping[str, Any],
    remote_id: RemoteEventId,
    path: str,
    state: _ParseState,
) -> TimeEnd | DistanceEnd | UnsupportedNode:
    duration = _number(raw.get("duration"))
    distance = _number(raw.get("distance"))
    duration_source = str(raw.get("duration_source") or "").lower()
    distance_source = str(raw.get("distance_source") or "").lower()

    if distance is not None and distance > 0:
        if duration is not None and duration > 0:
            # Beide Werte vorhanden: Eine ausdrückliche Quellenangabe sagt,
            # welche Größe die Ende-Bedingung ist. `duration_source=estimated`
            # ist der belegte F04-Fall: die vorgegebene Distanz bleibt das
            # Ende, die Dauer ist die berechnete Schätzung.
            # `distance_source=estimated` ist der umgekehrte Fall einer
            # Zeitvorgabe, deren Strecke intervals geschätzt hat.
            if duration_source in {"estimated", "distance"}:
                return DistanceEnd(distance)
            if distance_source == "estimated":
                return TimeEnd(duration)
            if not duration_source and not distance_source:
                # Die echte intervals-API nennt bei einer vom Nutzer
                # vorgegebenen Distanz gar keine Quelle: der Distanzschritt
                # kommt als `{"distance": 8000, "duration": 3235}` zurück.
                # Bei einer Zeitvorgabe liefert sie dagegen nur die Dauer,
                # etwa `{"duration": 600}` für einen Zeitabschnitt oder
                # `{"duration": 2700}` für 45 Minuten Rad. Treffen beide
                # Werte ohne Quelle zusammen, ist deshalb die Distanz die
                # vorgegebene Ende-Bedingung und die Dauer die von intervals
                # berechnete Schätzung; eine Schätzung darf das Ende nie
                # bestimmen.
                return DistanceEnd(distance)
            state.restrict(
                RestrictionCode.UNKNOWN_CONTENT,
                f"{path}: Distanz und Dauer ohne eindeutige Ende-Bedingung.",
            )
            return UnsupportedNode(
                id=_node_id(remote_id, path),
                label=str(raw.get("text") or "Unklarer Abschnitt"),
                reason="Distanz und Dauer sind vorhanden, die Ende-Bedingung ist nicht belegt.",
                source_ref=path,
            )
        return DistanceEnd(distance)
    if duration is not None and duration > 0:
        return TimeEnd(duration)

    state.restrict(
        RestrictionCode.UNKNOWN_CONTENT,
        f"{path}: keine bekannte Zeit- oder Distanz-Endebedingung.",
    )
    return UnsupportedNode(
        id=_node_id(remote_id, path),
        label=str(raw.get("text") or "Offener Abschnitt"),
        reason="Weder Dauer noch Distanz sind als Ende-Bedingung belegt.",
        source_ref=path,
    )


def _parse_target(
    raw: Mapping[str, Any],
    remote_id: RemoteEventId,
    path: str,
    state: _ParseState,
    event: Mapping[str, Any],
    zone_sets: Mapping[str, str] | None,
):
    fields = [name for name in ("power", "hr", "pace") if isinstance(raw.get(name), Mapping)]
    if len(fields) > 1:
        state.restrict(RestrictionCode.MULTIPLE_TARGETS, f"{path}: mehrere Zielarten.")
        return UnsupportedNode(
            id=_node_id(remote_id, path),
            label=str(raw.get("text") or "Mehrere Ziele"),
            reason="Mehrere Zielarten in einem Schritt sind nicht verlustfrei abbildbar.",
            source_ref=path,
        )
    if not fields:
        return NoTarget()

    name = fields[0]
    target = raw[name]
    assert isinstance(target, Mapping)
    remote_id = RemoteEventId(event.get("id"))
    if name == "hr":
        return _parse_hr(target, remote_id, path, state, event, zone_sets)
    if name == "power":
        return _parse_power(target, remote_id, path, state)
    return _parse_pace(target, remote_id, path, state, event)


def _parse_hr(
    raw: Mapping[str, Any],
    remote_id: RemoteEventId,
    path: str,
    state: _ParseState,
    event: Mapping[str, Any],
    zone_sets: Mapping[str, str] | None,
):
    units = str(raw.get("units") or "").lower()
    value = raw.get("value")
    if units in {"hr_zone", "zone"} and value is not None:
        try:
            number = _positive_int(value)
        except ValueError as exc:
            state.restrict(RestrictionCode.UNKNOWN_CONTENT, f"{path}: {exc}")
            return UnsupportedNode(
                id=_node_id(remote_id, path),
                label="Unbekanntes HF-Ziel",
                reason=str(exc),
                source_ref=path,
            )
        zone_set = (zone_sets or {}).get(str(event.get("type") or ""))
        if not zone_set:
            zone_set = f"{_sport_slug(str(event.get('type') or ''))}-hr"
        return ZoneTarget(
            metric=ZoneMetric.HEART_RATE,
            zone_id=f"{zone_set}-{number}",
            zone_set_id=zone_set,
        )
    state.restrict(
        RestrictionCode.UNKNOWN_CONTENT,
        f"{path}: HF-Ziel ohne belegte Zonenreferenz.",
    )
    return UnsupportedNode(
        id=_node_id(remote_id, path),
        label="Unbekanntes HF-Ziel",
        reason="Nur HF-Zonen mit Zonenreferenz sind im vorhandenen Vertrag belegt.",
        source_ref=path,
    )


def _parse_power(
    raw: Mapping[str, Any],
    remote_id: RemoteEventId,
    path: str,
    state: _ParseState,
):
    units = str(raw.get("units") or "").lower()
    values = _value_spec(raw, path, state)
    if values is None:
        return NoTarget()
    if isinstance(values, UnsupportedNode):
        return values
    if units in {"w", "watts", "watt"}:
        return PowerTarget(unit=PowerUnit.WATTS, values=values)
    if units in {"%ftp", "%", "percentftp", "percent_ftp"}:
        return PowerTarget(unit=PowerUnit.PERCENT_FTP, values=values)
    state.restrict(
        RestrictionCode.UNKNOWN_CONTENT,
        f"{path}: unbekannte Leistungseinheit {units!r}.",
    )
    return UnsupportedNode(
        id=_node_id(remote_id, path),
        label="Unbekanntes Leistungsziel",
        reason=f"Leistungseinheit {units!r} ist nicht belegt.",
        source_ref=path,
    )


def _parse_pace(
    raw: Mapping[str, Any],
    remote_id: RemoteEventId,
    path: str,
    state: _ParseState,
    event: Mapping[str, Any],
):
    units = str(raw.get("units") or "").strip().lower()
    if units.startswith("secs"):
        # intervals.icu liefert absolute Pace in Sekunden je Referenzstrecke:
        # ``secs`` ohne Angabe, sonst ``secs/km``, ``secs/100m`` usw. Die
        # Referenzstrecke steht entweder in der Einheit oder in den
        # Sporteinstellungen der Quelle (Schwimmen je 100 m, sonst je km).
        unit = _pace_seconds_unit(units, _sport(event))
        if unit is None:
            state.restrict(
                RestrictionCode.UNKNOWN_CONTENT,
                f"{path}: unbekannte Pace-Referenz in {units!r}.",
            )
            return UnsupportedNode(
                id=_node_id(remote_id, path),
                label="Unbekanntes Pace-Ziel",
                reason=f"Pace-Einheit {units!r} ist nicht belegt.",
                source_ref=path,
            )
        factor = 1.0
    elif units in {"min/km", "min_per_km", "pace"}:
        unit = PaceUnit.SECONDS_PER_KM
        factor = 60.0
    elif units in {"min/100m", "min_per_100m", "min/100", "/100m"}:
        unit = PaceUnit.SECONDS_PER_100M
        factor = 60.0
    else:
        state.restrict(
            RestrictionCode.UNKNOWN_CONTENT,
            f"{path}: unbekannte Pace-Einheit {units!r}.",
        )
        return UnsupportedNode(
            id=_node_id(remote_id, path),
            label="Unbekanntes Pace-Ziel",
            reason=f"Pace-Einheit {units!r} ist nicht belegt.",
            source_ref=path,
        )
    values = _value_spec(raw, path, state, factor=factor, allow_value=True)
    if values is None:
        return NoTarget()
    return PaceTarget(unit=unit, values=values)


def _pace_seconds_unit(units: str, sport: str | None) -> PaceUnit | None:
    """Referenzstrecke einer ``secs``-Einheit als kanonische Pace-Einheit."""
    _, slash, reference = units.partition("/")
    if reference in {"km", "kilometer"}:
        return PaceUnit.SECONDS_PER_KM
    if reference in {"100m", "100"}:
        return PaceUnit.SECONDS_PER_100M
    if reference:
        return None
    # Ohne ausdrückliche Referenz gilt die Sporteinstellung von intervals:
    # Schwimmen rechnet je 100 m, alle anderen Sportarten je Kilometer.
    return (
        PaceUnit.SECONDS_PER_100M
        if _SPORT_FAMILY.get(sport or "") == "swim"
        else PaceUnit.SECONDS_PER_KM
    )


def _value_spec(
    raw: Mapping[str, Any],
    path: str,
    state: _ParseState,
    *,
    factor: float = 1.0,
    allow_value: bool = False,
) -> Value | ValueRange | UnsupportedNode | None:
    start = _number(raw.get("start"))
    end = _number(raw.get("end"))
    single = _number(raw.get("value")) if allow_value else None
    if start is None and end is None and single is None:
        return None
    if start is not None and end is not None:
        low, high = sorted((start * factor, end * factor))
        if low != high:
            return ValueRange(low, high)
        return Value(low)
    chosen = start if start is not None else end if end is not None else single
    assert chosen is not None
    return Value(chosen * factor)


def _role(raw: Mapping[str, Any]) -> StepRole:
    intensity = str(raw.get("intensity") or "").strip().lower()
    if intensity in {"warmup", "active", "rest", "cooldown"}:
        return {
            "warmup": StepRole.WARMUP,
            "active": StepRole.WORK,
            "rest": StepRole.RECOVERY,
            "cooldown": StepRole.COOLDOWN,
        }[intensity]
    if _truthy(raw.get("warmup")):
        return StepRole.WARMUP
    if _truthy(raw.get("cooldown")):
        return StepRole.COOLDOWN
    return role_from_name(raw.get("text") or raw.get("name"))


def _node_id(remote_id: RemoteEventId, path: str) -> NodeId:
    safe = re.sub(r"[^A-Za-z0-9_.:-]+", "-", path).strip("-")
    return NodeId(f"node:event:{remote_id}:{safe}")


def _source_refs(record: Mapping[str, Any]) -> tuple[SourceActivityRef, ...]:
    refs: list[SourceActivityRef] = []
    raw_refs = record.get("sourceRefs") or record.get("source_refs") or []
    if isinstance(raw_refs, Iterable) and not isinstance(raw_refs, (str, bytes, Mapping)):
        for item in raw_refs:
            if not isinstance(item, Mapping):
                continue
            source = item.get("source") or item.get("source_name")
            source_id = item.get("sourceId") or item.get("source_id")
            if source and source_id is not None:
                refs.append(SourceActivityRef(str(source), str(source_id)))
    source = record.get("source")
    source_id = record.get("source_id")
    if source and source_id is not None:
        refs.append(SourceActivityRef(str(source), str(source_id)))
    unique = {ref.key: ref for ref in refs}
    return tuple(unique[key] for key in sorted(unique))


def _sport_slug(sport: str) -> str:
    known = _SPORT_FAMILY.get(sport)
    return known or re.sub(r"[^a-z0-9]+", "-", sport.lower()).strip("-") or "other"


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive_int(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("Der Wert muss eine positive ganze Zahl sein.")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Der Wert muss eine positive ganze Zahl sein.") from exc
    if number < 1:
        raise ValueError("Der Wert muss mindestens 1 sein.")
    return number


def _present(value: object) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, (str, list, tuple, dict)) and len(value) == 0:
        return False
    return True


def _truthy(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "ja"}
    return bool(value)


def _falsey(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"0", "false", "no", "nein"}
    return value is False


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_timestamp(value: object) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    # Nur ein tatsächlich mit Zeitzone versehener Wert ist ein belastbarer
    # Remote-Zeitpunkt; sonst lieber nichts behaupten.
    if "T" not in text or not (text.endswith("Z") or "+" in text[10:] or "-" in text[10:]):
        return None
    return text


__all__ = [
    "NotAPlannedWorkout",
    "RemoteWorkout",
    "activity_date",
    "activity_reference_from_record",
    "read_remote_event",
    "recorded_entry_from_record",
    "sport_label",
]
