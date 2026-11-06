"""P02: Fachmodell, Identitäten, Listenprojektion und Schreibgrenze.

Die Tests bauen F01–F07 ausschließlich aus Fixtures und dem Modell auf. Es
gibt keinen Netzwerkaufruf, keine UI und keine Produktivdatenbank.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from datetime import date
from typing import Any

import pytest
from planner_fixtures import (
    build_plan_from_case,
    load_case,
    load_remote,
    snapshot_for_case,
)

from trainings_cockpit import db, metrics
from trainings_cockpit.planner import (
    ActivityId,
    ActivityReference,
    CompletionReferenceListEntry,
    DistanceEnd,
    DraftId,
    Editability,
    FieldBuffer,
    FieldValidity,
    LinkedListEntry,
    NodeId,
    ObjectKind,
    OperationId,
    PaceTarget,
    PaceUnit,
    PlanId,
    PlannedListEntry,
    PlannedWorkout,
    PlanReference,
    PowerTarget,
    PowerUnit,
    RecordedListEntry,
    RelationshipId,
    RelationshipStatus,
    RepeatNode,
    RestrictionCode,
    SourceActivityRef,
    SourceSnapshot,
    StepNode,
    StepRole,
    TimeEnd,
    TrainingRange,
    TrainingRelationship,
    UnsupportedNode,
    Value,
    WorkoutDraft,
    WriteBoundaryError,
    WriteCoordinator,
    iter_nodes,
    list_entry_key,
    require_planned_draft,
)

ACCOUNT = "fixture-account"
ATHLETE = "fixture-athlete"


def executed_steps(plan: PlannedWorkout) -> list[StepNode]:
    def expand(nodes: tuple[Any, ...]) -> list[StepNode]:
        out: list[StepNode] = []
        for node in nodes:
            if isinstance(node, StepNode):
                out.append(node)
            elif isinstance(node, RepeatNode):
                for repetition in range(node.repetitions):
                    children = node.children
                    if node.skip_final_recovery and repetition == node.repetitions - 1:
                        last = children[-1] if children else None
                        if isinstance(last, StepNode) and last.role is StepRole.RECOVERY:
                            children = children[:-1]
                    out.extend(expand(children))
        return out

    return expand(plan.nodes)


def known_duration(plan: PlannedWorkout) -> float:
    return sum(step.end.seconds for step in executed_steps(plan) if isinstance(step.end, TimeEnd))


def known_distance(plan: PlannedWorkout) -> float:
    return sum(
        step.end.metres for step in executed_steps(plan) if isinstance(step.end, DistanceEnd)
    )


def structural_steps(plan: PlannedWorkout) -> list[StepNode]:
    return [node for node in iter_nodes(plan.nodes) if isinstance(node, StepNode)]


def plan_reference(value: str = "123", sport: str = "Run") -> PlanReference:
    return PlanReference(PlanId(value), ACCOUNT, ATHLETE)


def activity_reference(value: str = "123") -> ActivityReference:
    return ActivityReference(
        ActivityId(value),
        ACCOUNT,
        ATHLETE,
        source_refs=(
            SourceActivityRef("garmin", f"garmin-{value}"),
            SourceActivityRef("intervals", f"intervals-{value}"),
        ),
    )


def test_f01_ist_ein_zusammenhaengender_zone_2_lauf() -> None:
    plan = build_plan_from_case(load_case("F01"))
    steps = executed_steps(plan)

    assert [node.kind for node in plan.nodes] == ["step"]
    assert len(steps) == 1
    assert steps[0].end == TimeEnd(2700)
    assert steps[0].role is StepRole.STEADY
    assert steps[0].target.zone_id == "run-hr-2"
    assert steps[0].target.zone_set_id == "run-hr"
    assert known_duration(plan) == 2700
    assert known_distance(plan) == 0
    assert plan.editability is Editability.FULL


def test_f02_hat_drei_wurzelknoten_und_zehn_ausfuehrungen() -> None:
    plan = build_plan_from_case(load_case("F02"))
    steps = executed_steps(plan)

    assert [node.kind for node in plan.nodes] == ["step", "repeat", "step"]
    assert len(steps) == 10
    assert known_duration(plan) == 2160
    assert [step.role for step in steps] == [
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
    assert isinstance(steps[1].target, PaceTarget)
    assert steps[1].target.unit is PaceUnit.SECONDS_PER_KM
    assert steps[1].target.values.min == 330
    assert steps[1].target.values.max == 345
    assert steps[2].target.zone_id == "run-hr-1"


def test_f02_varianten_bleiben_rechenbar() -> None:
    plan = build_plan_from_case(load_case("F02"))
    main = next(node for node in plan.nodes if isinstance(node, RepeatNode))

    changed = replace(main.children[0], end=TimeEnd(180))
    longer_repeat = replace(main, children=(changed, main.children[1]))
    longer = replace(plan, nodes=(plan.nodes[0], longer_repeat, plan.nodes[2]))
    assert known_duration(longer) == 2400
    assert len(executed_steps(longer)) == 10

    skipped = replace(main, skip_final_recovery=True)
    skipped_plan = replace(plan, nodes=(plan.nodes[0], skipped, plan.nodes[2]))
    assert known_duration(skipped_plan) == 2040
    assert len(executed_steps(skipped_plan)) == 9

    without_group = replace(plan, nodes=(plan.nodes[0], plan.nodes[2]))
    assert known_duration(without_group) == 1200
    assert len(executed_steps(without_group)) == 2


def test_f03_trennt_hf_und_watt_und_haelt_null_watt() -> None:
    plan = build_plan_from_case(load_case("F03"))
    steps = executed_steps(plan)

    assert known_duration(plan) == 3900
    assert len(steps) == 8
    work = next(step for step in steps if step.role is StepRole.WORK)
    assert isinstance(work.target, PowerTarget)
    assert work.target.unit is PowerUnit.WATTS
    assert work.target.values.min == 160
    assert work.target.values.max == 170

    zero = PowerTarget(PowerUnit.WATTS, Value(0))
    assert zero.values.value == 0
    assert zero.unit is PowerUnit.WATTS


def test_f04_behaelt_die_distanz_als_ende_bedingung() -> None:
    plan = build_plan_from_case(load_case("F04"))
    steps = executed_steps(plan)

    assert known_distance(plan) == 4000
    assert known_duration(plan) == 1680
    distance_steps = [step for step in steps if isinstance(step.end, DistanceEnd)]
    assert len(distance_steps) == 4
    assert all(step.end.kind == "distance" for step in distance_steps)
    assert all(step.end.metres == 1000 for step in distance_steps)

    remote = load_remote("distance-step.json")["event"]
    assert remote["workout_doc"]["steps"][1]["steps"][0]["duration_source"] == "estimated"
    assert remote["workout_doc"]["steps"][1]["steps"][0]["duration"] == 348


def test_f05_haelt_schwimmpace_pro_100_meter_getrennt() -> None:
    plan = build_plan_from_case(load_case("F05"))
    steps = executed_steps(plan)
    work = next(step for step in steps if step.role is StepRole.WORK)

    assert known_distance(plan) == 800
    assert known_duration(plan) == 240
    assert len(steps) == 16
    assert work.target.unit is PaceUnit.SECONDS_PER_100M
    assert work.target.values.value == 120
    assert work.target.values.value != 120 * 10  # nicht als Sekunden/km gedeutet


def test_f06_kann_leere_und_tatsaechlich_leere_aufbauten_darstellen() -> None:
    case = load_case("F06")
    plans = [build_plan_from_case({"plan": entry["plan"]}) for entry in case["plans"]]

    assert [len(executed_steps(plan)) for plan in plans] == [0, 0, 0]
    assert [len(structural_steps(plan)) for plan in plans] == [0, 0, 1]
    assert plans[1].nodes[0].children == ()
    assert plans[2].nodes[0].skip_final_recovery is True


def test_f07_erhaelt_unbekannte_knoten_und_den_rohsnapshot() -> None:
    case = load_case("F07")
    plan = build_plan_from_case(case)
    source = snapshot_for_case(case)
    unsupported = [node for node in iter_nodes(plan.nodes) if isinstance(node, UnsupportedNode)]

    assert [node.kind for node in plan.nodes] == ["step", "unsupported", "unsupported"]
    assert len(unsupported) == 2
    assert all(node.source_ref.startswith("/workout_doc/steps/") for node in unsupported)
    assert plan.editability is Editability.METADATA_ONLY
    assert plan.is_metadata_editable is True
    assert plan.is_structure_editable is False
    assert RestrictionCode.UNKNOWN_CONTENT in plan.restriction_codes
    assert RestrictionCode.MULTIPLE_TARGETS in plan.restriction_codes

    assert source.raw == load_remote("unknown-content.json")["event"]
    assert source.raw["workout_doc"]["unknown_doc_field"] == {"keep": ["a", "b", 3]}
    assert source.raw_workout_text == source.raw["description"]
    assert source.relevant_content_hash.startswith("sha256:")

    # Ein reines Öffnen reicht nicht bis zum Schreibkoordinator.
    with pytest.raises(WriteBoundaryError):
        require_planned_draft(ActivityReference(ActivityId("9107"), ACCOUNT, ATHLETE))


def test_basissnapshot_und_feldpuffer_trennen_original_vom_entwurf() -> None:
    plan = build_plan_from_case(load_case("F01"))
    source = snapshot_for_case(load_case("F01"))
    draft = WorkoutDraft.start(
        plan,
        source,
        draft_id="draft:1",
        operation_id="op:1",
    )
    first = draft.current.nodes[0]
    draft.set_field_buffer(
        first.id,
        "end.seconds",
        FieldBuffer(raw="4", parsed=4, validity=FieldValidity.INCOMPLETE, message="Minuten fehlen"),
    )

    assert draft.base == plan
    assert draft.base.nodes[0] == first
    assert draft.current == plan
    assert draft.incomplete_fields == ("node:f01:run:end.seconds",)
    assert draft.local_revision == 1
    assert draft.has_unsaved_changes is True
    assert draft.draft_id == DraftId("draft:1")
    assert draft.operation_id == OperationId("op:1")

    saved_hash = source.relevant_content_hash
    changed = json.loads(json.dumps(source.raw))
    changed["name"] = "lokal verändert"
    changed_snapshot = SourceSnapshot.capture(
        1, changed, fetched_at="2026-11-08T09:15:00+01:00"
    )
    assert changed_snapshot.relevant_content_hash != saved_hash


def test_verschieben_aendert_keine_ids_und_nicht_die_basis() -> None:
    plan = build_plan_from_case(load_case("F02"))
    original_ids = {node.id for node in iter_nodes(plan.nodes)}
    remote_id = plan.remote_id
    draft = WorkoutDraft.start(plan, snapshot_for_case(load_case("F02")))

    draft.move_node("node:f02:cooldown", 0)

    assert [node.id for node in draft.current.nodes] == [
        NodeId("node:f02:cooldown"),
        NodeId("node:f02:warmup"),
        NodeId("node:f02:main"),
    ]
    assert {node.id for node in iter_nodes(draft.current.nodes)} == original_ids
    assert draft.current.remote_id == remote_id
    assert [node.id for node in draft.base.nodes] == [
        NodeId("node:f02:warmup"),
        NodeId("node:f02:main"),
        NodeId("node:f02:cooldown"),
    ]

    draft.move_node("node:f02:recovery", 0)
    repeat = next(node for node in draft.current.nodes if isinstance(node, RepeatNode))
    assert [child.id for child in repeat.children] == [
        NodeId("node:f02:recovery"),
        NodeId("node:f02:work"),
    ]


def test_gleiche_numerische_plan_und_aktivitaets_id_sind_verschieden() -> None:
    plan = plan_reference("123")
    activity = activity_reference("123")
    planned_entry = PlannedListEntry("2026-11-08", plan)
    recorded_entry = RecordedListEntry("2026-11-08", activity)
    linked_entry = LinkedListEntry(
        "2026-11-08",
        plan,
        (activity,),
        RelationshipId("rel:1"),
    )

    assert plan.plan_id.value == activity.activity_id.value == "123"
    assert plan != activity
    assert plan.identity.object_kind is ObjectKind.PLAN
    assert activity.identity.object_kind is ObjectKind.ACTIVITY
    assert plan.key != activity.key
    assert len({planned_entry.key, recorded_entry.key, linked_entry.key}) == 3
    entries = (planned_entry, recorded_entry, linked_entry)
    assert len({list_entry_key(entry) for entry in entries}) == 3
    assert len({plan.key: plan, activity.key: activity}) == 2


def test_f12_haelt_bestaetigte_beziehung_und_offene_planung_getrennt() -> None:
    p1 = plan_reference("123")
    p2 = plan_reference("124")
    a1 = activity_reference("123")
    source_refs = a1.source_refs

    relationship = TrainingRelationship(
        relationship_id=RelationshipId("rel:1"),
        plan=p1,
        activities=(a1,),
        status=RelationshipStatus.CONFIRMED,
        completion_confirmed=True,
    )
    assert relationship.is_complete is True
    assert len(relationship.activities) == 1
    assert len(source_refs) == 2
    assert relationship.activities[0].key == a1.key

    open_plan = PlannedListEntry("2026-11-08", p2)
    completed_plan = LinkedListEntry(
        "2026-11-08",
        p1,
        (a1,),
        relationship.relationship_id,
    )
    assert open_plan.plan.plan_id == PlanId("124")
    assert completed_plan.activities[0].activity_id == ActivityId("123")
    assert open_plan.key != completed_plan.key

    second = activity_reference("a-2")
    multiple = TrainingRelationship(
        relationship_id=RelationshipId("rel:multi"),
        plan=p1,
        activities=(a1, second),
        status=RelationshipStatus.CONFIRMED,
        completion_confirmed=True,
    )
    assert [activity.activity_id for activity in multiple.activities] == [
        ActivityId("123"),
        ActivityId("a-2"),
    ]
    assert len({activity.key for activity in multiple.activities}) == 2

    partial = TrainingRelationship(
        relationship_id=RelationshipId("rel:partial"),
        plan=p1,
        activities=(a1,),
        status=RelationshipStatus.PARTIAL,
        completion_confirmed=False,
    )
    assert partial.is_complete is False
    with pytest.raises(ValueError):
        TrainingRelationship(
            relationship_id=RelationshipId("rel:partial-2"),
            plan=p1,
            activities=(a1,),
            status=RelationshipStatus.PARTIAL,
            completion_confirmed=True,
        )


def test_f13_projiziert_planwoche_und_aktivitaetswoche_ohne_verschmelzung() -> None:
    plan = plan_reference("1301")
    activity = activity_reference("1301")
    relationship = TrainingRelationship(
        relationship_id=RelationshipId("rel:1301"),
        plan=plan,
        activities=(activity,),
        status=RelationshipStatus.CONFIRMED,
        completion_confirmed=True,
    )

    completion = CompletionReferenceListEntry(
        "2026-11-08",
        plan,
        ("2026-11-09",),
        relationship.relationship_id,
    )
    activity_entry = LinkedListEntry(
        "2026-11-09",
        plan,
        (activity,),
        relationship.relationship_id,
    )

    assert completion.date == "2026-11-08"
    assert completion.activity_dates == ("2026-11-09",)
    assert completion.plan.plan_id == PlanId("1301")
    assert activity_entry.date == "2026-11-09"
    assert activity_entry.plan.plan_id == PlanId("1301")
    assert completion.key != activity_entry.key


def test_training_range_ist_inklusive_und_lokal() -> None:
    week = TrainingRange("2026-11-02", "2026-11-08", "Europe/Vienna")

    assert week.contains("2026-11-02") is True
    assert week.contains("2026-11-08") is True
    assert week.contains("2026-11-09") is False
    assert week.key == "range:Europe/Vienna:2026-11-02:2026-11-08"
    with pytest.raises(ValueError):
        TrainingRange("2026-11-08", "2026-11-02", "Europe/Vienna")
    with pytest.raises(ValueError):
        TrainingRange("2026-11-02", "2026-11-08", "Mars/Olympus")


def test_editierbarkeit_braucht_konkrete_gruende() -> None:
    plan = build_plan_from_case(load_case("F01"))

    with pytest.raises(ValueError):
        replace(plan, editability=Editability.READ_ONLY)
    with pytest.raises(ValueError):
        replace(plan, editability=Editability.READ_ONLY, editability_reason="   ")
    read_only = replace(
        plan,
        editability=Editability.READ_ONLY,
        editability_reason="Remote-Schreibrecht fehlt.",
        restriction_codes=(RestrictionCode.REMOTE_READ_ONLY,),
    )
    assert read_only.is_metadata_editable is False
    assert read_only.editability_reason == "Remote-Schreibrecht fehlt."
    with pytest.raises(ValueError):
        replace(plan, editability_reason="Grund ohne Einschränkung")


def test_knoten_ids_sind_eindeutig_und_unveraenderlich() -> None:
    plan = build_plan_from_case(load_case("F02"))
    ids = [node.id for node in iter_nodes(plan.nodes)]
    assert len(ids) == len(set(ids))

    node = plan.nodes[0]
    assert isinstance(node, StepNode)
    with pytest.raises(FrozenInstanceError):
        node.name = "neu"  # type: ignore[misc]
    with pytest.raises(ValueError):
        replace(plan, nodes=(plan.nodes[0], plan.nodes[0]))

    assert NodeId("123") != PlanId("123")
    assert NodeId("123") == NodeId("123")
    assert NodeId.new() != NodeId.new()


def test_workout_draft_beginnt_ohne_basis_mutation() -> None:
    plan = build_plan_from_case(load_case("F01"))
    draft = WorkoutDraft.start(plan)
    assert draft.current == plan
    assert draft.current is not plan
    assert draft.base is plan
    assert draft.base_source is None

    new_draft = WorkoutDraft.new(plan)
    assert new_draft.base is None
    assert new_draft.has_unsaved_changes is True


def test_schreibgrenze_akzeptiert_nur_geplante_entwuerfe() -> None:
    written: list[WorkoutDraft] = []

    class Writer:
        def write(self, draft: WorkoutDraft) -> str:
            written.append(draft)
            return "ok"

    coordinator = WriteCoordinator(Writer())
    draft = WorkoutDraft.start(build_plan_from_case(load_case("F01")))

    assert coordinator.submit(draft) == "ok"
    assert written == [draft]
    assert coordinator.prepare(draft) is draft

    with pytest.raises(WriteBoundaryError):
        coordinator.submit(activity_reference("123"))
    with pytest.raises(WriteBoundaryError):
        coordinator.submit(build_plan_from_case(load_case("F01")))
    with pytest.raises(WriteBoundaryError):
        coordinator.submit({"current": draft.current})
    with pytest.raises(WriteBoundaryError):
        coordinator.submit(PlannedListEntry("2026-11-08", plan_reference()))
    assert written == [draft]

    read_only = WorkoutDraft.start(
        replace(
            draft.current,
            editability=Editability.READ_ONLY,
            editability_reason="Nur lesbar.",
        )
    )
    with pytest.raises(WriteBoundaryError):
        coordinator.submit(read_only)
    assert written == [draft]


def test_f15_bewahrt_das_vorhandene_aktivitaetsmodell(tmp_path) -> None:
    con = db.connect(tmp_path / "planner.db")
    try:
        db.init_db(con)
        db.upsert_activities(
            con,
            [
                {
                    "id": "detail-strength",
                    "start_date_local": "2026-11-04T18:00:00",
                    "type": "WeightTraining",
                    "name": "Krafttraining",
                    "moving_time": 2700,
                    "elapsed_time": 3000,
                    "total_elevation_gain": None,
                    "calories": 210,
                    "average_heartrate": 112,
                    "max_heartrate": 141,
                    "icu_training_load": 18,
                    "icu_hr_zone_times": [900, 1200, 600, 0, 0],
                    "source": "FIXTURE",
                }
            ],
        )
        rows = db.training_between(con, date(2026, 11, 4), date(2026, 11, 4))
        row = db.activity_by_row_id(con, rows[0]["id"])
    finally:
        con.close()

    assert row is not None
    assert row["sport"] == "WeightTraining"
    assert row["moving_s"] == 2700
    assert row["distance_m"] is None
    payload = metrics.unit_payload(row)
    assert payload["sport_label"] == "Kraft"
    assert payload["origin"] == "intervals.icu"
    assert payload["zones"][0]["seconds"] == 900

    reference = ActivityReference(
        ActivityId(str(row["source_id"])),
        ACCOUNT,
        ATHLETE,
        source_refs=(SourceActivityRef(row["source"], str(row["source_id"])),),
    )
    assert reference.activity_id == ActivityId("detail-strength")
    assert reference.identity.object_kind is ObjectKind.ACTIVITY
    assert not isinstance(reference, PlannedWorkout)
