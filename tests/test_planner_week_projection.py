from __future__ import annotations

import json

from trainings_cockpit.planner import (
    ActivityId,
    ActivityReference,
    PlanId,
    PlanReference,
    RelationshipId,
    RelationshipStatus,
    TrainingRelationship,
)
from trainings_cockpit.planner.dates import planner_week_range
from trainings_cockpit.planner.week import build_planner_week


def _plan_row(day: str = "2026-11-08") -> dict:
    event = {
        "id": 1,
        "category": "WORKOUT",
        "start_date_local": f"{day}T00:00:00",
        "type": "Run",
        "name": "Lockerer Lauf",
        "moving_time": 2700,
        "workout_doc": {"steps": [{"text": "Lauf", "duration": 2700}]},
    }
    return {
        "id": 1,
        "date": day,
        "sport": "Run",
        "category": "WORKOUT",
        "name": "Lockerer Lauf",
        "load": 40,
        "duration_s": 2700,
        "distance_m": None,
        "intensity": None,
        "raw": json.dumps(event),
    }


def _activity_row(day: str = "2026-11-08") -> dict:
    return {
        "id": 1,
        "source": "intervals",
        "source_id": "a-1",
        "date": day,
        "start_local": f"{day}T07:00:00",
        "sport": "Run",
        "name": "Lockerer Lauf",
        "duration_s": 2580,
        "moving_s": 2520,
        "distance_m": None,
        "elevation_m": None,
        "avg_hr": None,
        "max_hr": None,
        "avg_power": None,
        "np": None,
        "calories": None,
        "load": 40,
        "intensity": None,
        "raw": None,
    }


def _relationship(activity_day_ref: str = "1") -> TrainingRelationship:
    return TrainingRelationship(
        relationship_id=RelationshipId("rel:1"),
        plan=PlanReference(PlanId("plan:event:1"), "default", "default"),
        activities=(
            ActivityReference(ActivityId(activity_day_ref), "default", "default"),
        ),
        status=RelationshipStatus.CONFIRMED,
        completion_confirmed=True,
    )


def test_bestaetigte_beziehung_ist_eine_primere_aufzeichnung_ohne_doppelzaehlung() -> None:
    period = planner_week_range("2026-11-08", "Europe/Vienna")
    payload = build_planner_week(
        period,
        [_plan_row()],
        [_activity_row()],
        today="2026-11-08",
        time_zone="Europe/Vienna",
        relationships=[_relationship()],
    )

    assert [entry["kind"] for entry in payload["entries"]] == ["linked"]
    assert payload["entries"][0]["actual"]["seconds"] == 2520
    assert payload["entries"][0]["plan"]["name"] == "Lockerer Lauf"
    assert payload["summary"]["recorded"]["seconds"] == 2520
    assert payload["summary"]["open_plan"]["count"] == 0


def test_belegter_abschluss_ausserhalb_der_woche_zaehlt_keine_ist_zeit() -> None:
    period = planner_week_range("2026-11-08", "Europe/Vienna")
    payload = build_planner_week(
        period,
        [_plan_row()],
        [_activity_row("2026-11-09")],
        today="2026-11-08",
        time_zone="Europe/Vienna",
        relationships=[_relationship()],
    )

    assert [entry["kind"] for entry in payload["entries"]] == ["completionReference"]
    entry = payload["entries"][0]
    assert entry["date"] == "2026-11-08"
    assert entry["compact_text"] == "Erledigt am 9. November"
    assert payload["summary"]["recorded"]["seconds"] == 0
    assert payload["summary"]["open_plan"]["count"] == 0
