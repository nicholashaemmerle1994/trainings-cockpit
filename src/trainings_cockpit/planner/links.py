"""Verknüpfungen zwischen geplanten Einheiten und Aufzeichnungen.

Eine Verknüpfung ist eine eigene Aussage. Sie entsteht auf zwei Wegen:

* **automatisch**, wenn an einem lokalen Tag in derselben Sportartfamilie
  genau eine Planung und genau eine Aufzeichnung übrig sind. Dann ist die
  Paarung eindeutig; alles andere bleibt getrennt.
* **ausdrücklich** durch den Athleten, auch wenn mehrere Kandidaten am selben
  Tag liegen oder die Sportart abweicht.

``separated`` ist die dritte Aussage: Der Athlet hat ein Paar getrennt. Sie
verhindert, dass die nächste Wochenabfrage eine automatische Paarung sofort
wiederherstellt. Die Auflösung liest nur; geschrieben wird ausschließlich in
:func:`link_unit` und :func:`separate_unit`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .dates import start_of_planner_week
from .identities import (
    ActivityId,
    ActivityReference,
    PlanId,
    PlanReference,
    RelationshipId,
)
from .projections import RelationshipStatus, TrainingRelationship

LINKED = "linked"
SEPARATED = "separated"
AUTO = "auto"
MANUAL = "manual"


class LinkError(ValueError):
    """Eine Verknüpfung ist fachlich nicht zulässig."""


class LinkNotFound(LinkError):
    """Planung oder Aufzeichnung existiert nicht mehr."""


def _link_sport_key(sport: str | None) -> str | None:
    """Vergleichsschlüssel für die 1:1-Paarung.

    Bekannte Varianten derselben Sportart (Ride/VirtualRide, Run/TrailRun,
    Swim/OpenWaterSwim) teilen einen Schlüssel. Alles andere vergleicht sich
    mit sich selbst — ``plan.sport_family`` ist dafür bewusst nicht die
    Grundlage, denn dort geht es um gemeinsame Geschwindigkeiten, nicht um
    Identität.
    """
    from ..plan import sport_family

    text = (sport or "").strip()
    if not text:
        return None
    return sport_family(text) or text


def _day(row: Mapping[str, Any]) -> str:
    return str(row.get("date") or "")[:10]


def _plan_reference(
    event_id: int,
    *,
    account_id: str,
    athlete_id: str,
) -> PlanReference:
    return PlanReference(PlanId(f"plan:event:{event_id}"), account_id, athlete_id)


def _activity_reference(
    row_id: int,
    *,
    account_id: str,
    athlete_id: str,
) -> ActivityReference:
    return ActivityReference(ActivityId(str(row_id)), account_id, athlete_id)


def _relationship(
    *,
    event_id: int,
    activity_ids: tuple[int, ...],
    relationship_id: str,
    account_id: str,
    athlete_id: str,
) -> TrainingRelationship:
    return TrainingRelationship(
        relationship_id=RelationshipId(relationship_id),
        plan=_plan_reference(event_id, account_id=account_id, athlete_id=athlete_id),
        activities=tuple(
            _activity_reference(row_id, account_id=account_id, athlete_id=athlete_id)
            for row_id in activity_ids
        ),
        status=RelationshipStatus.CONFIRMED,
        completion_confirmed=True,
    )


def resolve_relationships(
    plan_rows: Iterable[Mapping[str, Any]],
    activity_rows: Iterable[Mapping[str, Any]],
    links: Iterable[Mapping[str, Any]],
    *,
    account_id: str = "default",
    athlete_id: str = "default",
) -> tuple[list[TrainingRelationship], list[str]]:
    """Bestätigte und eindeutige Paarungen für eine Woche auflösen.

    ``links`` sind die gespeicherten Aussagen. Eine ``linked``-Zeile gewinnt
    immer; eine eindeutige Paarung entsteht nur, wenn nach Abzug der
    gespeicherten Links genau eine Planung und eine Aufzeichnung derselben
    Sportart (bekannte Varianten zusammengefasst) am selben lokalen Tag übrig
    bleiben. Die Regel ist bewusst eng: Name, Dauer und Ähnlichkeit
    entscheiden nicht.
    """
    plans = {int(row["id"]): row for row in plan_rows}
    activities = {int(row["id"]): row for row in activity_rows}
    link_list = [dict(link) for link in links]
    issues: list[str] = []

    used_event_ids: set[int] = set()
    used_activity_ids: set[int] = set()
    separated: set[tuple[int, int]] = set()
    linked_by_event: dict[int, list[int]] = {}

    for link in link_list:
        try:
            event_id = int(link["event_id"])
            activity_id = int(link["activity_id"])
        except (KeyError, TypeError, ValueError):
            issues.append("Verknüpfung ohne gültige IDs ignoriert.")
            continue
        state = str(link.get("state") or "")
        if state == SEPARATED:
            separated.add((event_id, activity_id))
            continue
        if state != LINKED:
            issues.append(f"Verknüpfung {event_id}/{activity_id}: unbekannter Zustand.")
            continue
        used_event_ids.add(event_id)
        used_activity_ids.add(activity_id)
        # Die Aussage bleibt auch dann bestehen, wenn eine Seite gerade nicht
        # in der Woche geladen ist. Sie darf nicht zu einer anderen Paarung
        # weiterverwendet werden.
        if event_id in plans and activity_id in activities:
            linked_by_event.setdefault(event_id, []).append(activity_id)

    relationships: list[TrainingRelationship] = []
    for event_id, activity_ids in sorted(linked_by_event.items()):
        unique_ids = tuple(sorted(set(activity_ids)))
        relationships.append(
            _relationship(
                event_id=event_id,
                activity_ids=unique_ids,
                relationship_id="link:"
                + ":".join(str(value) for value in (event_id, *unique_ids)),
                account_id=account_id,
                athlete_id=athlete_id,
            )
        )

    groups: dict[tuple[str, str], dict[str, list[int]]] = {}
    for event_id, row in plans.items():
        if event_id in used_event_ids:
            continue
        sport_key = _link_sport_key(row.get("sport"))
        day = _day(row)
        if sport_key is None or not day:
            continue
        groups.setdefault((day, sport_key), {"plans": [], "activities": []})[
            "plans"
        ].append(event_id)
    for activity_id, row in activities.items():
        if activity_id in used_activity_ids:
            continue
        sport_key = _link_sport_key(row.get("sport"))
        day = _day(row)
        if sport_key is None or not day:
            continue
        groups.setdefault((day, sport_key), {"plans": [], "activities": []})[
            "activities"
        ].append(activity_id)

    for _key, group in sorted(groups.items()):
        event_ids = sorted(group["plans"])
        activity_ids = sorted(group["activities"])
        if len(event_ids) != 1 or len(activity_ids) != 1:
            continue
        event_id = event_ids[0]
        activity_id = activity_ids[0]
        if (event_id, activity_id) in separated:
            continue
        relationships.append(
            _relationship(
                event_id=event_id,
                activity_ids=(activity_id,),
                relationship_id=f"auto:{event_id}:{activity_id}",
                account_id=account_id,
                athlete_id=athlete_id,
            )
        )

    def sort_key(relationship: TrainingRelationship) -> tuple[str, str, str]:
        event_id = int(relationship.plan.plan_id.value.rsplit(":", 1)[-1])
        return (
            _day(plans.get(event_id, {})),
            relationship.plan.key,
            relationship.relationship_id.value,
        )

    relationships.sort(key=sort_key)
    return relationships, issues


def _load_unit_and_plan(
    conn: Any, row_id: int, event_id: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    from .. import db

    activity = db.activity_by_row_id(conn, row_id)
    if activity is None:
        raise LinkNotFound("Einheit nicht gefunden.")
    event = db.event_by_id(conn, event_id)
    if event is None:
        raise LinkNotFound("Planung nicht gefunden.")
    return activity, event


def _validate_pair(
    conn: Any,
    activity: Mapping[str, Any],
    event: Mapping[str, Any],
    *,
    time_zone: str,
) -> None:
    from .. import db

    if (event.get("category") or "WORKOUT") != "WORKOUT":
        raise LinkError("Nur geplante Einheiten lassen sich verknüpfen.")
    if str(activity.get("sport") or "") in db.NON_TRAINING_SPORTS:
        raise LinkError("Diese Aufzeichnung zählt nicht als Trainingseinheit.")
    activity_day = _day(activity)
    event_day = _day(event)
    if not activity_day or not event_day:
        raise LinkError("Planung oder Einheit hat kein Datum.")
    if start_of_planner_week(activity_day, time_zone) != start_of_planner_week(
        event_day, time_zone
    ):
        raise LinkError("Planung und Einheit müssen in derselben Woche liegen.")


def link_unit(
    conn: Any,
    row_id: int,
    event_id: int,
    *,
    account_id: str,
    athlete_id: str,
    time_zone: str,
) -> None:
    """Eine Aufzeichnung ausdrücklich mit einer Planung verbinden."""
    from .. import db

    activity, event = _load_unit_and_plan(conn, row_id, event_id)
    _validate_pair(conn, activity, event, time_zone=time_zone)
    db.set_plan_link(
        conn,
        account_id=account_id,
        athlete_id=athlete_id,
        event_id=event_id,
        activity_id=row_id,
    )


def separate_unit(
    conn: Any,
    row_id: int,
    event_id: int,
    *,
    account_id: str,
    athlete_id: str,
    time_zone: str,
) -> None:
    """Eine Verknüpfung trennen und die Trennung merken."""
    from .. import db

    activity, event = _load_unit_and_plan(conn, row_id, event_id)
    _validate_pair(conn, activity, event, time_zone=time_zone)
    db.separate_plan_link(
        conn,
        account_id=account_id,
        athlete_id=athlete_id,
        event_id=event_id,
        activity_id=row_id,
    )


__all__ = [
    "AUTO",
    "LINKED",
    "MANUAL",
    "SEPARATED",
    "LinkError",
    "LinkNotFound",
    "link_unit",
    "resolve_relationships",
    "separate_unit",
]
