"""P17: Serializer, Payload-Grenze und Erhaltungsregeln.

Die Tests bauen ausschließlich auf den F01–F07-Fixtures und konstruierten
Randfällen auf. Es gibt keinen Netzwerkaufruf und keinen Produktschreibpfad.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from planner_fixtures import (
    build_plan_from_case,
    load_case,
    load_remote,
    snapshot_for_case,
)

from trainings_cockpit.planner import (
    ActivityId,
    ActivityReference,
    DistanceEnd,
    FieldBuffer,
    FieldValidity,
    HeartRateTarget,
    NoTarget,
    NoWriteNeeded,
    PlannedListEntry,
    PlannedWorkout,
    PlanReference,
    PowerTarget,
    PowerUnit,
    RepeatNode,
    SerializationBoundaryError,
    SerializationError,
    StepNode,
    StepRole,
    TimeEnd,
    Value,
    WorkoutDraft,
    ZoneTarget,
    prepare_write,
    read_remote_event,
    serialize_workout_text,
)


def _fixture(case_id: str):
    case = load_case(case_id)
    plan = build_plan_from_case(case)
    source = snapshot_for_case(case) if case.get("remoteFixture") else None
    return case, plan, source


def _draft(case_id: str) -> tuple[WorkoutDraft, PlannedWorkout, dict]:
    case, plan, source = _fixture(case_id)
    if source is None:
        return WorkoutDraft.new(plan), plan, case
    return WorkoutDraft.start(plan, source), plan, case


def _step(plan: PlannedWorkout, name: str) -> StepNode:
    for node in plan.nodes:
        if isinstance(node, StepNode) and node.name == name:
            return node
        if isinstance(node, RepeatNode):
            for child in node.children:
                if isinstance(child, StepNode) and child.name == name:
                    return child
    raise AssertionError(f"Schritt {name!r} fehlt")


def test_f01_workouttext_bleibt_bei_name_und_datum_unveraendert() -> None:
    case, plan, _ = _fixture("F01")
    remote = load_remote(str(case["remoteFixture"]).rsplit("/", 1)[-1])["event"]
    draft, base, _ = _draft("F01")
    assert serialize_workout_text(plan) == remote["description"]
    draft.current = replace(base, name="Ruhiger Lauf am Abend")

    prepared = prepare_write(draft)

    assert prepared.kind == "update"
    assert prepared.mode == "metadata"
    assert prepared.payload == {"name": "Ruhiger Lauf am Abend"}
    assert "description" not in prepared.payload
    assert prepared.workout_text is None
    assert prepared.remote_id == str(base.remote_id)


def test_f01_strukturtext_enthaelt_zone_dauer_und_keine_internen_ids() -> None:
    _, plan, _ = _fixture("F01")
    text = serialize_workout_text(plan)
    assert text == "- Dauerlauf 45m Z2 HR"
    assert "node:" not in text
    assert "fixture:" not in text


def test_f02_wiederholung_rollen_und_gemischte_ziele() -> None:
    _, plan, _ = _fixture("F02")
    text = serialize_workout_text(plan)

    assert "Hauptteil 4x" in text
    assert "- Einlaufen 10m Z2 HR intensity=warmup" in text
    assert "- Belastung 2m 5:30-5:45/km Pace intensity=active" in text
    assert "- Erholung 2m Z1 HR intensity=rest" in text
    assert "- Auslaufen 10m Z1 HR intensity=cooldown" in text
    assert text.startswith("- Einlaufen")
    assert "\n\nHauptteil 4x\n" in text


def test_f02_strukturänderung_erzeugt_nur_den_workouttext() -> None:
    draft, base, _ = _draft("F02")
    main = next(node for node in base.nodes if isinstance(node, RepeatNode))
    work = main.children[0]
    changed_main = replace(main, children=(replace(work, end=TimeEnd(180)), *main.children[1:]))
    draft.current = replace(
        base,
        nodes=(base.nodes[0], changed_main, base.nodes[2]),
    )

    prepared = prepare_write(draft)

    assert prepared.kind == "update"
    assert prepared.mode == "structure"
    assert set(prepared.payload) == {"description"}
    assert "- Belastung 3m 5:30-5:45/km Pace" in prepared.payload["description"]
    assert "name" not in prepared.payload
    assert "start_date_local" not in prepared.payload


def test_f03_watt_bereich_und_prozent_bleiben_unterscheidbar() -> None:
    _, plan, _ = _fixture("F03")
    text = serialize_workout_text(plan)
    assert "- Arbeit 10m 160-170w intensity=active" in text
    assert "- Erholung 5m 90-110w intensity=rest" in text

    work = _step(plan, "Arbeit")
    relative = replace(
        plan,
        nodes=tuple(
            replace(node, children=tuple(
                replace(child, target=PowerTarget(PowerUnit.PERCENT_FTP, Value(90)))
                if child is work else child
                for child in node.children
            )) if node is plan.nodes[1] else node
            for node in plan.nodes
        ),
    )
    assert "90%" in serialize_workout_text(relative)
    assert "90w" not in serialize_workout_text(relative)


def test_f03_null_watt_bleibt_ein_gueltiger_einzelwert() -> None:
    _, plan, _ = _fixture("F03")
    work = _step(plan, "Arbeit")
    zero = replace(plan, nodes=tuple(
        replace(node, children=tuple(
            replace(child, target=PowerTarget(PowerUnit.WATTS, Value(0)))
            if child is work else child
            for child in node.children
        )) if node is plan.nodes[1] else node
        for node in plan.nodes
    ))
    assert "0w" in serialize_workout_text(zero)


def test_f04_distanz_wird_mtr_und_pace_traegt_ihre_referenz() -> None:
    _, plan, _ = _fixture("F04")
    text = serialize_workout_text(plan)
    assert "1000mtr" in text
    assert "5:30/km Pace" in text
    assert "1000m " not in text
    assert "1000m\n" not in text

    case = load_case("F06")["plans"][0]["plan"]
    four_hundred = build_plan_from_case({"plan": {
        **case,
        "nodes": [{
            "kind": "step",
            "id": "node:test:400",
            "name": "Belastung",
            "role": "work",
            "end": {"kind": "distance", "metres": 400},
            "target": {"kind": "none"},
        }],
    }})
    assert serialize_workout_text(four_hundred) == "- Belastung 400mtr intensity=active"


def test_f05_schwimmpace_bleibt_pro_100_meter() -> None:
    _, plan, _ = _fixture("F05")
    # Der Fixture-Name „100 m“ wäre als Prompt eine Dauer und wird deshalb
    # vor der Payload-Erzeugung abgelehnt statt falsch geschrieben.
    with pytest.raises(SerializationError, match="Zeit-, Distanz- oder Paceangabe"):
        serialize_workout_text(plan)

    safe = replace(
        plan,
        nodes=(
            replace(
                plan.nodes[0],
                children=(
                    replace(plan.nodes[0].children[0], name="Belastung"),
                    plan.nodes[0].children[1],
                ),
            ),
        ),
    )
    text = serialize_workout_text(safe)
    assert "- Belastung 100mtr 2:00/100m Pace intensity=active" in text
    assert "2:00/km" not in text


@pytest.mark.parametrize("case_id", ["F01", "F02", "F03", "F04", "F06"])
def test_f06_leere_und_nicht_ausfuehrbare_plaene_werden_abgelehnt(case_id: str) -> None:
    if case_id == "F06":
        case = load_case("F06")
        for entry in case["plans"]:
            plan = build_plan_from_case({"plan": entry["plan"]})
            draft = WorkoutDraft.new(plan)
            with pytest.raises(SerializationError):
                prepare_write(draft)
        return
    _, plan, _ = _fixture(case_id)
    assert serialize_workout_text(plan)


def test_f07_metadaten_aenderung_laesst_den_rohtext_unangetastet() -> None:
    case, plan, _ = _fixture("F07")
    draft, base, _ = _draft("F07")
    assert base.editability.value == "metadataOnly"
    draft.current = replace(
        base,
        name="Verschobener Import",
        date="2026-11-09",
    )

    prepared = prepare_write(draft)

    assert prepared.mode == "metadata"
    assert prepared.payload == {
        "name": "Verschobener Import",
        "start_date_local": "2026-11-09T09:15:00",
    }
    assert prepared.payload.get("description") is None
    assert case["remoteFixture"]
    source = draft.base_source
    assert source is not None
    remote = load_remote(str(case["remoteFixture"]).rsplit("/", 1)[-1])["event"]
    assert source.raw_workout_text == remote["description"]


def test_f07_strukturierung_unbekannter_inhalte_wird_abgelehnt() -> None:
    draft, base, _ = _draft("F07")
    draft.current = replace(base, nodes=base.nodes[:1])

    with pytest.raises(SerializationError):
        prepare_write(draft)


def test_f07_notizen_bleiben_bei_metadaten_erhalten_und_blockieren_struktur() -> None:
    draft, base, _ = _draft("F07")
    assert base.notes
    draft.current = replace(base, name="Neuer Name")
    prepared = prepare_write(draft)
    assert "description" not in prepared.payload
    assert base.notes in (draft.base_source.raw["workout_doc"]["notes"])

    draft.current = replace(base, nodes=base.nodes[:1])
    with pytest.raises(SerializationError):
        prepare_write(draft)


def test_ohne_aenderung_gibt_es_keinen_schreibauftrag() -> None:
    draft, _, _ = _draft("F01")
    with pytest.raises(NoWriteNeeded):
        prepare_write(draft)


def test_ungueltiger_feldpuffer_wird_vor_der_payload_erzeugung_abgelehnt() -> None:
    draft, plan, _ = _draft("F01")
    step = _step(plan, "Dauerlauf")
    draft.set_field_buffer(
        step.id,
        "end.value",
        FieldBuffer(
            raw="5:",
            parsed=None,
            validity=FieldValidity.INVALID,
            message="Die Dauer ist unvollständig.",
        ),
    )
    with pytest.raises(SerializationError, match="nicht speicherbar"):
        prepare_write(draft)


def test_absolute_bpm_und_nicht_belegte_zonen_werden_abgelehnt() -> None:
    _, plan, _ = _fixture("F01")
    bpm = replace(plan, nodes=(replace(plan.nodes[0], target=HeartRateTarget(Value(150))),))
    with pytest.raises(SerializationError, match="bpm"):
        serialize_workout_text(bpm)

    custom = replace(
        plan,
        nodes=(replace(
            plan.nodes[0],
            target=ZoneTarget(
                metric=plan.nodes[0].target.metric,
                zone_id="run-custom-sweetspot",
                zone_set_id="run-custom",
            ),
        ),),
    )
    with pytest.raises(SerializationError, match="Standardzone"):
        serialize_workout_text(custom)


def test_skip_final_recovery_und_verschachtelte_wiederholung_werden_abgelehnt() -> None:
    _, plan, _ = _fixture("F02")
    main = next(node for node in plan.nodes if isinstance(node, RepeatNode))
    skipped = replace(plan, nodes=(
        plan.nodes[0],
        replace(main, skip_final_recovery=True),
        plan.nodes[2],
    ))
    with pytest.raises(SerializationError, match="auslassen"):
        serialize_workout_text(skipped)

    nested = replace(plan, nodes=(
        replace(plan.nodes[0], id="node:test:nested"),
        replace(main, name="Aussen", children=(
            StepNode(
                id="node:test:work",
                name="Arbeit",
                end=TimeEnd(60),
                role=StepRole.WORK,
                target=NoTarget(),
            ),
            replace(main, name="Innen", id="node:test:inner"),
        )),
    ))
    with pytest.raises(SerializationError, match="Verschachtelte"):
        serialize_workout_text(nested)


def test_schrittnotizen_und_reservierte_namen_werden_abgelehnt() -> None:
    _, plan, _ = _fixture("F01")
    noted = replace(plan, nodes=(replace(plan.nodes[0], notes="Nur locker atmen"),))
    with pytest.raises(SerializationError, match="Schrittnotizen"):
        serialize_workout_text(noted)

    newline = replace(plan, nodes=(replace(plan.nodes[0], name="Lauf\n- 5m 90%"),))
    with pytest.raises(SerializationError, match="Zeilenumbrüche"):
        serialize_workout_text(newline)

    reserved = replace(plan, nodes=(replace(plan.nodes[0], name="Lauf intensity=warmup"),))
    with pytest.raises(SerializationError, match="reserviertes"):
        serialize_workout_text(reserved)

    duration_name = replace(plan, nodes=(replace(plan.nodes[0], name="Lauf 45m"),))
    with pytest.raises(SerializationError, match="Zeit-, Distanz- oder Paceangabe"):
        serialize_workout_text(duration_name)


def test_zeit_distanz_und_pace_verlieren_keine_praezision() -> None:
    _, plan, _ = _fixture("F01")
    fractional = replace(
        plan,
        nodes=(replace(plan.nodes[0], end=TimeEnd(90.5)),),
    )
    with pytest.raises(SerializationError, match="Präzisionsverlust"):
        serialize_workout_text(fractional)

    fractional_distance = replace(
        plan,
        nodes=(replace(plan.nodes[0], end=DistanceEnd(400.5)),),
    )
    with pytest.raises(SerializationError, match="ganzen Metern"):
        serialize_workout_text(fractional_distance)


def test_aktivitaet_und_listenprojektion_werden_an_der_grenze_abgelehnt() -> None:
    activity = ActivityReference(ActivityId("9101"), "default", "default")
    planned = PlannedListEntry(
        "2026-11-02",
        PlanReference("plan:f01", "default", "default"),
    )
    with pytest.raises(SerializationBoundaryError):
        prepare_write(activity)
    with pytest.raises(SerializationBoundaryError):
        prepare_write(planned)
    with pytest.raises(SerializationBoundaryError):
        prepare_write({"activity_id": "9101"})
    with pytest.raises(SerializationBoundaryError):
        serialize_workout_text(activity)


def test_gleiche_numerische_id_erlaubt_keinen_typwechsel() -> None:
    draft, plan, _ = _draft("F01")
    assert str(plan.remote_id) == "9101"
    draft.current = replace(plan, name="Weiterhin ein Plan")
    prepared = prepare_write(draft)
    assert prepared.remote_id == "9101"

    with pytest.raises(SerializationBoundaryError):
        prepare_write(ActivityReference(ActivityId("9101"), "default", "default"))


def test_payload_enthaelt_keine_node_ids_demo_ids_oder_berechneten_remote_felder() -> None:
    draft, plan, _ = _draft("F02")
    main = next(node for node in plan.nodes if isinstance(node, RepeatNode))
    draft.current = replace(
        plan,
        nodes=(plan.nodes[0], replace(main, repetitions=5), plan.nodes[2]),
    )
    prepared = prepare_write(draft)
    serialized = json.dumps(prepared.payload, ensure_ascii=False)

    assert "node:" not in serialized
    assert "fixture:" not in serialized
    assert "workout_doc" not in prepared.payload
    assert "moving_time" not in prepared.payload
    assert "distance" not in prepared.payload
    assert "icu_training_load" not in prepared.payload
    assert "icu_intensity" not in prepared.payload
    assert set(prepared.payload) <= {"name", "start_date_local", "description"}


def test_neuanlage_hat_getrennte_lokale_identitaet_ohne_remote_id() -> None:
    _, plan, _ = _fixture("F01")
    draft = WorkoutDraft.new(replace(
        plan,
        local_id="plan:draft:neu",
        remote_id=None,
        external_id=None,
        name="Neuer Dauerlauf",
        date="2026-11-11",
        local_time=None,
        notes=None,
    ))

    prepared = prepare_write(draft)

    assert prepared.kind == "create"
    assert prepared.mode == "create"
    assert prepared.remote_id is None
    assert prepared.local_id == "plan:draft:neu"
    assert prepared.payload == {
        "category": "WORKOUT",
        "type": "Run",
        "name": "Neuer Dauerlauf",
        "start_date_local": "2026-11-11T00:00:00",
        "description": "- Dauerlauf 45m Z2 HR",
    }
    assert "external_id" not in prepared.payload


def test_remote_id_darf_bei_update_nicht_wechseln() -> None:
    draft, plan, _ = _draft("F01")
    draft.current = replace(plan, remote_id="9999", name="Andere ID")
    with pytest.raises(SerializationError, match="Remote-ID"):
        prepare_write(draft)


def test_rollen_werden_aus_dem_belegten_intensity_feld_gelesen() -> None:
    event = {
        "id": 9901,
        "category": "WORKOUT",
        "start_date_local": "2026-11-02T00:00:00",
        "type": "Run",
        "name": "Rollen",
        "description": "",
        "workout_doc": {
            "steps": [
                {"text": "A", "duration": 60, "intensity": "warmup"},
                {"text": "B", "duration": 60, "intensity": "active"},
                {"text": "C", "duration": 60, "intensity": "rest"},
                {"text": "D", "duration": 60, "intensity": "cooldown"},
            ],
        },
    }
    parsed = read_remote_event(
        event,
        fetched_at="2026-11-02T10:00:00+01:00",
        time_zone="Europe/Vienna",
    )
    assert [node.role for node in parsed.plan.nodes] == [
        StepRole.WARMUP,
        StepRole.WORK,
        StepRole.RECOVERY,
        StepRole.COOLDOWN,
    ]


def test_serializer_ist_ohne_schreibweg_und_mit_allen_kontrollfeldern_dokumentiert() -> None:
    from trainings_cockpit.planner.serializer import (
        CONTROLLED_REMOTE_FIELDS,
        PRESERVED_REMOTE_FIELDS,
    )

    assert CONTROLLED_REMOTE_FIELDS == ("name", "start_date_local", "description")
    assert {"workout_doc", "moving_time", "distance", "icu_training_load"} <= set(
        PRESERVED_REMOTE_FIELDS
    )
    _, plan, _ = _fixture("F01")
    draft = WorkoutDraft.new(
        replace(plan, local_id="plan:draft:doc", remote_id=None, notes=None)
    )
    prepared = prepare_write(draft)
    assert prepared.controlled_fields == (
        "name",
        "start_date_local",
        "description",
        "type",
        "category",
    )
    assert prepared.as_dict()["payload"]["type"] == "Run"
