"""P05: Parser, Validierung, Ausführungsfolge, Summen und Wochenprojektion."""

from __future__ import annotations

from dataclasses import replace

import pytest
from planner_fixtures import build_plan_from_case, load_case, load_remote

from trainings_cockpit.planner import (
    FieldKind,
    FieldValidity,
    HeartRateTarget,
    NoTarget,
    PaceTarget,
    PaceUnit,
    PlanId,
    PowerTarget,
    PowerUnit,
    RelationshipId,
    RelationshipStatus,
    RepeatNode,
    StepRole,
    TimeEnd,
    TrainingRange,
    TrainingRelationship,
    ValidationCode,
    Value,
    ValueRange,
    WorkoutDraft,
    WriteBoundaryError,
    ZoneMetric,
    ZoneTarget,
    build_week_projection,
    build_week_summary,
    calculate_known_totals,
    completion_text,
    derive_execution_sequence,
    format_distance,
    format_duration,
    format_pace,
    format_target,
    format_totals,
    open_plan_totals,
    parse_decimal,
    parse_distance,
    parse_duration,
    parse_field_input,
    parse_pace,
    parse_pace_range,
    parse_value_range,
    plan_record,
    planner_week_range,
    read_remote_event,
    recorded_activity_from_record,
    recorded_seconds,
    relationship_actuals,
    require_planned_draft,
    rolling_dashboard_range,
    validate_workout,
)

ACCOUNT = "fixture-account"
ATHLETE = "fixture-athlete"


def case_plan(case_id: str):
    return build_plan_from_case(load_case(case_id))


def simple_plan(raw: dict, *, time_zone: str):
    """Baut für F11/F13 einen Plan mit der angegebenen Dauer."""
    remote = str(raw.get("remoteId") or raw.get("id"))
    local = raw.get("localId") or f"plan:{remote}"
    duration = raw.get("durationSeconds") or 2700
    from trainings_cockpit.planner import PlannedWorkout, StepNode

    return PlannedWorkout(
        local_id=local,
        remote_id=remote,
        name=raw.get("name") or "",
        sport=raw.get("sport") or "Run",
        date=raw["date"],
        time_zone=time_zone,
        nodes=(
            StepNode(
                id=f"node:{local}:only",
                name=raw.get("name") or "Einheit",
                end=TimeEnd(duration),
            ),
        ),
    )


def plan_record_for(raw: dict, *, time_zone: str):
    plan = simple_plan(raw, time_zone=time_zone)
    return plan_record(plan, account_id=ACCOUNT, athlete_id=ATHLETE)


def activity_record(raw: dict):
    return recorded_activity_from_record(raw, account_id=ACCOUNT, athlete_id=ATHLETE)


def relationship_for(
    plan_record_value,
    activities,
    *,
    relationship_id: str,
    status: RelationshipStatus = RelationshipStatus.CONFIRMED,
    completion: bool = True,
) -> TrainingRelationship:
    return TrainingRelationship(
        RelationshipId(relationship_id),
        plan_record_value.reference,
        tuple(activity.reference for activity in activities),
        status=status,
        completion_confirmed=completion,
    )


# ------------------------------------------------------------------ Parser


def test_gemeinsame_parser_lesen_deutsche_und_technische_formen() -> None:
    assert parse_duration("45") == 2700
    assert parse_duration("45m") == 2700
    assert parse_duration("1h 30m") == 5400
    assert parse_duration("1:30") == 5400
    assert parse_duration("1:30:00") == 5400
    assert parse_duration("90s") == 90
    assert parse_duration("1,5h") == 5400
    assert parse_decimal("1,5") == 1.5
    assert parse_decimal("5.5") == 5.5
    assert parse_distance("10km") == 10000
    assert parse_distance("1000m") == 1000
    assert parse_distance("1,5 km") == 1500
    assert parse_distance("1.000 m") == 1000
    assert parse_pace("5:30") == 330
    assert parse_pace("5:30 min/km") == 330
    assert parse_pace("5,5") == 330
    assert parse_pace("2:00 /100 m", PaceUnit.SECONDS_PER_100M) == 120
    assert parse_pace_range("5:30-5:45 min/km") == ValueRange(330, 345)
    assert parse_pace_range("2:00-2:15 /100 m", PaceUnit.SECONDS_PER_100M) == ValueRange(120, 135)
    assert parse_value_range("0") == Value(0)
    assert parse_value_range("160-170") == ValueRange(160, 170)
    assert parse_value_range("60-90%") == ValueRange(60, 90)


def test_ungueltige_parserwerte_werden_nicht_zu_null() -> None:
    for text in ("", "0", "1x", "1h 30"):
        with pytest.raises(ValueError):
            parse_duration(text)
    for text in ("", "0m", "1x"):
        with pytest.raises(ValueError):
            parse_distance(text)
    for text in ("", "0:00", "5:99", "schnell"):
        with pytest.raises(ValueError):
            parse_pace(text)
    with pytest.raises(ValueError):
        parse_value_range("170-160")


def test_feldvalidierung_trennt_unvollstaendig_und_ungueltig() -> None:
    empty = parse_field_input("", FieldKind.VALUE_RANGE)
    zero = parse_field_input("0", FieldKind.VALUE_RANGE)
    invalid = parse_field_input("abc", FieldKind.DURATION)
    incomplete = parse_field_input("4", FieldKind.DURATION)

    assert empty.validity is FieldValidity.INCOMPLETE
    assert empty.parsed is None
    assert empty.message == "Wert fehlt."
    assert zero.validity is FieldValidity.VALID
    assert zero.parsed == Value(0)
    assert invalid.validity is FieldValidity.INVALID
    assert invalid.parsed is None
    # „4“ ist als Dauer vier Minuten, also vollständig – nicht unvollständig.
    assert incomplete.validity is FieldValidity.VALID
    assert incomplete.parsed == 240


def test_zielformatierung_unterscheidet_null_wert_fehlend_und_ohne_ziel() -> None:
    assert format_target(None) == "Wert fehlt"
    assert format_target(NoTarget()) == "Ohne Ziel"
    assert format_target(PowerTarget(PowerUnit.WATTS, Value(0))) == "0 W"
    assert format_target(PowerTarget(PowerUnit.WATTS, ValueRange(160, 170))) == "160–170 W"
    assert format_target(PowerTarget(PowerUnit.PERCENT_FTP, ValueRange(60, 90))) == "60–90 % FTP"
    assert format_target(HeartRateTarget(ValueRange(140, 150))) == "140–150 bpm"
    assert format_target(PaceTarget(PaceUnit.SECONDS_PER_KM, Value(330))) == "5:30 min/km"
    assert (
        format_target(PaceTarget(PaceUnit.SECONDS_PER_KM, ValueRange(330, 345)))
        == "5:30–5:45 min/km"
    )
    assert (
        format_target(PaceTarget(PaceUnit.SECONDS_PER_100M, Value(120)))
        == "2:00 /100 m"
    )
    assert format_target(ZoneTarget(ZoneMetric.HEART_RATE, "run-hr-2")) == "Zone 2"


def test_praezision_bleibt_bis_zur_formatierung_exakt() -> None:
    assert format_duration(2160) == "36 min"
    assert format_duration(2040) == "34 min"
    assert format_duration(6600) == "1 h 50 min"
    assert format_duration(10800) == "3 h"
    assert format_duration(90) == "1 min 30 s"
    assert format_distance(4000) == "4 km"
    assert format_distance(800) == "800 m"
    assert format_distance(1500) == "1,5 km"
    assert format_pace(330) == "5:30 min/km"
    assert format_pace(120, PaceUnit.SECONDS_PER_100M) == "2:00 /100 m"


# ------------------------------------------------------------------ F01–F07


def test_f01_liefert_eine_ausfuehrung_und_2700_sekunden() -> None:
    plan = case_plan("F01")
    totals = calculate_known_totals(plan)
    sequence = derive_execution_sequence(plan)

    assert totals.duration_seconds == 2700
    assert totals.distance_metres == 0
    assert totals.executions == 1
    assert totals.has_unknown is False
    assert len(sequence.executions) == 1
    assert sequence.executions[0].node_id == plan.nodes[0].id
    assert sequence.executions[0].repetition_index is None
    assert sequence.executions[0].position == 0
    assert validate_workout(plan).valid is True
    assert format_totals(totals) == "45 min"


def test_f02_wiederholungssemantik_einschliesslich_letzter_erholung() -> None:
    plan = case_plan("F02")
    totals = calculate_known_totals(plan)
    sequence = derive_execution_sequence(plan)

    assert (totals.duration_seconds, totals.executions) == (2160, 10)
    assert [step.role for step in sequence.executions] == [
        StepRole.WARMUP,
        StepRole.WORK,
        StepRole.RECOVERY,
        StepRole.WORK,
        StepRole.RECOVERY,
        StepRole.WORK,
        StepRole.RECOVERY,
        StepRole.WORK,
        StepRole.RECOVERY,
        StepRole.COOLDOWN,
    ]
    assert [step.repetition_index for step in sequence.executions[1:9]] == [
        1,
        1,
        2,
        2,
        3,
        3,
        4,
        4,
    ]

    main = next(node for node in plan.nodes if isinstance(node, RepeatNode))
    skipped_main = replace(main, skip_final_recovery=True)
    skipped_plan = replace(plan, nodes=(plan.nodes[0], skipped_main, plan.nodes[2]))
    skipped = calculate_known_totals(skipped_plan)
    skipped_sequence = derive_execution_sequence(skipped_plan)
    assert (skipped.duration_seconds, skipped.executions) == (2040, 9)
    assert len(skipped_sequence.executions) == 9
    assert skipped_sequence.executions[-1].role is StepRole.COOLDOWN

    longer = replace(main.children[0], end=TimeEnd(180))
    longer_plan = replace(
        plan,
        nodes=(plan.nodes[0], replace(main, children=(longer, main.children[1])), plan.nodes[2]),
    )
    assert (calculate_known_totals(longer_plan).duration_seconds,
            calculate_known_totals(longer_plan).executions) == (2400, 10)

    without_group = replace(plan, nodes=(plan.nodes[0], plan.nodes[2]))
    assert (calculate_known_totals(without_group).duration_seconds,
            calculate_known_totals(without_group).executions) == (1200, 2)


def test_f03_haelt_0_watt_als_gueltigen_wert() -> None:
    plan = case_plan("F03")
    totals = calculate_known_totals(plan)

    assert (totals.duration_seconds, totals.executions) == (3900, 8)
    zero = PowerTarget(PowerUnit.WATTS, Value(0))
    assert format_target(zero) == "0 W"
    assert zero.values.value == 0


def test_f04_mischt_zeit_und_distanz_ohne_schaetzung() -> None:
    plan = case_plan("F04")
    totals = calculate_known_totals(plan)

    assert totals.duration_seconds == 1680
    assert totals.distance_metres == 4000
    assert totals.executions == 10
    assert totals.is_mixed is True
    assert totals.first_end == "time"
    assert format_totals(totals) == "28 min + 4 km"
    assert validate_workout(plan).valid is True


def test_f05_schwimmpace_und_gemischte_achse() -> None:
    plan = case_plan("F05")
    totals = calculate_known_totals(plan)

    assert totals.distance_metres == 800
    assert totals.duration_seconds == 240
    assert totals.executions == 16
    assert totals.first_end == "distance"
    assert format_totals(totals) == "800 m + 4 min"
    work = derive_execution_sequence(plan).executions[0]
    assert isinstance(work.target, PaceTarget)
    assert work.target.unit is PaceUnit.SECONDS_PER_100M
    assert work.target.values == Value(120)


def test_f06_alle_drei_leeren_formen_werden_beim_speichern_abgewiesen() -> None:
    case = load_case("F06")
    plans = [build_plan_from_case({"plan": entry["plan"]}) for entry in case["plans"]]
    expected_codes = [
        ValidationCode.EMPTY_WORKOUT,
        ValidationCode.EMPTY_REPEAT,
        ValidationCode.NO_EXECUTED_STEPS,
    ]

    for plan, expected in zip(plans, expected_codes, strict=True):
        validation = validate_workout(plan)
        assert validation.valid is False
        assert expected in validation.codes
        assert calculate_known_totals(plan).executions == 0
        assert derive_execution_sequence(plan).executions == ()
        with pytest.raises(WriteBoundaryError):
            require_planned_draft(WorkoutDraft.new(plan))


def test_f07_begrenzt_struktur_bearbeitung_aber_erlaubt_sichere_metadaten() -> None:
    event = load_remote("unknown-content.json")["event"]
    source = read_remote_event(
        event,
        fetched_at="2026-11-08T09:15:00+01:00",
        time_zone="Europe/Vienna",
    )
    base = source.plan

    structure = validate_workout(base)
    metadata = validate_workout(base, mode="metadata")
    assert structure.valid is False
    assert ValidationCode.UNSUPPORTED_CONTENT in structure.codes
    assert metadata.valid is True

    draft = WorkoutDraft.start(base, source.source)
    draft.current = replace(draft.current, name="Sicher umbenannt")
    assert require_planned_draft(draft) is draft

    draft.current = replace(
        draft.current,
        nodes=tuple(reversed(draft.current.nodes)),
    )
    with pytest.raises(WriteBoundaryError):
        require_planned_draft(draft)


def test_grosse_wiederholungszahl_wird_komprimiert_nicht_still_gekuerzt() -> None:
    plan = case_plan("F02")
    main = next(node for node in plan.nodes if isinstance(node, RepeatNode))
    huge = replace(plan, nodes=(plan.nodes[0], replace(main, repetitions=100_000), plan.nodes[2]))

    totals = calculate_known_totals(huge)
    sequence = derive_execution_sequence(huge, max_executions=7)

    assert totals.duration_seconds == 600 + 100_000 * 240 + 600
    assert totals.executions == 200_002
    assert len(sequence.executions) == 7
    assert sequence.total_executions == 200_002
    assert sequence.complete is False
    assert len(sequence.compressions) == 2
    assert sequence.compressions[0].omitted_repetitions == 99_997
    assert sum(item.omitted_executions for item in sequence.compressions) == 199_995
    assert validate_workout(huge).valid is True


# ------------------------------------------------------------------ Summen


def test_ist_dauer_verwendet_die_bestehende_basis() -> None:
    assert recorded_seconds({"moving_s": 3000, "duration_s": 3600}) == 3000
    assert recorded_seconds({"moving_s": None, "duration_s": 3600}) == 3600
    # Die bestehende Definition fällt bei einer 0 auf die Dauer zurück.
    assert recorded_seconds({"moving_s": 0, "duration_s": 3600}) == 3600
    assert recorded_seconds({"movingSeconds": 1800}) == 1800
    assert recorded_seconds({}) == 0


def test_f11_dashboard_und_planer_woche_liefern_verschiedene_summen() -> None:
    case = load_case("F11")
    zone = case["timeZone"]
    activities = [activity_record(row) for row in case["activities"]]
    plans = [plan_record_for(raw, time_zone=zone) for raw in case["plans"]]

    planner_week = planner_week_range("2026-11-02", zone)
    dashboard_week = rolling_dashboard_range("2026-11-06", 7, zone)
    planner = build_week_summary(planner_week, plans, activities)
    dashboard = build_week_summary(dashboard_week, [], activities)

    assert planner.recorded_seconds == 6600
    assert planner.recorded.count == 2
    assert planner.open_plan_seconds == 2700
    assert planner.open_plan.count == 1
    assert dashboard.recorded_seconds == 10800
    assert dashboard.recorded.count == 4
    assert dashboard.open_plan_seconds == 0
    assert format_duration(planner.recorded_seconds) == "1 h 50 min"
    assert format_duration(dashboard.recorded_seconds) == "3 h"
    assert planner_week != dashboard_week


def test_f12_bestaetigte_beziehung_ergibt_42_minuten_und_30_minuten_offen() -> None:
    case = load_case("F12")
    zone = case["timeZone"]
    plans = [plan_record_for(raw, time_zone=zone) for raw in case["plans"]]
    a1 = activity_record(case["activities"][0])
    a2 = activity_record(case["activities"][1])
    relation = relationship_for(plans[0], [a1], relationship_id="rel:1")

    actual = relationship_actuals(relation, [a1, a2])
    open_plans = open_plan_totals(plans, [relation])
    summary = build_week_summary(
        planner_week_range("2026-11-02", zone),
        plans,
        [a1],
        [relation],
    )

    assert actual.seconds == 42 * 60
    assert actual.load == 40
    assert actual.count == 1
    assert open_plans.seconds == 30 * 60
    assert open_plans.count == 1
    assert summary.recorded_seconds == 42 * 60
    assert summary.open_plan_seconds == 30 * 60
    assert summary.completion_references == ()
    assert plans[0].reference.plan_id == PlanId("plan:P1")
    assert a1.reference.activity_id.value == "123"

    multiple = relationship_for(plans[0], [a1, a2], relationship_id="rel:multi")
    multi_actual = relationship_actuals(multiple, [a1, a2])
    assert (multi_actual.count, multi_actual.seconds) == (2, 4320)
    assert len({activity.key for activity in multi_actual.activities}) == 2

    partial = relationship_for(
        plans[0],
        [a1],
        relationship_id="rel:partial",
        status=RelationshipStatus.PARTIAL,
        completion=False,
    )
    partial_open = open_plan_totals(plans, [partial])
    assert partial_open.seconds == 2700 + 1800
    assert partial_open.count == 2
    assert partial.is_complete is False


def test_f13_zaehlt_die_aufzeichnung_nur_in_ihrer_tatsaechlichen_woche() -> None:
    case = load_case("F13")
    zone = case["timeZone"]
    plans = [plan_record_for(raw, time_zone=zone) for raw in case["plans"]]
    activity = activity_record(case["activities"][0])
    relation = relationship_for(plans[0], [activity], relationship_id="rel:1301")

    plan_week = planner_week_range("2026-11-02", zone)
    activity_week = planner_week_range("2026-11-09", zone)
    plan_summary = build_week_summary(plan_week, plans, [activity], [relation])
    activity_summary = build_week_summary(activity_week, plans, [activity], [relation])
    plan_projection = build_week_projection(plan_week, plans, [activity], [relation])
    activity_projection = build_week_projection(activity_week, plans, [activity], [relation])

    assert plan_summary.recorded_seconds == 0
    assert plan_summary.open_plan_seconds == 0
    assert len(plan_summary.completion_references) == 1
    assert plan_summary.completion_references[0].date == "2026-11-08"
    assert plan_summary.completion_references[0].activity_dates == ("2026-11-09",)
    assert completion_text("2026-11-09") == "Erledigt am 9. November"
    assert [entry.kind for entry in plan_projection.entries] == ["completionReference"]

    assert activity_summary.recorded_seconds == 2520
    assert activity_summary.recorded.count == 1
    assert activity_summary.open_plan_seconds == 0
    assert [entry.kind for entry in activity_projection.entries] == ["linked"]
    assert activity_projection.entries[0].date == "2026-11-09"
    assert plans[0].plan.date == "2026-11-08"
    assert activity.date == "2026-11-09"


def test_f12_projektion_zeigt_bestaetigte_und_offene_planung_getrennt() -> None:
    case = load_case("F12")
    zone = case["timeZone"]
    plans = [plan_record_for(raw, time_zone=zone) for raw in case["plans"]]
    activities = [activity_record(row) for row in case["activities"]]
    relation = relationship_for(plans[0], [activities[0]], relationship_id="rel:1")

    projection = build_week_projection(
        planner_week_range("2026-11-02", zone),
        plans,
        activities,
        [relation],
    )
    kinds = [entry.kind for entry in projection.entries]

    assert kinds.count("linked") == 1
    assert kinds.count("planned") == 1
    assert kinds.count("recorded") == 1
    assert [entry.date for entry in projection.entries] == [
        "2026-11-08",
        "2026-11-08",
        "2026-11-08",
    ]
    assert projection.summary.open_plan_seconds == 30 * 60
    assert projection.summary.recorded_seconds == 42 * 60 + 30 * 60


def test_unbekannte_beziehung_bleibt_sichtbar_und_zaehlt_nicht_als_offen() -> None:
    case = load_case("F12")
    zone = case["timeZone"]
    plans = [plan_record_for(raw, time_zone=zone) for raw in case["plans"]]
    activity = activity_record(case["activities"][0])
    relation = relationship_for(plans[0], [activity], relationship_id="rel:unknown")
    period = planner_week_range("2026-11-02", zone)

    projection = build_week_projection(period, plans, [], [relation])

    assert projection.summary.relationship_issues
    assert projection.summary.open_plan_seconds == 30 * 60
    assert [entry.kind for entry in projection.entries] == ["planned", "planned"]


def test_leere_woche_ist_erst_nach_vollstaendiger_abfrage_eine_null() -> None:
    period = TrainingRange("2026-08-10", "2026-08-16", "Europe/Vienna")
    summary = build_week_summary(period, [], [])
    projection = build_week_projection(period, [], [])

    assert summary.recorded_seconds == 0
    assert summary.recorded.count == 0
    assert summary.open_plan_seconds == 0
    assert summary.open_plan.count == 0
    assert projection.entries == ()
