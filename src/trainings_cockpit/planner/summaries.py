"""Ist-Summen, offene Planung und die gemeinsame Wochenprojektion.

Die Ist-Dauer kommt aus derselben Definition wie im bestehenden Dashboard:
Bewegungszeit, sonst verstrichene Dauer. Diese Basis wird hier nicht neu
erfunden. Eine kanonische Aktivität zählt genau einmal an ihrem tatsächlichen
lokalen Datum; Verknüpfungsreferenzen und abgeschlossene Planungen werden
nicht zusätzlich als offene Planung addiert.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .identities import ActivityReference, PlanReference
from .model import PlannedWorkout
from .primitives import LocalDate, require_local_date
from .projections import (
    CompletionReferenceListEntry,
    LinkedListEntry,
    PlannedListEntry,
    RecordedListEntry,
    RelationshipProjectionError,
    TrainingListEntry,
    TrainingRange,
    TrainingRelationship,
    list_entry_key,
    relationship_entries,
)
from .remote import activity_date, activity_reference_from_record
from .validation import KnownTotals, calculate_known_totals


def recorded_seconds(value: Mapping[str, Any] | RecordedActivity) -> float:
    """Die bestehende Ist-Dauerdefinition, zentral für alle Verbraucher.

    ``moving`` gewinnt vor ``duration``; ein fehlender Wert ist 0, aber eine
    vorhandene 0 bleibt 0. Schätzungen kommen hier nicht hinein.
    """
    if isinstance(value, RecordedActivity):
        return value.seconds
    moving = value.get("moving_s")
    if moving is None:
        moving = value.get("movingSeconds")
    if moving:
        return float(moving)
    duration = value.get("duration_s")
    if duration is None:
        duration = value.get("durationSeconds")
    return float(duration) if duration is not None else 0.0


def recorded_load(value: Mapping[str, Any] | RecordedActivity) -> float:
    if isinstance(value, RecordedActivity):
        return float(value.load or 0)
    load = value.get("load")
    if load is None:
        load = value.get("icu_training_load")
    return float(load) if load is not None else 0.0


@dataclass(frozen=True, slots=True)
class RecordedActivity:
    """Eine bereits kanonische Aufzeichnung an ihrem tatsächlichen Tag."""

    reference: ActivityReference
    date: LocalDate
    seconds: float
    load: float | None = None
    name: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.reference, ActivityReference):
            raise ValueError("reference muss eine ActivityReference sein.")
        object.__setattr__(self, "date", require_local_date(self.date, "date"))
        if self.seconds < 0:
            raise ValueError("seconds darf nicht negativ sein.")
        if self.load is not None and self.load < 0:
            raise ValueError("load darf nicht negativ sein.")


@dataclass(frozen=True, slots=True)
class RecordedTotals:
    seconds: float = 0.0
    load: float = 0.0
    count: int = 0
    activities: tuple[ActivityReference, ...] = ()

    @property
    def minutes(self) -> float:
        return self.seconds / 60


def recorded_totals(activities: Iterable[RecordedActivity]) -> RecordedTotals:
    """Summiert eindeutige kanonische Aktivitäten; Duplikate zählen nicht doppelt."""
    unique: dict[str, RecordedActivity] = {}
    for activity in activities:
        if not isinstance(activity, RecordedActivity):
            raise TypeError("activities müssen RecordedActivity enthalten.")
        unique.setdefault(activity.reference.key, activity)
    ordered = tuple(unique[key] for key in sorted(unique))
    return RecordedTotals(
        seconds=sum(activity.seconds for activity in ordered),
        load=sum(float(activity.load or 0) for activity in ordered),
        count=len(ordered),
        activities=tuple(activity.reference for activity in ordered),
    )


def recorded_activity_from_record(
    record: Mapping[str, Any],
    *,
    account_id: str,
    athlete_id: str,
) -> RecordedActivity:
    return RecordedActivity(
        reference=activity_reference_from_record(
            record,
            account_id=account_id,
            athlete_id=athlete_id,
        ),
        date=activity_date(record),
        seconds=recorded_seconds(record),
        load=recorded_load(record),
        name=str(record.get("name") or ""),
    )


def recorded_activity_from_row(
    row: Mapping[str, Any],
    *,
    account_id: str,
    athlete_id: str,
) -> RecordedActivity:
    return recorded_activity_from_record(row, account_id=account_id, athlete_id=athlete_id)


@dataclass(frozen=True, slots=True)
class PlanRecord:
    reference: PlanReference
    plan: PlannedWorkout

    def __post_init__(self) -> None:
        if not isinstance(self.reference, PlanReference):
            raise ValueError("reference muss eine PlanReference sein.")
        if not isinstance(self.plan, PlannedWorkout):
            raise ValueError("plan muss ein PlannedWorkout sein.")

    @property
    def totals(self) -> KnownTotals:
        return calculate_known_totals(self.plan)


def plan_record(
    plan: PlannedWorkout,
    *,
    account_id: str,
    athlete_id: str,
) -> PlanRecord:
    return PlanRecord(
        PlanReference(plan.local_id, account_id, athlete_id),
        plan,
    )


@dataclass(frozen=True, slots=True)
class OpenPlanTotals:
    seconds: float = 0.0
    distance_metres: float = 0.0
    count: int = 0
    has_unknown: bool = False
    plans: tuple[PlanReference, ...] = ()

    @property
    def minutes(self) -> float:
        return self.seconds / 60


def _completed_plan_keys(relationships: Iterable[TrainingRelationship]) -> set[str]:
    return {
        relationship.plan.key
        for relationship in relationships
        if relationship.is_complete
    }


def open_plan_totals(
    plans: Iterable[PlanRecord],
    relationships: Iterable[TrainingRelationship] = (),
    period: TrainingRange | None = None,
) -> OpenPlanTotals:
    """Offene Planungen separat; bestätigt abgeschlossene zählen nicht erneut."""
    completed = _completed_plan_keys(relationships)
    unique: dict[str, PlanRecord] = {}
    for plan in plans:
        if not isinstance(plan, PlanRecord):
            raise TypeError("plans müssen PlanRecord enthalten.")
        if period is not None and not period.contains(plan.plan.date):
            continue
        unique.setdefault(plan.reference.key, plan)
    open_records = [
        record for key, record in sorted(unique.items()) if key not in completed
    ]
    seconds = 0.0
    distance = 0.0
    unknown = False
    for record in open_records:
        totals = record.totals
        seconds += totals.duration_seconds
        distance += totals.distance_metres
        unknown = unknown or totals.has_unknown
    return OpenPlanTotals(
        seconds=seconds,
        distance_metres=distance,
        count=len(open_records),
        has_unknown=unknown,
        plans=tuple(record.reference for record in open_records),
    )


def relationship_actuals(
    relationship: TrainingRelationship,
    activities: Iterable[RecordedActivity],
) -> RecordedTotals:
    """Nur die tatsächlich zugeordneten Aufzeichnungen einer Beziehung."""
    known = {activity.reference.key: activity for activity in activities}
    selected = [
        known[activity.key]
        for activity in relationship.activities
        if activity.key in known
    ]
    return recorded_totals(selected)


@dataclass(frozen=True, slots=True)
class WeekSummary:
    period: TrainingRange
    recorded: RecordedTotals
    open_plan: OpenPlanTotals
    completion_references: tuple[CompletionReferenceListEntry, ...] = ()
    relationship_issues: tuple[str, ...] = ()

    @property
    def recorded_seconds(self) -> float:
        return self.recorded.seconds

    @property
    def open_plan_seconds(self) -> float:
        return self.open_plan.seconds


def _activity_dates(activities: Iterable[RecordedActivity]) -> dict[str, LocalDate]:
    return {activity.reference.key: activity.date for activity in activities}


def build_week_summary(
    period: TrainingRange,
    plans: Iterable[PlanRecord],
    activities: Iterable[RecordedActivity],
    relationships: Iterable[TrainingRelationship] = (),
) -> WeekSummary:
    """Ist und offene Planung für einen lokalen Wochenvertrag.

    Die Aufzeichnungen werden nach ihrem tatsächlichen Datum gefiltert. Eine
    abgeschlossene Planung, deren Aufzeichnung außerhalb der Woche liegt,
    erzeugt am Plantermin nur einen Erledigt-Hinweis und keine Ist-Zeit.
    """
    if not isinstance(period, TrainingRange):
        raise ValueError("period muss eine TrainingRange sein.")
    activity_list = tuple(activities)
    plan_list = tuple(plans)
    relationship_list = tuple(relationships)
    dates = _activity_dates(activity_list)
    completed = [
        relationship for relationship in relationship_list if relationship.is_complete
    ]

    completion: list[CompletionReferenceListEntry] = []
    issues: list[str] = []
    for relationship in completed:
        record = next(
            (
                plan
                for plan in plan_list
                if plan.reference.key == relationship.plan.key
            ),
            None,
        )
        if record is None or not period.contains(record.plan.date):
            continue
        try:
            entries = relationship_entries(relationship, record.plan.date, dates)
        except RelationshipProjectionError as exc:
            issues.append(str(exc))
            continue
        completion.extend(
            entry
            for entry in entries
            if isinstance(entry, CompletionReferenceListEntry) and period.contains(entry.date)
        )

    in_period = [activity for activity in activity_list if period.contains(activity.date)]
    return WeekSummary(
        period=period,
        recorded=recorded_totals(in_period),
        open_plan=open_plan_totals(plan_list, relationship_list, period),
        completion_references=tuple(sorted(completion, key=lambda entry: entry.key)),
        relationship_issues=tuple(issues),
    )


@dataclass(frozen=True, slots=True)
class WeekProjection:
    summary: WeekSummary
    entries: tuple[TrainingListEntry, ...] = field(default_factory=tuple)


def build_week_projection(
    period: TrainingRange,
    plans: Iterable[PlanRecord],
    activities: Iterable[RecordedActivity],
    relationships: Iterable[TrainingRelationship] = (),
) -> WeekProjection:
    """Gemeinsame Liste aus Planungen, Aufzeichnungen und belegten Beziehungen."""
    activity_list = tuple(activities)
    plan_list = tuple(plans)
    relationship_list = tuple(relationships)
    summary = build_week_summary(period, plan_list, activity_list, relationship_list)
    dates = _activity_dates(activity_list)
    completed = _completed_plan_keys(relationship_list)
    entries: dict[str, TrainingListEntry] = {}
    covered_activities: set[str] = set()
    projected_plans: set[str] = set()
    incomplete_projections: set[str] = set()

    for relationship in relationship_list:
        if not relationship.is_complete:
            continue
        try:
            projected = relationship_entries(
                relationship,
                _plan_date(relationship, plan_list),
                dates,
            )
        except RelationshipProjectionError:
            incomplete_projections.add(relationship.plan.key)
            continue
        for entry in projected:
            if not period.contains(entry.date):
                continue
            entries[list_entry_key(entry)] = entry
            if isinstance(entry, LinkedListEntry):
                projected_plans.add(relationship.plan.key)
                covered_activities.update(activity.key for activity in entry.activities)
            if isinstance(entry, CompletionReferenceListEntry):
                projected_plans.add(relationship.plan.key)

    for plan in plan_list:
        if not period.contains(plan.plan.date):
            continue
        if plan.reference.key in completed and plan.reference.key not in incomplete_projections:
            continue
        if plan.reference.key in projected_plans:
            continue
        entry = PlannedListEntry(plan.plan.date, plan.reference)
        entries[list_entry_key(entry)] = entry

    for activity in activity_list:
        if not period.contains(activity.date):
            continue
        if activity.reference.key in covered_activities:
            continue
        entry = RecordedListEntry(activity.date, activity.reference)
        entries[list_entry_key(entry)] = entry

    ordered = tuple(sorted(entries.values(), key=_entry_sort_key))
    return WeekProjection(summary=summary, entries=ordered)


def _plan_date(
    relationship: TrainingRelationship,
    plans: tuple[PlanRecord, ...],
) -> LocalDate:
    for record in plans:
        if record.reference.key == relationship.plan.key:
            return record.plan.date
    raise RelationshipProjectionError(
        f"Der Plantermin zu {relationship.plan.key} ist in den geladenen Planungen nicht enthalten."
    )


def _entry_sort_key(entry: TrainingListEntry) -> tuple[str, int, str]:
    order = {
        "planned": 0,
        "linked": 1,
        "completionReference": 2,
        "recorded": 3,
    }
    return (entry.date, order.get(entry.kind, 9), list_entry_key(entry))


__all__ = [
    "OpenPlanTotals",
    "PlanRecord",
    "RecordedActivity",
    "RecordedTotals",
    "WeekProjection",
    "WeekSummary",
    "build_week_projection",
    "build_week_summary",
    "open_plan_totals",
    "plan_record",
    "recorded_activity_from_record",
    "recorded_activity_from_row",
    "recorded_load",
    "recorded_seconds",
    "recorded_totals",
    "relationship_actuals",
]
