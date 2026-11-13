"""TB-21: Rundlauf und Konflikt lesen denselben Gruppennamen.

Die Wiederholungszahl steht in `RepeatNode.repetitions`. Eine Zahl im
Gruppennamen („Hauptteil 4x“) schreibt der Serializer nicht so, wie sie lokal
steht, sondern immer mit der tatsächlichen Anzahl. Die gemeinsame
Vergleichsprojektion muss deshalb denselben Namen lesen wie der Schreibpfad.
"""

from __future__ import annotations

from dataclasses import replace

from trainings_cockpit.planner import (
    DistanceEnd,
    Editability,
    PaceTarget,
    PaceUnit,
    PlanId,
    PlannedWorkout,
    RepeatNode,
    StepNode,
    StepRole,
    TimeEnd,
    ValueRange,
    ZoneMetric,
    ZoneTarget,
    changed_content_fields,
    plan_shape,
    repeat_group_name,
    role_from_name,
    verify_roundtrip,
)


def _plan(group_name: str, *, repetitions: int = 6) -> PlannedWorkout:
    zone = ZoneTarget(ZoneMetric.HEART_RATE, "run-hr-2", "run-hr")
    return PlannedWorkout(
        local_id=PlanId("plan:draft:intervall"),
        remote_id=None,
        external_id=None,
        name="Threshold 6x4",
        sport="Run",
        date="2026-11-11",
        local_time=None,
        time_zone="Europe/Vienna",
        nodes=(
            StepNode(
                id="node:draft:einlaufen",
                name="Einlaufen",
                end=DistanceEnd(2000),
                role=StepRole.RECOVERY,
                target=zone,
            ),
            RepeatNode(
                id="node:draft:hauptteil",
                name=group_name,
                repetitions=repetitions,
                children=(
                    StepNode(
                        id="node:draft:belastung",
                        name="Belastung",
                        end=TimeEnd(240),
                        role=StepRole.WORK,
                        target=PaceTarget(
                            PaceUnit.SECONDS_PER_KM, ValueRange(334, 345)
                        ),
                    ),
                    StepNode(
                        id="node:draft:erholung",
                        name="Erholung",
                        end=TimeEnd(120),
                        role=StepRole.RECOVERY,
                        target=zone,
                    ),
                ),
            ),
            StepNode(
                id="node:draft:auslaufen",
                name="Auslaufen",
                end=DistanceEnd(1000),
                role=StepRole.RECOVERY,
                target=zone,
            ),
        ),
        notes=None,
        editability=Editability.FULL,
    )


def _renamed_groups(plan: PlannedWorkout, *names: str) -> PlannedWorkout:
    repeats = iter(names)
    nodes = tuple(
        replace(node, name=next(repeats)) if isinstance(node, RepeatNode) else node
        for node in plan.nodes
    )
    return replace(plan, nodes=nodes)


def test_gruppenname_ohne_wiederholungszahl_ist_kein_rundlaufunterschied() -> None:
    intended = _plan("Hauptteil 4x", repetitions=6)
    # intervals schreibt den Gruppenkopf mit der tatsächlichen Anzahl zurück.
    actual = _renamed_groups(intended, "Hauptteil 6x")

    check = verify_roundtrip(intended, actual)

    assert check.valid is True, check.reason
    assert plan_shape(intended)["nodes"] == plan_shape(actual)["nodes"]


def test_echter_gruppenname_bleibt_eine_rundlaufabweichung() -> None:
    intended = _plan("Hauptteil 4x", repetitions=6)
    actual = _renamed_groups(intended, "Einlaufen")

    check = verify_roundtrip(intended, actual)

    assert check.valid is False
    assert "Aufbau" in str(check.reason)


def test_konflikt_ignoriert_nur_die_mitgeschriebene_wiederholungszahl() -> None:
    baseline = _plan("Hauptteil 6x", repetitions=6)
    remote = _plan("Hauptteil 4x", repetitions=6)

    assert changed_content_fields(baseline, remote) == ()
    assert changed_content_fields(baseline, _renamed_groups(remote, "Einlaufen")) == (
        "structure",
    )


def test_gruppenname_ohne_wiederholungszahl_leer_bleibt_leer() -> None:
    assert repeat_group_name("Hauptteil 6x") == "Hauptteil"
    assert repeat_group_name("Hauptteil 6×") == "Hauptteil"
    assert repeat_group_name("6x") == ""
    assert repeat_group_name("Hauptteil") == "Hauptteil"



def _with_cooldown(role: StepRole) -> PlannedWorkout:
    plan = _plan("Hauptteil 6x")
    return replace(
        plan,
        nodes=(
            *plan.nodes,
            StepNode(
                id="node:draft:cooldown",
                name="Cooldown",
                end=DistanceEnd(300),
                role=role,
            ),
        ),
    )


def test_rolle_aus_dem_namen_ist_kein_rundlaufunterschied() -> None:
    # D-98: Für `steady` schreibt der Serializer keinen `intensity`-Tag.
    # intervals und der Leseadapter leiten die Rolle deshalb aus dem Namen ab
    # („Cooldown“). Der Rundlauf darf daraus keine Abweichung machen.
    intended = _with_cooldown(StepRole.STEADY)
    actual = _with_cooldown(StepRole.COOLDOWN)

    check = verify_roundtrip(intended, actual)

    assert check.valid is True, check.reason
    assert plan_shape(intended)["nodes"] == plan_shape(actual)["nodes"]


def test_explizite_rolle_bleibt_eine_rundlaufabweichung() -> None:
    intended = _with_cooldown(StepRole.STEADY)
    actual = _with_cooldown(StepRole.WORK)

    check = verify_roundtrip(intended, actual)

    assert check.valid is False
    assert "Aufbau" in str(check.reason)


def test_rollenname_wird_gemeinsam_gelesen() -> None:
    assert role_from_name("Cooldown") is StepRole.COOLDOWN
    assert role_from_name("Auslaufen") is StepRole.COOLDOWN
    assert role_from_name("Belastung") is StepRole.WORK
    assert role_from_name("Erholung") is StepRole.RECOVERY
    assert role_from_name("Einschwimmen") is StepRole.STEADY
    assert role_from_name(None) is StepRole.STEADY
