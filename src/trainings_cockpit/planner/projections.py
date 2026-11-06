"""Gemeinsame Listenprojektion für Planungen und Aufzeichnungen.

Die Projektion ist keine dritte Datenquelle. Sie verweist entweder auf einen
Plan, auf die vorhandene kanonische Aktivität oder auf eine nachgewiesene
Beziehung. Eine Aktivitätsreferenz wird nie in eine Planung umgedeutet.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from .identities import (
    ActivityReference,
    PlanReference,
    RelationshipId,
)
from .primitives import LocalDate, require_local_date, require_time_zone


@dataclass(frozen=True, slots=True)
class TrainingRange:
    """Inklusive lokale Datumsgrenzen; keine UTC-Umrechnung."""

    start_date: LocalDate
    end_date: LocalDate
    time_zone: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "start_date", require_local_date(self.start_date, "start_date"))
        object.__setattr__(self, "end_date", require_local_date(self.end_date, "end_date"))
        object.__setattr__(self, "time_zone", require_time_zone(self.time_zone))
        if self.start_date > self.end_date:
            raise ValueError("start_date darf nicht nach end_date liegen.")

    def contains(self, day: LocalDate) -> bool:
        local_day = require_local_date(day, "day")
        return self.start_date <= local_day <= self.end_date

    @property
    def key(self) -> str:
        return f"range:{self.time_zone}:{self.start_date}:{self.end_date}"


@dataclass(frozen=True, slots=True)
class PlannedListEntry:
    date: LocalDate
    plan: PlanReference
    kind: ClassVar[str] = "planned"

    def __post_init__(self) -> None:
        object.__setattr__(self, "date", require_local_date(self.date))

    @property
    def key(self) -> str:
        return f"planned|{self.plan.key}"


@dataclass(frozen=True, slots=True)
class RecordedListEntry:
    date: LocalDate
    activity: ActivityReference
    kind: ClassVar[str] = "recorded"

    def __post_init__(self) -> None:
        object.__setattr__(self, "date", require_local_date(self.date))

    @property
    def key(self) -> str:
        return f"recorded|{self.activity.key}"


@dataclass(frozen=True, slots=True)
class LinkedListEntry:
    """Bestätigte Beziehung an einem tatsächlichen lokalen Aktivitätstag."""

    date: LocalDate
    plan: PlanReference
    activities: tuple[ActivityReference, ...]
    relationship_id: RelationshipId
    kind: ClassVar[str] = "linked"

    def __post_init__(self) -> None:
        object.__setattr__(self, "date", require_local_date(self.date))
        if not isinstance(self.relationship_id, RelationshipId):
            object.__setattr__(self, "relationship_id", RelationshipId(self.relationship_id))
        activities = tuple(self.activities)
        if not activities:
            raise ValueError("Ein linked-Eintrag braucht mindestens eine Aktivität.")
        if any(not isinstance(activity, ActivityReference) for activity in activities):
            raise ValueError("activities dürfen nur ActivityReference enthalten.")
        keys = [activity.key for activity in activities]
        if len(keys) != len(set(keys)):
            raise ValueError("Eine Aktivität darf in einem linked-Eintrag nur einmal vorkommen.")
        object.__setattr__(self, "activities", activities)

    @property
    def key(self) -> str:
        return f"linked|{self.relationship_id}"


@dataclass(frozen=True, slots=True)
class CompletionReferenceListEntry:
    """Erledigt-Hinweis am ursprünglichen Plantermin, ohne Ist-Kennzahlen."""

    date: LocalDate
    plan: PlanReference
    activity_dates: tuple[LocalDate, ...]
    relationship_id: RelationshipId
    kind: ClassVar[str] = "completionReference"

    def __post_init__(self) -> None:
        object.__setattr__(self, "date", require_local_date(self.date))
        if not isinstance(self.relationship_id, RelationshipId):
            object.__setattr__(self, "relationship_id", RelationshipId(self.relationship_id))
        dates = tuple(require_local_date(day, "activity_dates") for day in self.activity_dates)
        if not dates:
            raise ValueError("Eine completionReference braucht mindestens ein Aktivitätsdatum.")
        if len(dates) != len(set(dates)):
            raise ValueError("activity_dates dürfen sich nicht wiederholen.")
        object.__setattr__(self, "activity_dates", dates)

    @property
    def key(self) -> str:
        return f"completionReference|{self.relationship_id}"


type TrainingListEntry = (
    PlannedListEntry | RecordedListEntry | LinkedListEntry | CompletionReferenceListEntry
)


class RelationshipStatus(StrEnum):
    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    OPEN = "open"


@dataclass(frozen=True, slots=True)
class TrainingRelationship:
    """Explizite Beziehung; Abschluss ist eine eigene, bestätigte Aussage."""

    relationship_id: RelationshipId
    plan: PlanReference
    activities: tuple[ActivityReference, ...]
    status: RelationshipStatus = RelationshipStatus.CONFIRMED
    completion_confirmed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.relationship_id, RelationshipId):
            object.__setattr__(self, "relationship_id", RelationshipId(self.relationship_id))
        if not isinstance(self.plan, PlanReference):
            raise ValueError("plan muss eine PlanReference sein.")
        if not isinstance(self.status, RelationshipStatus):
            object.__setattr__(self, "status", RelationshipStatus(self.status))
        activities = tuple(self.activities)
        if not activities:
            raise ValueError("Eine Beziehung braucht mindestens eine Aktivität.")
        if any(not isinstance(activity, ActivityReference) for activity in activities):
            raise ValueError("activities dürfen nur ActivityReference enthalten.")
        keys = [activity.key for activity in activities]
        if len(keys) != len(set(keys)):
            raise ValueError(
                "Eine kanonische Aktivität darf in einer Beziehung nur einmal zählen."
            )
        object.__setattr__(self, "activities", activities)
        if self.completion_confirmed and self.status is not RelationshipStatus.CONFIRMED:
            raise ValueError("Ein bestätigter Abschluss braucht eine bestätigte Beziehung.")

    @property
    def is_complete(self) -> bool:
        return self.status is RelationshipStatus.CONFIRMED and self.completion_confirmed

    @property
    def relationship_key(self) -> str:
        return f"relationship:{self.plan.account_id}:{self.plan.athlete_id}:{self.relationship_id}"


class RelationshipProjectionError(ValueError):
    """Eine Beziehung verweist auf eine Aktivität ohne bekannten tatsächlichen Tag."""


def relationship_entries(
    relationship: TrainingRelationship,
    plan_date: LocalDate,
    activity_dates: Mapping[str, LocalDate],
) -> tuple[TrainingListEntry, ...]:
    """Projiziert eine **bestätigte** Beziehung in die gemeinsame Wochenliste.

    Jede Aktivität bleibt an ihrem tatsächlichen lokalen Tag. Liegt der
    Plantermin in keiner dieser Tagesgruppen, entsteht am ursprünglichen
    Plantermin zusätzlich eine reine ``completionReference`` ohne Ist-Werte.
    Eine offene oder teilweise Beziehung erzeugt hier bewusst keinen
    Erledigt-Eintrag; der Aufrufer stellt Plan und Aufzeichnungen dann getrennt
    dar.
    """
    if not relationship.is_complete:
        return ()
    target = require_local_date(plan_date, "plan_date")
    grouped: dict[str, list[ActivityReference]] = {}
    missing: list[str] = []
    for activity in relationship.activities:
        day = activity_dates.get(activity.key)
        if day is None:
            missing.append(activity.key)
            continue
        grouped.setdefault(require_local_date(day, "activity_dates"), []).append(activity)
    if missing:
        raise RelationshipProjectionError(
            "Unbekannte Aktivitätstage für: " + ", ".join(sorted(missing))
        )

    entries: list[TrainingListEntry] = [
        LinkedListEntry(
            date=day,
            plan=relationship.plan,
            activities=tuple(grouped[day]),
            relationship_id=relationship.relationship_id,
        )
        for day in sorted(grouped)
    ]
    if target not in grouped:
        entries.append(
            CompletionReferenceListEntry(
                date=target,
                plan=relationship.plan,
                activity_dates=tuple(sorted(grouped)),
                relationship_id=relationship.relationship_id,
            )
        )
    return tuple(entries)


def list_entry_key(entry: TrainingListEntry) -> str:
    """Typisierter Schlüssel; Plan 123 und Aktivität 123 kollidieren nicht."""
    if not isinstance(
        entry,
        (PlannedListEntry, RecordedListEntry, LinkedListEntry, CompletionReferenceListEntry),
    ):
        raise TypeError("Unbekannter Listeneintrag.")
    return entry.key


__all__ = [
    "CompletionReferenceListEntry",
    "LinkedListEntry",
    "PlannedListEntry",
    "RecordedListEntry",
    "RelationshipProjectionError",
    "RelationshipStatus",
    "TrainingListEntry",
    "TrainingRange",
    "TrainingRelationship",
    "list_entry_key",
    "relationship_entries",
]

