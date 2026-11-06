"""Wochenabfrage für den Trainingsplaner.

Die Abfrage verbindet zwei vorhandene Lesewege, ohne sie zu vermischen:

* Planungen aus der Tabelle ``event`` über den bestehenden Event-Lesepfad,
* Aufzeichnungen aus der Tabelle ``activity`` über den bestehenden
  Aktivitäts-Lesepfad.

Die beiden Quellen werden getrennt geladen und getrennt gemeldet. Ein Fehler
der einen Quelle macht die andere nicht leer. Die Projektion ist eine reine
Anzeigeform: Sie erzeugt weder einen Plan noch eine Aufzeichnung und leitet
keine Beziehung aus gleichzeitigem Vorkommen ab.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from typing import Any

from .dates import (
    format_day,
    get_week_days,
    week_label,
)
from .identities import ActivityId, ActivityReference, PlanId, PlanReference
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
from .summaries import recorded_seconds

WEEKDAYS = (
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
)
WEEKDAYS_SHORT = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")

#: Reihenfolge innerhalb eines Tages, wenn keine Startzeit entscheidet.
#: Geplantes steht vor der Aufzeichnung; die Erledigt-Referenz ist nur ein
#: Hinweis und keine zusätzliche Einheit.
ENTRY_KIND_ORDER = {
    "planned": 0,
    "linked": 1,
    "completionReference": 2,
    "recorded": 3,
}

SOURCE_COMPLETE = "complete"
SOURCE_EMPTY = "empty"
SOURCE_PARTIAL = "partial"
SOURCE_ERROR = "error"
SOURCE_UNAVAILABLE = "unavailable"


def account_context(conn: Any) -> tuple[str, str]:
    """Account und Athlet aus dem vorhandenen Settings-Speicher, mit Default."""
    from .. import db

    account = (db.get_setting(conn, "account_id") or "default").strip() or "default"
    athlete = (db.get_setting(conn, "athlete_id") or "default").strip() or "default"
    return account, athlete


def week_query_keys(
    period: TrainingRange,
    *,
    account_id: str = "default",
    athlete_id: str = "default",
    today: str | None = None,
) -> dict[str, str]:
    """Cache-Schlüssel nach Abschnitt 9.9.

    Quelle, Account/Athlet, Zeitraumgrenzen und Zeitzone sind Teil des
    Schlüssels. Die Wochenprojektion ist ausdrücklich nicht der rollierende
    Dashboard-Schlüssel.
    """
    base = (
        f"planner:v1:{account_id}:{athlete_id}:{period.time_zone}:"
        f"{period.start_date}:{period.end_date}"
    )
    dashboard_end = date.fromisoformat(today or period.end_date)
    dashboard_start = dashboard_end - timedelta(days=6)
    dashboard = (
        f"dashboard:v1:{account_id}:{athlete_id}:{period.time_zone}:"
        f"{dashboard_start.isoformat()}:{dashboard_end.isoformat()}:projection:rolling"
    )
    return {
        "week": f"{base}:projection:week",
        "plans": f"{base}:source:plans",
        "activities": f"{base}:source:activities",
        "dashboard": dashboard,
    }


def planned_seconds(entry: Mapping[str, Any]) -> float | None:
    """Bekannte geplante Dauer eines Listeneintrags; ``None`` heißt unbekannt."""
    planned = entry.get("planned")
    if not isinstance(planned, Mapping):
        return None
    if planned.get("known_seconds") is not None:
        return float(planned["known_seconds"])
    # Abwärtskompatibel zu einer reinen Anzeigeform ohne known_seconds:
    # eine geschätzte Dauer darf hier nicht als bekannt gelten.
    if planned.get("estimated") == "dauer":
        return None
    if planned.get("seconds") is not None:
        return float(planned["seconds"])
    minutes = planned.get("minutes")
    return float(minutes) * 60 if minutes is not None else None


def planned_metres(entry: Mapping[str, Any]) -> float | None:
    planned = entry.get("planned")
    if not isinstance(planned, Mapping):
        return None
    if planned.get("known_distance_metres") is not None:
        return float(planned["known_distance_metres"])
    if planned.get("estimated") == "distanz":
        return None
    if planned.get("distance_metres") is not None:
        return float(planned["distance_metres"])
    km = planned.get("km")
    return float(km) * 1000 if km is not None else None


def _json_object(raw: object) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _local_start(raw: Mapping[str, Any], fallback: str | None = None) -> str | None:
    value = raw.get("start_date_local") or raw.get("start_date")
    if value is None and fallback:
        value = fallback
    if value is None:
        return None
    text = str(value)
    if "T" not in text:
        return None
    clock = text.split("T", 1)[1][:5]
    # GanzTägige Events tragen 00:00. Das ist keine erfundene Uhrzeit.
    return None if clock in {"", "00:00"} else clock


def _sport_label(sport: str | None) -> str:
    from ..plan import SPORT_LABELS

    return SPORT_LABELS.get(sport or "", sport or "Andere Sportart")


def _activity_view(
    row: Mapping[str, Any],
    *,
    account_id: str,
    athlete_id: str,
) -> dict[str, Any]:
    from .. import metrics

    payload = metrics.activity_payload(dict(row))
    start = str(row.get("start_local") or "")
    clock = start[11:16] if len(start) >= 16 and start[10] == "T" else None
    if clock == "00:00":
        clock = None
    reference = ActivityReference(
        ActivityId(str(row["id"])),
        account_id,
        athlete_id,
    )
    return {
        "kind": "recorded",
        "key": RecordedListEntry(str(row["date"]), reference).key,
        "date": str(row["date"]),
        "start": clock,
        "activity": payload,
        "activity_row_id": int(row["id"]),
        "activity_id": payload["id"],
        "name": payload["name"],
        "sport": payload["sport"],
        "sport_label": payload["sport_label"],
        "actual": {
            "minutes": payload.get("duration_min"),
            "km": payload.get("distance_km"),
            "load": payload.get("load"),
            "intensity": payload.get("intensity"),
            "seconds": recorded_seconds(row),
        },
        "planned": None,
        "status": "recorded",
    }


def _plan_view(
    row: Mapping[str, Any],
    *,
    speeds_kmh: Mapping[str, float] | None,
    account_id: str,
    athlete_id: str,
    time_zone: str,
) -> dict[str, Any]:
    from .. import plan as plan_mod

    raw = _json_object(row.get("raw"))
    event = dict(raw)
    # ``plan.planned()`` erwartet den unveränderten Rohdatensatz als JSON-Text.
    # Ohne diese Quelle würde ein frisch bestätigtes Event ohne berechnete
    # Dauer-/Distanzspalten als „ohne Vorgabe“ erscheinen, obwohl sein
    # workout_doc vollständig lesbar ist.
    if isinstance(row.get("raw"), str) and row.get("raw").strip():
        event["raw"] = row["raw"]
    event.setdefault("id", row.get("id"))
    event.setdefault("start_date_local", row.get("date"))
    event.setdefault("type", row.get("sport"))
    event.setdefault("category", row.get("category") or "WORKOUT")
    event.setdefault("name", row.get("name"))
    event.setdefault("moving_time", row.get("duration_s"))
    event.setdefault("duration_s", row.get("duration_s"))
    event.setdefault("distance", row.get("distance_m"))
    event.setdefault("distance_m", row.get("distance_m"))
    event.setdefault("icu_training_load", row.get("load"))
    event.setdefault("icu_intensity", row.get("intensity"))
    try:
        numbers = plan_mod.planned(event, dict(speeds_kmh or {}))
    except Exception:  # noqa: BLE001 - ein unbekannter Aufbau bleibt lesbar
        numbers = _numbers_from_row(row)
    planned = _planned_values(numbers, row.get("load"))
    known = _known_totals(event, time_zone)
    if known is not None:
        known_seconds, known_metres, unknown = known
        planned["known_seconds"] = known_seconds
        planned["known_distance_metres"] = known_metres
        planned["has_unknown"] = unknown
    reference = PlanReference(
        PlanId(f"plan:event:{row['id']}"),
        account_id,
        athlete_id,
    )
    return {
        "kind": "planned",
        "key": PlannedListEntry(str(row["date"]), reference).key,
        "date": str(row["date"]),
        "start": _local_start(raw, row.get("date")),
        "plan": {
            "id": int(row["id"]),
            "remote_id": str(row["id"]),
            "local_id": f"plan:event:{row['id']}",
            "reference": reference.key,
            "date": str(row["date"]),
            "sport": row.get("sport"),
            "sport_label": _sport_label(row.get("sport")),
            "name": row.get("name") or "",
        },
        "plan_id": int(row["id"]),
        "name": row.get("name") or _sport_label(row.get("sport")),
        "sport": row.get("sport"),
        "sport_label": _sport_label(row.get("sport")),
        "planned": planned,
        "actual": None,
        "status": "planned",
        "_reference": reference,
    }


def _known_totals(
    event: Mapping[str, Any], time_zone: str
) -> tuple[float | None, float | None, bool] | None:
    """Bekannte Mengen aus dem vorhandenen P04/P05-Modell, wenn lesbar.

    Die Anzeigezahlen aus :func:`plan.planned` dürfen eine fehlende Hälfte
    schätzen. Für die Wochensumme zählt nur, was der Aufbau wirklich vorgibt.
    """
    from .remote import read_remote_event
    from .validation import calculate_known_totals

    try:
        remote = read_remote_event(
            event,
            fetched_at=datetime.now().astimezone().isoformat(timespec="seconds"),
            time_zone=time_zone,
        )
    except Exception:  # noqa: BLE001 - der Anzeigepfad darf daran nicht scheitern
        return None
    totals = calculate_known_totals(remote.plan)
    if totals.executions == 0:
        return None
    duration = totals.duration_seconds if totals.duration_seconds > 0 else None
    distance = totals.distance_metres if totals.distance_metres > 0 else None
    # Ein Distanzziel kann im Event stehen, ohne dass ein Abschnitt es wiederholt.
    if distance is None and event.get("distance_m") and totals.first_end == "time":
        distance = float(event["distance_m"])
    if duration is None and distance is None:
        return None
    return duration, distance, totals.has_unknown


def _numbers_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Fallback aus den vorhandenen Spalten, wenn der Aufbau nicht lesbar ist."""
    duration = row.get("duration_s")
    distance = row.get("distance_m")
    minutes = round(float(duration) / 60) if duration else None
    km = round(float(distance) / 1000, 1) if distance else None
    if distance:
        primary = "distance"
    elif duration:
        primary = "duration"
    else:
        primary = None
    return {
        "minutes": minutes,
        "km": km,
        "estimated": "keine",
        "primary": primary,
    }


def _planned_values(numbers: Mapping[str, Any], load: object) -> dict[str, Any]:
    """Bekannte und geschätzte Vorgaben getrennt halten.

    ``minutes``/``km`` sind die Anzeigeform und dürfen eine Schätzung tragen.
    Die Summen dürfen nur die tatsächlich vorgegebene Hälfte verwenden.
    """
    minutes = numbers.get("minutes")
    km = numbers.get("km")
    primary = numbers.get("primary")
    estimated = numbers.get("estimated")
    seconds = float(minutes) * 60 if minutes is not None else None
    metres = float(km) * 1000 if km is not None else None
    known_seconds = (
        seconds
        if seconds is not None and (primary == "duration" or estimated == "keine")
        else None
    )
    known_metres = (
        metres
        if metres is not None and (primary == "distance" or estimated == "keine")
        else None
    )
    return {
        "minutes": minutes,
        "km": km,
        "estimated": estimated,
        "primary": primary,
        "load": load,
        "seconds": seconds,
        "distance_metres": metres,
        "known_seconds": known_seconds,
        "known_distance_metres": known_metres,
        "has_unknown": known_seconds is None and known_metres is None,
    }


def _serialize_projected(
    entry: TrainingListEntry,
    *,
    plans: Mapping[str, dict[str, Any]],
    activities: Mapping[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Einen P05-Eintrag in die API-Form bringen; keine neue Beziehung erfinden."""
    if isinstance(entry, PlannedListEntry):
        view = plans.get(entry.plan.key)
        return _public_plan(view) if view else None
    if isinstance(entry, RecordedListEntry):
        view = activities.get(entry.activity.key)
        return _public_activity(view) if view else None
    if isinstance(entry, LinkedListEntry):
        plan = plans.get(entry.plan.key)
        linked = [activities.get(activity.key) for activity in entry.activities]
        linked_views = [view for view in linked if view is not None]
        if not linked_views:
            return None
        primary = linked_views[0]
        seconds = sum(float(view["actual"]["seconds"]) for view in linked_views)
        load = sum(float(view["actual"].get("load") or 0) for view in linked_views)
        starts = [view["start"] for view in linked_views if view.get("start")]
        return {
            "kind": "linked",
            "key": entry.key,
            "date": entry.date,
            "start": min(starts) if starts else None,
            "plan": plan["plan"] if plan else None,
            "plan_id": plan["plan_id"] if plan else None,
            "name": plan["name"] if plan else primary["name"],
            "sport": plan["sport"] if plan else primary["sport"],
            "sport_label": plan["sport_label"] if plan else primary["sport_label"],
            "planned": plan["planned"] if plan else None,
            "actual": {
                "minutes": round(seconds / 60) if seconds else None,
                "km": primary["actual"].get("km"),
                "load": load or None,
                "seconds": seconds,
            },
            "activities": linked_views,
            "activity": primary,
            "status": "completed",
            "relationship_id": str(entry.relationship_id),
        }
    if isinstance(entry, CompletionReferenceListEntry):
        plan = plans.get(entry.plan.key)
        return {
            "kind": "completionReference",
            "key": entry.key,
            "date": entry.date,
            "start": None,
            "plan": plan["plan"] if plan else None,
            "plan_id": plan["plan_id"] if plan else None,
            "name": plan["name"] if plan else "",
            "sport": plan["sport"] if plan else None,
            "sport_label": plan["sport_label"] if plan else "Andere Sportart",
            "planned": None,
            "actual": None,
            "activity": None,
            "activity_dates": list(entry.activity_dates),
            "compact_text": "Erledigt am " + format_day(entry.activity_dates[0]),
            "status": "completionReference",
            "relationship_id": str(entry.relationship_id),
        }
    return None


def _entry_sort_key(entry: Mapping[str, Any]) -> tuple[str, int, str]:
    """Startzeit zuerst; Einträge ohne Uhrzeit stabil danach."""
    start = entry.get("start")
    return (
        f"0:{start}" if start else "1:",
        ENTRY_KIND_ORDER.get(str(entry.get("kind")), 9),
        str(entry.get("key") or ""),
    )


def _source(
    *,
    source: str,
    key: str,
    state: str,
    count: int,
    error: str | None,
    coverage: str,
) -> dict[str, Any]:
    return {
        "source": source,
        "key": key,
        "state": state,
        "loaded": state not in {SOURCE_ERROR, SOURCE_UNAVAILABLE},
        "complete": state in {SOURCE_COMPLETE, SOURCE_EMPTY},
        "count": count,
        "error": error,
        "coverage": coverage,
    }


def coverage_for_period(period: TrainingRange, sync_range: object, *, to_field: str = "to") -> str:
    """Ob der vorhandene Sync den Zeitraum nachweislich abdeckt."""
    if not isinstance(sync_range, Mapping):
        return "unknown"
    raw_from = sync_range.get("from")
    raw_to = sync_range.get(to_field) or sync_range.get("to")
    if not raw_from or not raw_to:
        return "unknown"
    try:
        start = date.fromisoformat(str(raw_from)[:10])
        end = date.fromisoformat(str(raw_to)[:10])
    except ValueError:
        return "unknown"
    if end < start:
        return "unknown"
    week_start = date.fromisoformat(period.start_date)
    week_end = date.fromisoformat(period.end_date)
    return "covered" if week_start <= end and week_end >= start else "uncovered"


def build_planner_week(
    period: TrainingRange,
    plan_rows: Iterable[Mapping[str, Any]],
    activity_rows: Iterable[Mapping[str, Any]],
    *,
    today: str,
    time_zone: str,
    account_id: str = "default",
    athlete_id: str = "default",
    plans_state: str = SOURCE_COMPLETE,
    activities_state: str = SOURCE_COMPLETE,
    plans_error: str | None = None,
    activities_error: str | None = None,
    plans_coverage: str = "unknown",
    activities_coverage: str = "unknown",
    relationships: Iterable[TrainingRelationship] = (),
    speeds_kmh: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Eine Woche als getrennte Quellen und gemeinsame Anzeigeprojektion."""
    plan_rows = list(plan_rows)
    activity_rows = list(activity_rows)
    plan_issues: list[str] = []
    activity_issues: list[str] = []
    issues: list[str] = []

    plans: dict[str, dict[str, Any]] = {}
    for row in plan_rows:
        try:
            view = _plan_view(
                row,
                speeds_kmh=speeds_kmh,
                account_id=account_id,
                athlete_id=athlete_id,
                time_zone=period.time_zone,
            )
        except Exception as exc:  # noqa: BLE001 - eine Zeile darf den Tag nicht kippen
            plan_issues.append(f"Planung {row.get('id')}: {str(exc)[:120]}")
            continue
        plans[view["_reference"].key] = view
    if plan_issues and plans_state in {SOURCE_COMPLETE, SOURCE_EMPTY}:
        plans_state = SOURCE_PARTIAL
    issues.extend(plan_issues)

    activities: dict[str, dict[str, Any]] = {}
    for row in activity_rows:
        try:
            view = _activity_view(row, account_id=account_id, athlete_id=athlete_id)
        except Exception as exc:  # noqa: BLE001 - eine Zeile darf den Tag nicht kippen
            activity_issues.append(f"Aufzeichnung {row.get('id')}: {str(exc)[:120]}")
            continue
        reference = ActivityReference(
            ActivityId(str(row["id"])),
            account_id,
            athlete_id,
        )
        activities[reference.key] = view
    if activity_issues and activities_state in {SOURCE_COMPLETE, SOURCE_EMPTY}:
        activities_state = SOURCE_PARTIAL
    issues.extend(activity_issues)

    # Die reinen P05-Einträge zentral bilden. Beziehungen kommen nur aus dem
    # ausdrücklich übergebenen Vertrag, nie aus Namen oder gleichen Tagen.
    projected: dict[str, dict[str, Any]] = {}
    projected_plans: set[str] = set()
    covered_activities: set[str] = set()
    plan_dates = {key: str(view["date"]) for key, view in plans.items()}
    activity_dates = {key: str(view["date"]) for key, view in activities.items()}
    for relationship in relationships:
        if not relationship.is_complete:
            continue
        plan_date = plan_dates.get(relationship.plan.key)
        if plan_date is None:
            issues.append(
                f"Beziehung {relationship.relationship_id}: Plantermin nicht in der Woche geladen."
            )
            continue
        try:
            entries = relationship_entries(relationship, plan_date, activity_dates)
        except RelationshipProjectionError as exc:
            issues.append(str(exc))
            continue
        for entry in entries:
            serialized = _serialize_projected(entry, plans=plans, activities=activities)
            if serialized is None:
                continue
            if serialized["date"] < period.start_date or serialized["date"] > period.end_date:
                continue
            projected[list_entry_key(entry)] = serialized
            if isinstance(entry, LinkedListEntry):
                projected_plans.add(relationship.plan.key)
                covered_activities.update(activity.key for activity in entry.activities)
            if isinstance(entry, CompletionReferenceListEntry):
                projected_plans.add(relationship.plan.key)

    for key, view in plans.items():
        if key in projected_plans:
            continue
        if view["date"] < period.start_date or view["date"] > period.end_date:
            continue
        projected.setdefault(view["key"], _public_plan(view))

    for key, view in activities.items():
        if key in covered_activities:
            continue
        if view["date"] < period.start_date or view["date"] > period.end_date:
            continue
        projected.setdefault(view["key"], _public_activity(view))

    entries = sorted(projected.values(), key=_entry_sort_key)
    days = _days(period, entries, today)

    in_period_activities = [
        view
        for view in activities.values()
        if period.start_date <= view["date"] <= period.end_date
    ]
    recorded_count = len(in_period_activities)
    recorded_seconds_total = sum(
        float(view["actual"]["seconds"]) for view in in_period_activities
    )
    recorded_load = sum(
        float(view["actual"].get("load") or 0) for view in in_period_activities
    )

    open_entries = [
        entry
        for entry in entries
        if entry["kind"] == "planned" and entry.get("key") not in {
            view["key"] for key, view in plans.items() if key in projected_plans
        }
    ]
    open_seconds = 0.0
    open_metres = 0.0
    open_unknown = False
    for entry in open_entries:
        seconds = planned_seconds(entry)
        metres = planned_metres(entry)
        if seconds is None and metres is None:
            open_unknown = True
        open_seconds += seconds or 0.0
        open_metres += metres or 0.0
    plans_loaded = plans_state not in {SOURCE_ERROR, SOURCE_UNAVAILABLE}
    activities_loaded = activities_state not in {SOURCE_ERROR, SOURCE_UNAVAILABLE}
    open_count = len(open_entries)

    plans_complete = plans_state in {SOURCE_COMPLETE, SOURCE_EMPTY}
    activities_complete = activities_state in {SOURCE_COMPLETE, SOURCE_EMPTY}
    keys = week_query_keys(
        period,
        account_id=account_id,
        athlete_id=athlete_id,
        today=today,
    )
    payload = {
        "week": period.start_date,
        "from": period.start_date,
        "to": period.end_date,
        "time_zone": time_zone,
        "label": week_label(period.start_date),
        "calendar_week": _calendar_week(period.start_date),
        "today": today,
        "days": days,
        "entries": entries,
        "summary": {
            "recorded": {
                "state": activities_state,
                "complete": activities_complete,
                "seconds": int(recorded_seconds_total) if activities_loaded else None,
                "load": round(recorded_load) if activities_loaded else None,
                "count": recorded_count if activities_loaded else None,
            },
            "open_plan": {
                "state": plans_state,
                "complete": plans_complete,
                "seconds": int(open_seconds) if plans_loaded else None,
                "distance_metres": int(open_metres) if plans_loaded else None,
                "count": open_count if plans_loaded else None,
                "has_unknown": bool(open_unknown) if plans_loaded else True,
            },
        },
        "sources": {
            "plans": _source(
                source="plans",
                key=keys["plans"],
                state=plans_state,
                count=sum(
                    1 for view in plans.values()
                    if period.start_date <= view["date"] <= period.end_date
                ),
                error=plans_error,
                coverage=plans_coverage,
            ),
            "activities": _source(
                source="activities",
                key=keys["activities"],
                state=activities_state,
                count=recorded_count,
                error=activities_error,
                coverage=activities_coverage,
            ),
        },
        "query": {
            "key": keys["week"],
            "plans_key": keys["plans"],
            "activities_key": keys["activities"],
            "dashboard_key": keys["dashboard"],
            "projection": "week",
        },
        "relationship_issues": issues,
    }
    return payload


def _public_plan(view: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in view.items() if not key.startswith("_")}


def _public_activity(view: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in view.items() if not key.startswith("_")}


def _calendar_week(week_start: str) -> int:
    return date.fromisoformat(week_start).isocalendar().week


def _days(period: TrainingRange, entries: list[dict[str, Any]], today: str) -> list[dict[str, Any]]:
    by_date: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_date.setdefault(str(entry["date"]), []).append(entry)
    days: list[dict[str, Any]] = []
    for index, day in enumerate(get_week_days(period.start_date, period.time_zone)):
        days.append(
            {
                "date": day,
                "weekday": WEEKDAYS[index],
                "weekday_short": WEEKDAYS_SHORT[index],
                "label": format_day(day),
                "is_today": day == today,
                "entries": by_date.get(day, []),
            }
        )
    return days


def planner_week_from_params(
    week: str | None,
    *,
    time_zone: str,
    today: str | None = None,
) -> TrainingRange:
    """Validierten Wochenparameter in den lokalen Wochenvertrag übersetzen."""
    from .dates import parse_week_parameter, planner_week_range

    now = None if today is None else _at_noon(today, time_zone)
    monday = parse_week_parameter(week, time_zone, now=now)
    return planner_week_range(monday, time_zone)


def _at_noon(local_date: str, time_zone: str):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.fromisoformat(f"{local_date}T12:00:00").replace(tzinfo=ZoneInfo(time_zone))


__all__ = [
    "SOURCE_COMPLETE",
    "SOURCE_EMPTY",
    "SOURCE_ERROR",
    "SOURCE_PARTIAL",
    "SOURCE_UNAVAILABLE",
    "account_context",
    "build_planner_week",
    "coverage_for_period",
    "planned_metres",
    "planned_seconds",
    "planner_week_from_params",
    "week_query_keys",
]
