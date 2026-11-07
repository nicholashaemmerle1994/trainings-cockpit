"""P04: Remote-Leseadapter, Erhaltungsregeln und Anzeigeprojektion."""

from __future__ import annotations

from dataclasses import replace

import pytest
from planner_fixtures import load_case, load_remote

from trainings_cockpit.planner import (
    CompletionReferenceListEntry,
    DistanceEnd,
    Editability,
    LinkedListEntry,
    NotAPlannedWorkout,
    PaceTarget,
    PaceUnit,
    PlanId,
    PlannedWorkout,
    PlanReference,
    RelationshipId,
    RelationshipProjectionError,
    RelationshipStatus,
    RestrictionCode,
    StepNode,
    StepRole,
    TimeEnd,
    TrainingRelationship,
    UnsupportedNode,
    Value,
    ValueRange,
    ZoneMetric,
    ZoneTarget,
    activity_date,
    activity_reference_from_record,
    calculate_known_totals,
    format_totals,
    iter_nodes,
    read_remote_event,
    recorded_entry_from_record,
    relationship_entries,
    sport_label,
)

ACCOUNT = "fixture-account"
ATHLETE = "fixture-athlete"
FETCHED = "2026-11-08T09:15:00+01:00"


def read_event(name: str):
    event = load_remote(name)["event"]
    return read_remote_event(
        event,
        fetched_at=FETCHED,
        time_zone="Europe/Vienna",
        account_id=ACCOUNT,
        athlete_id=ATHLETE,
        zone_sets={"Run": "run-hr", "Ride": "ride-hr", "Swim": "swim-hr"},
    )


def test_f01_liest_identitaet_termin_aufbau_und_quelle() -> None:
    event = load_remote("simple-zone-run.json")["event"]
    result = read_event("simple-zone-run.json")
    plan = result.plan

    assert plan.remote_id is not None
    assert str(plan.remote_id) == "9101"
    assert plan.name == "Ruhiger Dauerlauf"
    assert plan.sport == "Run"
    assert plan.date == "2026-11-02"
    assert plan.local_time is None
    assert plan.time_zone == "Europe/Vienna"
    assert len(plan.nodes) == 1
    assert isinstance(plan.nodes[0], StepNode)
    assert plan.nodes[0].end == TimeEnd(2700)
    assert plan.nodes[0].target.zone_id == "run-hr-2"
    assert plan.nodes[0].target.zone_set_id == "run-hr"
    assert plan.editability is Editability.FULL
    assert result.source.raw == event
    assert result.source.raw_workout_text == event["description"]


def test_f02_liest_wiederholung_und_getrennte_ziele() -> None:
    plan = read_event("repeated-intervals.json").plan
    repeat = plan.nodes[1]

    assert [node.kind for node in plan.nodes] == ["step", "repeat", "step"]
    assert repeat.repetitions == 4
    assert [child.name for child in repeat.children] == ["Belastung", "Erholung"]
    assert [child.role for child in repeat.children] == [StepRole.WORK, StepRole.RECOVERY]
    assert isinstance(repeat.children[0].target, PaceTarget)
    assert repeat.children[0].target.unit is PaceUnit.SECONDS_PER_KM
    assert repeat.children[0].target.values == ValueRange(330, 345)
    assert repeat.children[1].target.zone_id == "run-hr-1"
    assert plan.nodes[0].role is StepRole.WARMUP
    assert plan.nodes[-1].role is StepRole.COOLDOWN


def test_f04_distanz_plus_geschaetzte_dauer_bleibt_distanz() -> None:
    event = load_remote("distance-step.json")["event"]
    distance_step = event["workout_doc"]["steps"][1]["steps"][0]
    plan = read_event("distance-step.json").plan
    repeat = plan.nodes[1]
    work = repeat.children[0]

    assert distance_step["duration_source"] == "estimated"
    assert distance_step["duration"] == 348
    assert isinstance(work.end, DistanceEnd)
    assert work.end.metres == 1000
    assert work.target == PaceTarget(PaceUnit.SECONDS_PER_KM, Value(330))


def _pace_event(*steps: dict, sport: str = "Run", event_id: int = 9130) -> dict:
    return {
        "id": event_id,
        "category": "WORKOUT",
        "start_date_local": "2026-11-07T00:00:00",
        "type": sport,
        "name": "Long Run",
        "description": "-12km Z2 HR\n-5km 5:35-5:44 Pace\n-1km Z2 HR",
        "workout_doc": {"steps": list(steps)},
    }


def test_intervals_pace_in_sekunden_zaehlt_zur_distanz() -> None:
    # Die echte intervals.icu-Antwort schreibt absolute Pace als Sekunden je
    # Referenzstrecke (`secs`), nicht als Minuten mit `min/km`. Der Abschnitt
    # bleibt eine Distanz und zählt deshalb in die Gesamtkilometer.
    event = _pace_event(
        {
            "distance": 12000,
            "duration": 4860,
            "duration_source": "estimated",
            "hr": {"units": "hr_zone", "value": 2},
        },
        {
            "distance": 5000,
            "duration": 1700,
            "duration_source": "estimated",
            "pace": {"units": "secs", "start": 335, "end": 344},
        },
        {
            "distance": 1000,
            "duration": 400,
            "duration_source": "estimated",
            "hr": {"units": "hr_zone", "value": 2},
        },
    )
    result = read_remote_event(
        event,
        fetched_at=FETCHED,
        time_zone="Europe/Vienna",
        zone_sets={"Run": "run-hr"},
    )
    plan = result.plan
    pace_step = plan.nodes[1]

    assert plan.editability is Editability.FULL
    assert not any(isinstance(node, UnsupportedNode) for node in plan.nodes)
    assert isinstance(pace_step, StepNode)
    assert pace_step.end == DistanceEnd(5000)
    assert pace_step.target == PaceTarget(
        PaceUnit.SECONDS_PER_KM, ValueRange(335, 344)
    )

    totals = calculate_known_totals(plan)
    assert totals.distance_metres == 18000
    assert totals.executions == 3
    assert totals.has_unknown is False
    assert format_totals(totals) == "18 km"


def test_secs_ohne_referenz_folgt_der_sportart() -> None:
    run = read_remote_event(
        _pace_event(
            {"distance": 1000, "duration": 340, "pace": {"units": "secs", "value": 340}},
            event_id=9131,
        ),
        fetched_at=FETCHED,
        time_zone="Europe/Vienna",
    ).plan
    swim = read_remote_event(
        _pace_event(
            {"distance": 400, "duration": 480, "pace": {"units": "secs", "value": 120}},
            sport="Swim",
            event_id=9132,
        ),
        fetched_at=FETCHED,
        time_zone="Europe/Vienna",
    ).plan

    assert run.nodes[0].target == PaceTarget(PaceUnit.SECONDS_PER_KM, Value(340))
    assert swim.nodes[0].target == PaceTarget(PaceUnit.SECONDS_PER_100M, Value(120))


def test_secs_mit_ausdruecklicher_referenz_gewinnt_gegen_die_sportart() -> None:
    plan = read_remote_event(
        _pace_event(
            {
                "distance": 200,
                "duration": 240,
                "pace": {"units": "secs/100m", "start": 118, "end": 124},
            },
            sport="Run",
            event_id=9133,
        ),
        fetched_at=FETCHED,
        time_zone="Europe/Vienna",
    ).plan

    assert plan.nodes[0].target == PaceTarget(
        PaceUnit.SECONDS_PER_100M, ValueRange(118, 124)
    )



def test_distanz_mit_berechneter_dauer_ohne_quelle_bleibt_distanz() -> None:
    # Die echte intervals.icu-Antwort auf eine vom Nutzer vorgegebene Distanz
    # trägt beide Werte, aber keine Quelle: `distance` ist die Vorgabe,
    # `duration` die von intervals berechnete Schätzung. Nur eine Quelle würde
    # belegen, dass die Dauer die Ende-Bedingung ist.
    event = {
        "id": 9121,
        "category": "WORKOUT",
        "start_date_local": "2026-11-06T00:00:00",
        "type": "Run",
        "name": "10 km Zone 2",
        "description": "- Obere Zone zwei 10000mtr Z2 HR",
        "external_id": "fixture:distanz-berechnete-dauer",
        "workout_doc": {
            "steps": [
                {
                    "text": "Obere Zone zwei",
                    "distance": 10000,
                    "duration": 3000,
                    "hr": {"units": "hr_zone", "value": 2},
                }
            ],
            "distance": 10000,
            "duration": 3000,
        },
    }

    result = read_remote_event(
        event,
        fetched_at=FETCHED,
        time_zone="Europe/Vienna",
        zone_sets={"Run": "run-hr"},
    )
    plan = result.plan

    assert plan.editability is Editability.FULL
    assert plan.is_structure_editable is True
    assert RestrictionCode.UNKNOWN_CONTENT not in plan.restriction_codes
    assert not any(isinstance(node, UnsupportedNode) for node in plan.nodes)

    assert len(plan.nodes) == 1
    node = plan.nodes[0]
    assert isinstance(node, StepNode)
    assert node.end == DistanceEnd(10000)
    assert node.target == ZoneTarget(ZoneMetric.HEART_RATE, "run-hr-2", "run-hr")
    assert result.source.raw == event


def test_zeitvorgabe_mit_geschaetzter_distanz_bleibt_zeit() -> None:
    # Gegenrichtung der expliziten Regel: intervals kennzeichnet die Distanz
    # als Schätzung zur vorgegebenen Dauer. Dann bleibt die Dauer das Ende.
    event = {
        "id": 9122,
        "category": "WORKOUT",
        "start_date_local": "2026-11-06T00:00:00",
        "type": "Run",
        "name": "30 Minuten locker",
        "description": "- 30m Z2 HR",
        "workout_doc": {
            "steps": [
                {
                    "text": "Dauerlauf",
                    "duration": 1800,
                    "distance": 5000,
                    "distance_source": "estimated",
                    "hr": {"units": "hr_zone", "value": 2},
                }
            ]
        },
    }

    result = read_remote_event(
        event,
        fetched_at=FETCHED,
        time_zone="Europe/Vienna",
        zone_sets={"Run": "run-hr"},
    )
    node = result.plan.nodes[0]

    assert isinstance(node, StepNode)
    assert node.end == TimeEnd(1800)
    assert result.plan.editability is Editability.FULL


def test_berechnete_felder_verdecken_echtes_unbekanntes_feld_nicht() -> None:
    # Die Positivliste der berechneten Felder darf nur diese Felder ausnehmen.
    # Ein zusätzliches, echtes unbekanntes Feld muss weiterhin begrenzen und
    # in der Begründung stehen — sonst würde die Subtraktion zu breit wirken.
    event = {
        "id": 9123,
        "category": "WORKOUT",
        "start_date_local": "2026-11-06T00:00:00",
        "type": "Run",
        "name": "Gemischte Felder",
        "workout_doc": {
            "steps": [{"text": "Dauerlauf", "duration": 2700}],
            "locales": [],
            "distance": 0,
            "duration": 2700,
            "average_watts": 0,
            "unknown_doc_field": {"keep": True},
        },
    }

    result = read_remote_event(
        event,
        fetched_at=FETCHED,
        time_zone="Europe/Vienna",
        zone_sets={"Run": "run-hr"},
    )
    plan = result.plan

    assert plan.editability is Editability.METADATA_ONLY
    assert RestrictionCode.UNKNOWN_CONTENT in plan.restriction_codes
    assert plan.editability_reason is not None
    assert "unknown_doc_field" in plan.editability_reason
    assert "average_watts" not in plan.editability_reason
    assert "Unbekannte Dokumentfelder: unknown_doc_field" in plan.editability_reason


def test_f07_erhaelt_unbekanntes_und_begrenzt_die_editierbarkeit() -> None:
    event = load_remote("unknown-content.json")["event"]
    result = read_event("unknown-content.json")
    plan = result.plan
    unsupported = [node for node in iter_nodes(plan.nodes) if isinstance(node, UnsupportedNode)]

    assert [node.kind for node in plan.nodes] == ["step", "unsupported", "unsupported"]
    assert len(unsupported) == 2
    assert all(node.source_ref.startswith("/workout_doc/steps/") for node in unsupported)
    assert plan.local_time == "09:15"
    assert plan.editability is Editability.METADATA_ONLY
    assert plan.is_metadata_editable is True
    assert plan.is_structure_editable is False
    assert RestrictionCode.UNKNOWN_CONTENT in plan.restriction_codes
    assert RestrictionCode.MULTIPLE_TARGETS in plan.restriction_codes
    assert RestrictionCode.RAMP_OR_SPECIAL_STEP in plan.restriction_codes
    assert plan.notes == "Importierte Zusatznotiz, absichtlich nicht strukturiert."

    assert result.source.raw == event
    assert result.source.raw["workout_doc"]["unknown_doc_field"] == {"keep": ["a", "b", 3]}
    assert result.source.raw["weather"]["wind"] == "unbekannt"
    assert result.source.raw_workout_text == event["description"]

    renamed = replace(plan, name="Sicher umbenannt")
    assert renamed.nodes == plan.nodes
    assert result.source.raw == event


def test_zeit_workout_mit_berechneten_dokumentfeldern_bleibt_voll_editierbar() -> None:
    # intervals.icu hängt an jedes `workout_doc` berechnete Zusammenfassungen an
    # (Totals, Zonenzeiten, Leistungskennzahlen). Sie sind nicht Teil des
    # Schreibvertrags und dürfen die Strukturbearbeitung nicht begrenzen.
    event = {
        "id": 9120,
        "category": "WORKOUT",
        "start_date_local": "2026-11-02T00:00:00",
        "type": "Run",
        "name": "Ruhiger Dauerlauf",
        "description": "- Dauerlauf 45m Z2 HR",
        "external_id": "fixture:derived-fields",
        "workout_doc": {
            "steps": [
                {
                    "text": "Dauerlauf",
                    "duration": 2700,
                    "hr": {"units": "hr_zone", "value": 2},
                }
            ],
            "locales": [],
            "options": {},
            "distance": 0,
            "duration": 2700,
            "zoneTimes": [
                {"id": "Z1", "secs": 0},
                {"id": "Z2", "secs": 2700},
                {"id": "Z3", "secs": 0},
                {"id": "Z4", "secs": 0},
                {"id": "Z5", "secs": 0},
            ],
            "strain_score": None,
            "average_watts": 0,
            "normalized_power": 0,
            "variability_index": None,
            "polarization_index": 0,
        },
    }

    result = read_remote_event(
        event,
        fetched_at=FETCHED,
        time_zone="Europe/Vienna",
        zone_sets={"Run": "run-hr"},
    )
    plan = result.plan

    assert plan.editability is Editability.FULL
    assert plan.is_structure_editable is True
    assert plan.editability_reason is None
    assert plan.restriction_codes == ()
    assert RestrictionCode.UNKNOWN_CONTENT not in plan.restriction_codes

    assert len(plan.nodes) == 1
    node = plan.nodes[0]
    assert isinstance(node, StepNode)
    assert node.end == TimeEnd(2700)
    assert node.target.zone_id == "run-hr-2"
    assert node.target.zone_set_id == "run-hr"

    # Die berechneten Felder bleiben unverändert im Roh-Snapshot erhalten.
    assert result.source.raw == event
    assert result.source.raw["workout_doc"]["zoneTimes"][1] == {"id": "Z2", "secs": 2700}
    assert result.source.raw["workout_doc"]["duration"] == 2700


def test_unbekannte_sportart_bleibt_neutral_und_lesbar() -> None:
    event = {
        "id": 9901,
        "category": "WORKOUT",
        "start_date_local": "2026-11-10T17:00:00",
        "type": "UnderwaterHockey",
        "name": "Unbekannte Einheit",
        "workout_doc": {"steps": [{"text": "Spielen", "duration": 600}]},
    }
    result = read_remote_event(
        event,
        fetched_at=FETCHED,
        time_zone="Europe/Vienna",
    )

    assert result.plan.sport == "UnderwaterHockey"
    assert sport_label(result.plan.sport) == "Andere Sportart"
    assert result.plan.local_time == "17:00"
    assert isinstance(result.plan.nodes[0], StepNode)


def test_fehlgeleitete_remote_zone_bleibt_als_unbekannt_erhalten() -> None:
    event = {
        "id": 9903,
        "category": "WORKOUT",
        "start_date_local": "2026-11-10T18:00:00",
        "type": "Run",
        "name": "Unklare Zone",
        "workout_doc": {
            "steps": [
                {
                    "text": "Dauerlauf",
                    "duration": 600,
                    "hr": {"units": "hr_zone", "value": 0},
                }
            ]
        },
    }
    result = read_remote_event(event, fetched_at=FETCHED, time_zone="Europe/Vienna")

    assert isinstance(result.plan.nodes[0], UnsupportedNode)
    assert result.plan.editability is Editability.METADATA_ONLY
    assert RestrictionCode.UNKNOWN_CONTENT in result.plan.restriction_codes


def test_remote_schreibrecht_wird_beruecksichtigt() -> None:
    event = load_remote("simple-zone-run.json")["event"]
    result = read_remote_event(
        event,
        fetched_at=FETCHED,
        time_zone="Europe/Vienna",
        writable=False,
    )

    assert result.plan.editability is Editability.READ_ONLY
    assert result.plan.is_metadata_editable is False
    assert RestrictionCode.REMOTE_READ_ONLY in result.plan.restriction_codes
    assert result.plan.editability_reason


def test_nicht_workout_event_wird_nicht_als_planung_gelesen() -> None:
    event = {
        "id": 9902,
        "category": "NOTE",
        "start_date_local": "2026-11-10",
        "type": "Run",
        "name": "Notiz",
    }
    with pytest.raises(NotAPlannedWorkout):
        read_remote_event(event, fetched_at=FETCHED, time_zone="Europe/Vienna")


def test_aufzeichnung_bleibt_auf_dem_aktivitaetspfad() -> None:
    case = load_case("F15")
    record = case["activities"][2]
    reference = activity_reference_from_record(
        record,
        account_id=ACCOUNT,
        athlete_id=ATHLETE,
    )
    entry = recorded_entry_from_record(record, account_id=ACCOUNT, athlete_id=ATHLETE)

    assert record["sport"] == "WeightTraining"
    assert sport_label(record["sport"]) == "Kraft"
    assert reference.activity_id.value == record["activityId"]
    assert entry.date == "2026-11-04"
    assert not isinstance(reference, PlannedWorkout)
    assert entry.kind == "recorded"

    # Zwei Quellabbilder derselben Aufzeichnung bleiben eine kanonische Referenz.
    f12 = load_case("F12")["activities"][0]
    merged = activity_reference_from_record(f12, account_id=ACCOUNT, athlete_id=ATHLETE)
    assert merged.activity_id.value == "123"
    assert len(merged.source_refs) == 2
    assert {ref.source for ref in merged.source_refs} == {"garmin", "intervals"}
    assert activity_date(f12) == "2026-11-08"


def test_f12_projiziert_bestaetigte_beziehung_ohne_zweite_aufzeichnung() -> None:
    case = load_case("F12")
    p1 = case["plans"][0]
    a1 = case["activities"][0]
    plan_ref = PlanReference(PlanId(p1["localId"]), ACCOUNT, ATHLETE)
    activity = activity_reference_from_record(a1, account_id=ACCOUNT, athlete_id=ATHLETE)
    relation = TrainingRelationship(
        relationship_id=RelationshipId("rel:1"),
        plan=plan_ref,
        activities=(activity,),
        status=RelationshipStatus.CONFIRMED,
        completion_confirmed=True,
    )

    entries = relationship_entries(relation, p1["date"], {activity.key: a1["date"]})
    kinds = [entry.kind for entry in entries]

    assert kinds == ["linked"]
    assert isinstance(entries[0], LinkedListEntry)
    assert entries[0].date == "2026-11-08"
    assert entries[0].activities == (activity,)


def test_f13_projiziert_erledigt_hinweis_am_plantermin() -> None:
    case = load_case("F13")
    plan_ref = PlanReference(PlanId("plan:P1"), ACCOUNT, ATHLETE)
    activity = activity_reference_from_record(
        case["activities"][0], account_id=ACCOUNT, athlete_id=ATHLETE
    )
    relation = TrainingRelationship(
        relationship_id=RelationshipId("rel:1301"),
        plan=plan_ref,
        activities=(activity,),
        status=RelationshipStatus.CONFIRMED,
        completion_confirmed=True,
    )

    entries = relationship_entries(relation, "2026-11-08", {activity.key: "2026-11-09"})

    assert [entry.kind for entry in entries] == ["linked", "completionReference"]
    linked, completion = entries
    assert linked.date == "2026-11-09"
    assert isinstance(completion, CompletionReferenceListEntry)
    assert completion.date == "2026-11-08"
    assert completion.activity_dates == ("2026-11-09",)
    assert completion.plan.plan_id == plan_ref.plan_id


def test_offene_beziehung_erzeugt_keinen_erledigt_eintrag() -> None:
    case = load_case("F13")
    plan_ref = PlanReference(PlanId("plan:P1"), ACCOUNT, ATHLETE)
    activity = activity_reference_from_record(
        case["activities"][0], account_id=ACCOUNT, athlete_id=ATHLETE
    )
    partial = TrainingRelationship(
        relationship_id=RelationshipId("rel:partial"),
        plan=plan_ref,
        activities=(activity,),
        status=RelationshipStatus.PARTIAL,
        completion_confirmed=False,
    )

    assert relationship_entries(partial, "2026-11-08", {activity.key: "2026-11-09"}) == ()

    with pytest.raises(RelationshipProjectionError):
        confirmed = replace(
            partial,
            status=RelationshipStatus.CONFIRMED,
            completion_confirmed=True,
        )
        relationship_entries(confirmed, "2026-11-08", {})
