"""P20: Neuanlage mit lokaler Identität, tatsächlicher Remote-ID und Reconciliation."""

from __future__ import annotations

import copy
import re
from dataclasses import replace

from planner_fixtures import build_plan_from_case, load_case

from trainings_cockpit.planner import (
    DistanceEnd,
    EventWriteService,
    GatewayNotFound,
    PaceTarget,
    PaceUnit,
    PlannedWorkout,
    PowerTarget,
    RepeatNode,
    SaveCoordinator,
    SaveState,
    StepNode,
    StepRole,
    TimeEnd,
    Value,
    ValueRange,
    WorkoutDraft,
    ZoneMetric,
    ZoneTarget,
    prepare_write,
    stable_external_id,
)


def _zone_number(zone_id: str) -> int:
    match = re.search(r"-(\d+)$", zone_id)
    assert match
    return int(match.group(1))


def _step_doc(node: StepNode) -> dict:
    doc: dict = {"text": node.name}
    if isinstance(node.end, TimeEnd):
        doc["duration"] = int(node.end.seconds)
    elif isinstance(node.end, DistanceEnd):
        doc["distance"] = int(node.end.metres)
    target = node.target
    if isinstance(target, ZoneTarget):
        doc["hr"] = {"units": "hr_zone", "value": _zone_number(target.zone_id)}
    elif isinstance(target, PaceTarget):
        values = target.values
        start, end = (values.value, values.value) if isinstance(values, Value) else (
            values.min,
            values.max,
        )
        doc["pace"] = {
            "units": "min/km" if target.unit.value == "secondsPerKm" else "min/100m",
            "start": start / 60,
            "end": end / 60,
        }
    elif isinstance(target, PowerTarget):
        values = target.values
        start, end = (values.value, values.value) if isinstance(values, Value) else (
            values.min,
            values.max,
        )
        doc["power"] = {
            "units": "w" if target.unit.value == "watts" else "%ftp",
            "start": start,
            "end": end,
        }
    if node.role.value != "steady":
        doc["intensity"] = {
            "warmup": "warmup",
            "work": "active",
            "recovery": "rest",
            "cooldown": "cooldown",
        }[node.role.value]
    return doc


def _node_doc(node) -> dict:
    if isinstance(node, StepNode):
        return _step_doc(node)
    assert isinstance(node, RepeatNode)
    return {
        "text": node.name,
        "reps": node.repetitions,
        "steps": [_node_doc(child) for child in node.children],
    }


def event_from_plan(plan: PlannedWorkout, *, event_id: int) -> dict:
    return {
        "id": event_id,
        "category": "WORKOUT",
        "start_date_local": f"{plan.date}T00:00:00",
        "type": plan.sport,
        "name": plan.name,
        "description": "",
        "external_id": plan.external_id,
        "workout_doc": {"steps": [_node_doc(node) for node in plan.nodes]},
    }


class ControlledCreateGateway:
    def __init__(self) -> None:
        self.events: dict[int, dict] = {}
        self.create_calls: list[dict] = []
        self.update_calls: list[tuple[str, dict]] = []
        self.read_calls: list[str] = []
        self.fail_create: BaseException | None = None
        self.next_id = 1201
        self.response_id: int | None | object = "auto"
        self.response_external: str | None = None
        self.store_on_timeout = False
        self.plan_by_external: dict[str, PlannedWorkout] = {}
        self.activities: dict[str, dict] = {"act-1": {"id": "act-1"}}

    def create_event(self, payload: dict) -> dict:
        self.create_calls.append(copy.deepcopy(payload))
        external_id = payload["external_id"]
        plan = self.plan_by_external.get(external_id)
        event_id = self.next_id
        self.next_id += 1
        if plan is not None:
            event = event_from_plan(replace(plan, external_id=external_id), event_id=event_id)
            event.update(
                {
                    "name": payload["name"],
                    "start_date_local": payload["start_date_local"],
                }
            )
            self.events[event_id] = event
        if self.fail_create is not None:
            if self.store_on_timeout and plan is not None:
                pass
            else:
                self.events.pop(event_id, None)
            raise self.fail_create
        if self.response_id == "auto":
            response_id: int | None = event_id
        else:
            response_id = self.response_id  # type: ignore[assignment]
        response: dict = {
            "external_id": self.response_external or external_id,
        }
        if response_id is not None:
            response["id"] = response_id
        return response

    def update_event(self, remote_id: str, payload: dict) -> dict:
        self.update_calls.append((remote_id, copy.deepcopy(payload)))
        raise AssertionError("P20 darf kein Update als Create-Ersatz auslösen")

    def read_event(self, remote_id: str) -> dict:
        self.read_calls.append(remote_id)
        return copy.deepcopy(self.events[int(remote_id)])

    def find_by_external_id(self, external_id: str, day: str) -> list[dict]:
        del day
        return [
            copy.deepcopy(event)
            for event in self.events.values()
            if event.get("external_id") == external_id
        ]


def _new_plan(name: str = "Neuer Dauerlauf", local: str = "plan:draft:neu") -> PlannedWorkout:
    plan = build_plan_from_case(load_case("F01"))
    return replace(
        plan,
        local_id=local,
        remote_id=None,
        external_id=None,
        name=name,
        date="2026-11-11",
        local_time=None,
        notes=None,
    )


def _activate(draft, service):
    return SaveCoordinator(service).activate(
        draft, account_id="acct", athlete_id="7"
    )


def test_create_nutzt_stabile_externe_id_und_uebernimmt_echte_remote_id() -> None:
    plan = _new_plan()
    gateway = ControlledCreateGateway()
    expected_external = stable_external_id(
        plan.local_id, account_id="acct", athlete_id="7"
    )
    gateway.plan_by_external[expected_external] = plan
    service = EventWriteService(gateway)
    draft = WorkoutDraft.new(plan)

    outcome = _activate(draft, service)

    assert outcome.status.state is SaveState.SAVED
    assert outcome.status.remote_id == "1201"
    assert outcome.confirmed is not None
    assert str(outcome.confirmed.remote_id) == "1201"
    assert gateway.create_calls[0]["external_id"] == expected_external
    assert gateway.update_calls == []
    assert len(gateway.create_calls) == 1


def test_retry_mit_demselben_entwurf_behaelt_die_externe_id() -> None:
    plan = _new_plan()
    gateway = ControlledCreateGateway()
    expected_external = stable_external_id(
        plan.local_id, account_id="acct", athlete_id="7"
    )
    gateway.plan_by_external[expected_external] = plan
    gateway.fail_create = GatewayNotFound("kein Create")
    service = EventWriteService(gateway)
    draft = WorkoutDraft.new(plan)

    first = _activate(draft, service)
    assert first.status.state is SaveState.FAILED
    gateway.fail_create = None
    second = _activate(draft, service)

    assert second.status.state is SaveState.SAVED
    assert len(gateway.create_calls) == 2
    assert {call["external_id"] for call in gateway.create_calls} == {expected_external}


def test_zwei_gleichnamige_einheiten_am_selben_tag_bleiben_getrennt() -> None:
    first_plan = _new_plan("Gleicher Name", "plan:draft:a")
    second_plan = _new_plan("Gleicher Name", "plan:draft:b")
    first_external = prepare_write(
        WorkoutDraft.new(first_plan), account_id="acct", athlete_id="7"
    ).external_id
    second_external = prepare_write(
        WorkoutDraft.new(second_plan), account_id="acct", athlete_id="7"
    ).external_id
    assert first_external != second_external

    gateway = ControlledCreateGateway()
    gateway.plan_by_external[str(first_external)] = first_plan
    gateway.plan_by_external[str(second_external)] = second_plan
    service = EventWriteService(gateway)
    one = _activate(WorkoutDraft.new(first_plan), service)
    two = _activate(WorkoutDraft.new(second_plan), service)

    assert one.status.state is SaveState.SAVED
    assert two.status.state is SaveState.SAVED
    assert one.status.remote_id != two.status.remote_id
    assert len(gateway.events) == 2


def test_unklarer_create_wird_abgeglichen_nicht_wiederholt() -> None:
    plan = _new_plan()
    gateway = ControlledCreateGateway()
    expected_external = stable_external_id(
        plan.local_id, account_id="acct", athlete_id="7"
    )
    gateway.plan_by_external[expected_external] = plan
    gateway.fail_create = TimeoutError("Antwort verloren")
    gateway.store_on_timeout = True
    service = EventWriteService(gateway)
    draft = WorkoutDraft.new(plan)
    coordinator = SaveCoordinator(service)

    first = coordinator.activate(draft, account_id="acct", athlete_id="7")
    second = coordinator.activate(draft, account_id="acct", athlete_id="7")

    assert first.status.state is SaveState.UNKNOWN
    assert first.status.reconciliation_required is True
    assert second.status.state is SaveState.UNKNOWN
    assert len(gateway.create_calls) == 1

    reconciled = coordinator.reconcile(first.status.operation_id or "")

    assert reconciled.status.state is SaveState.SAVED
    assert reconciled.status.remote_id == "1201"
    assert reconciled.confirmed is not None
    assert len(gateway.create_calls) == 1


def test_fehlende_remote_id_wird_nicht_erfunden() -> None:
    plan = _new_plan()
    gateway = ControlledCreateGateway()
    expected_external = stable_external_id(
        plan.local_id, account_id="acct", athlete_id="7"
    )
    gateway.plan_by_external[expected_external] = plan
    gateway.response_id = None
    service = EventWriteService(gateway)
    draft = WorkoutDraft.new(plan)
    coordinator = SaveCoordinator(service)

    outcome = coordinator.activate(draft, account_id="acct", athlete_id="7")

    assert outcome.status.state is SaveState.SAVED_UNVERIFIED
    assert outcome.status.remote_id is None
    assert outcome.confirmed is None
    assert len(gateway.create_calls) == 1

    reconciled = coordinator.reconcile(outcome.status.operation_id or "")
    assert reconciled.status.state is SaveState.SAVED
    assert reconciled.status.remote_id == "1201"
    assert reconciled.confirmed is not None
    assert len(gateway.create_calls) == 1


def test_reconciliation_ohne_treffer_bleibt_offen_und_wiederholt_nicht() -> None:
    plan = _new_plan()
    gateway = ControlledCreateGateway()
    gateway.fail_create = TimeoutError("verloren")
    service = EventWriteService(gateway)
    draft = WorkoutDraft.new(plan)
    coordinator = SaveCoordinator(service)

    first = coordinator.activate(draft, account_id="acct", athlete_id="7")
    reconciled = coordinator.reconcile(first.status.operation_id or "")

    assert first.status.state is SaveState.UNKNOWN
    assert reconciled.status.state is SaveState.UNKNOWN
    assert len(gateway.create_calls) == 1


def test_mehrdeutige_externe_id_wird_konflikt_nicht_geraten() -> None:
    plan = _new_plan()
    gateway = ControlledCreateGateway()
    expected_external = stable_external_id(
        plan.local_id, account_id="acct", athlete_id="7"
    )
    gateway.plan_by_external[expected_external] = plan
    gateway.fail_create = TimeoutError("verloren")
    gateway.store_on_timeout = True
    service = EventWriteService(gateway)
    draft = WorkoutDraft.new(plan)
    coordinator = SaveCoordinator(service)
    first = coordinator.activate(draft, account_id="acct", athlete_id="7")
    # Ein zweites Event mit derselben externen Identität simuliert eine
    # unerwartete Remote-Dopplung; sie wird nicht zusammengeführt.
    duplicate = copy.deepcopy(next(iter(gateway.events.values())))
    duplicate["id"] = 9999
    gateway.events[9999] = duplicate

    reconciled = coordinator.reconcile(first.status.operation_id or "")

    assert reconciled.status.state is SaveState.CONFLICT
    assert reconciled.confirmed is None
    assert len(gateway.create_calls) == 1


def test_fremde_externe_id_in_der_antwort_wird_nicht_zugeordnet() -> None:
    plan = _new_plan()
    gateway = ControlledCreateGateway()
    expected_external = stable_external_id(
        plan.local_id, account_id="acct", athlete_id="7"
    )
    gateway.plan_by_external[expected_external] = plan
    gateway.response_external = "fremd:event"
    service = EventWriteService(gateway)

    outcome = _activate(WorkoutDraft.new(plan), service)

    assert outcome.status.state is SaveState.SAVED_UNVERIFIED
    assert outcome.status.remote_id is None
    assert outcome.confirmed is None
    assert len(gateway.create_calls) == 1


class RealIntervalsFormGateway:
    """Antwortet auf einen Distanz-Create wie die echte intervals.icu-API.

    Der zurückgelesene Distanzschritt trägt zusätzlich die von intervals
    berechnete Dauer — ohne `duration_source` und ohne `distance_source`:
    `{"distance": 8000, "duration": 3235}`. Genau diese Form hat den Rundlauf
    fälschlich als Abweichung gemeldet.
    """

    def __init__(self, *, event_id: int = 145277995) -> None:
        self.event_id = event_id
        self.events: dict[int, dict] = {}
        self.create_calls: list[dict] = []
        self.read_calls: list[str] = []

    def create_event(self, payload: dict) -> dict:
        self.create_calls.append(copy.deepcopy(payload))
        self.events[self.event_id] = {
            "id": self.event_id,
            "category": "WORKOUT",
            "start_date_local": payload["start_date_local"],
            "type": payload["type"],
            "name": payload["name"],
            "external_id": payload["external_id"],
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
        return {"id": self.event_id, "external_id": payload["external_id"]}

    def update_event(self, remote_id: str, payload: dict) -> dict:
        raise AssertionError("Ein Create darf kein Update auslösen")

    def read_event(self, remote_id: str) -> dict:
        self.read_calls.append(remote_id)
        return copy.deepcopy(self.events[int(remote_id)])


def _distance_plan() -> PlannedWorkout:
    return replace(
        _new_plan("10 km Zone 2", "plan:draft:distanz"),
        nodes=(
            StepNode(
                id="node:draft:distanz",
                name="Obere Zone zwei",
                end=DistanceEnd(10000),
                target=ZoneTarget(ZoneMetric.HEART_RATE, "run-hr-2", "run-hr"),
            ),
        ),
    )


def test_create_distanzplan_bestaetigt_rundlauf_mit_berechneter_dauer() -> None:
    # Ein 10-km-Plan (Zone 2) wird angelegt; intervals liefert den Schritt mit
    # Distanz plus berechneter Dauer ohne Quellenangabe zurück. Der Rundlauf
    # muss die Distanz als Ende wiedererkennen und den Write bestätigen.
    gateway = RealIntervalsFormGateway()
    service = EventWriteService(gateway)

    outcome = _activate(WorkoutDraft.new(_distance_plan()), service)

    assert outcome.status.state is SaveState.SAVED
    assert outcome.status.remote_id == "145277995"
    assert outcome.confirmed is not None
    confirmed_node = outcome.confirmed.nodes[0]
    assert isinstance(confirmed_node, StepNode)
    assert confirmed_node.end == DistanceEnd(10000)
    assert len(gateway.create_calls) == 1
    assert gateway.read_calls == ["145277995"]


class RealIntervalsIntervalGateway:
    """Antwortet auf einen Intervall-Create wie die echte intervals.icu-API.

    Der Gruppenkopf kommt mit der Anzahl zurück, die im Payload stand —
    hier „Hauptteil 6x“. Lokal trug die Gruppe noch den Vorlagennamen
    „Hauptteil 4x“, weil die Wiederholungen im Editor von 4 auf 6 geändert
    wurden. Die Wiederholungszahl im Namen ist kein eigener Inhalt: Der
    Serializer schreibt immer `repetitions`.
    """

    def __init__(self, *, event_id: int = 154458829) -> None:
        self.event_id = event_id
        self.events: dict[int, dict] = {}
        self.create_calls: list[dict] = []
        self.read_calls: list[str] = []

    def create_event(self, payload: dict) -> dict:
        self.create_calls.append(copy.deepcopy(payload))
        self.events[self.event_id] = {
            "id": self.event_id,
            "category": "WORKOUT",
            "start_date_local": payload["start_date_local"],
            "type": payload["type"],
            "name": payload["name"],
            "external_id": payload["external_id"],
            "workout_doc": {
                "steps": [
                    {
                        "text": "Einlaufen",
                        "distance": 2000,
                        "hr": {"units": "hr_zone", "value": 2},
                        "intensity": "rest",
                    },
                    {
                        "text": "Hauptteil 6x",
                        "reps": 6,
                        "steps": [
                            {
                                "text": "Belastung",
                                "duration": 240,
                                "pace": {"units": "secs/km", "start": 334, "end": 345},
                                "intensity": "active",
                            },
                            {
                                "text": "Erholung",
                                "duration": 120,
                                "hr": {"units": "hr_zone", "value": 2},
                                "intensity": "rest",
                            },
                        ],
                    },
                    {
                        "text": "Auslaufen",
                        "distance": 1000,
                        "hr": {"units": "hr_zone", "value": 2},
                        "intensity": "rest",
                    },
                ]
            },
        }
        return {"id": self.event_id, "external_id": payload["external_id"]}

    def update_event(self, remote_id: str, payload: dict) -> dict:
        raise AssertionError("Ein Create darf kein Update auslösen")

    def read_event(self, remote_id: str) -> dict:
        self.read_calls.append(remote_id)
        return copy.deepcopy(self.events[int(remote_id)])


def _stale_interval_plan() -> PlannedWorkout:
    zone = ZoneTarget(ZoneMetric.HEART_RATE, "run-hr-2", "run-hr")
    return replace(
        _new_plan("Threshold 6x4", "plan:draft:intervall"),
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
                name="Hauptteil 4x",
                repetitions=6,
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
    )


def test_create_intervallplan_bestaetigt_rundlauf_trotz_veralteter_gruppenzahl() -> None:
    # TB-21: Der Lauf stand korrekt in intervals, aber der Rundlauf verglich
    # den lokalen Vorlagennamen „Hauptteil 4x“ mit dem zurückgelesenen
    # „Hauptteil 6x“. Die tatsächliche Anzahl steht in `repetitions`; der
    # Write war korrekt und darf nicht als unbestätigt gelten.
    gateway = RealIntervalsIntervalGateway()
    service = EventWriteService(gateway)

    outcome = _activate(WorkoutDraft.new(_stale_interval_plan()), service)

    assert outcome.status.state is SaveState.SAVED
    assert outcome.status.message == "In intervals.icu gespeichert und zurückgelesen."
    assert outcome.confirmed is not None
    group = next(
        node for node in outcome.confirmed.nodes if isinstance(node, RepeatNode)
    )
    assert group.name == "Hauptteil 6x"
    assert group.repetitions == 6
    assert "Hauptteil 6x" in gateway.create_calls[0]["description"]
    assert "Hauptteil 4x" not in gateway.create_calls[0]["description"]
    assert len(gateway.create_calls) == 1


def test_neue_plaene_erfinden_keine_aktivitaetsbeziehung() -> None:
    plan = _new_plan()
    gateway = ControlledCreateGateway()
    expected_external = stable_external_id(
        plan.local_id, account_id="acct", athlete_id="7"
    )
    gateway.plan_by_external[expected_external] = plan
    before_activities = copy.deepcopy(gateway.activities)
    service = EventWriteService(gateway)

    outcome = _activate(WorkoutDraft.new(plan), service)

    assert outcome.status.state is SaveState.SAVED
    assert outcome.confirmed is not None
    assert gateway.activities == before_activities
    assert gateway.update_calls == []
    assert "activity" not in gateway.create_calls[0]
    assert gateway.create_calls[0]["external_id"] == expected_external


def test_abbrechen_vor_speichern_legt_nichts_an() -> None:
    plan = _new_plan()
    gateway = ControlledCreateGateway()
    WorkoutDraft.new(plan)

    assert gateway.create_calls == []
    assert gateway.events == {}



class RealIntervalsSwimGateway:
    """Antwortet auf den Schwimm-Create mit dem echten intervals-Dokument.

    intervals.icu liefert für den Abschnitt „Cooldown“ keinen `intensity`-Tag,
    weil der Serializer für `steady` bewusst keinen schreibt. Der Leseadapter
    leitet die Rolle deshalb aus dem Namen ab. Der Rundlauf darf daraus keine
    Abweichung machen (D-98).
    """

    def __init__(self, *, event_id: int = 155269681) -> None:
        self.event_id = event_id
        self.events: dict[int, dict] = {}
        self.create_calls: list[dict] = []
        self.read_calls: list[str] = []

    def create_event(self, payload: dict) -> dict:
        self.create_calls.append(copy.deepcopy(payload))
        self.events[self.event_id] = {
            "id": self.event_id,
            "category": "WORKOUT",
            "start_date_local": payload["start_date_local"],
            "type": payload["type"],
            "name": payload["name"],
            "external_id": payload["external_id"],
            "description": "pool size: 50m\n\n" + payload["description"],
            "workout_doc": {
                "steps": [
                    {"text": "Einschwimmen", "distance": 300, "duration": 108},
                    {
                        "reps": 7,
                        "text": "Hauptteil 7x",
                        "steps": [
                            {
                                "pace": {"units": "secs/100m", "value": 120},
                                "text": "Belastung",
                                "distance": 100,
                                "duration": 120,
                                "intensity": "active",
                            },
                            {
                                "text": "Erholung",
                                "duration": 18,
                                "intensity": "rest",
                            },
                        ],
                        "distance": 700,
                        "duration": 966,
                    },
                    {
                        "pace": {"units": "secs/100m", "value": 130},
                        "text": "Ausdauer",
                        "distance": 1200,
                        "duration": 1560,
                    },
                    {"text": "Cooldown", "distance": 300, "duration": 108},
                ],
                "locales": [],
                "options": {},
                "distance": 2500,
                "duration": 2742,
                "description": "pool size: 50m",
                "strain_score": None,
                "average_watts": 0,
                "normalized_power": 0,
                "variability_index": None,
                "polarization_index": None,
            },
        }
        return {"id": self.event_id, "external_id": payload["external_id"]}

    def update_event(self, remote_id: str, payload: dict) -> dict:
        raise AssertionError("Ein Create darf kein Update auslösen")

    def read_event(self, remote_id: str) -> dict:
        self.read_calls.append(remote_id)
        return copy.deepcopy(self.events[int(remote_id)])


def _swim_plan() -> PlannedWorkout:
    return replace(
        _new_plan("Endurance + Sweetspot", "plan:draft:schwimmen"),
        sport="Swim",
        date="2026-11-13",
        nodes=(
            StepNode(
                id="node:draft:einschwimmen",
                name="Einschwimmen",
                end=DistanceEnd(300),
            ),
            RepeatNode(
                id="node:draft:hauptteil",
                name="Hauptteil",
                repetitions=7,
                children=(
                    StepNode(
                        id="node:draft:belastung",
                        name="Belastung",
                        end=DistanceEnd(100),
                        role=StepRole.WORK,
                        target=PaceTarget(
                            PaceUnit.SECONDS_PER_100M, Value(120)
                        ),
                    ),
                    StepNode(
                        id="node:draft:erholung",
                        name="Erholung",
                        end=TimeEnd(18),
                        role=StepRole.RECOVERY,
                    ),
                ),
            ),
            StepNode(
                id="node:draft:ausdauer",
                name="Ausdauer",
                end=DistanceEnd(1200),
                target=PaceTarget(PaceUnit.SECONDS_PER_100M, Value(130)),
            ),
            StepNode(
                id="node:draft:cooldown",
                name="Cooldown",
                end=DistanceEnd(300),
            ),
        ),
    )


def test_create_schwimmplan_mit_gleichmaessigem_cooldown_bestaetigt_rundlauf() -> None:
    # Der gemeldete Fall: Der Abschnitt heißt „Cooldown“, ist aber bewusst
    # `steady`; der Serializer schreibt deshalb keinen `intensity`-Tag.
    # intervals liest die Rolle aus dem Namen zurück. Der Write ist korrekt und
    # darf nicht als `savedUnverified` enden.
    gateway = RealIntervalsSwimGateway()
    service = EventWriteService(gateway)

    outcome = _activate(WorkoutDraft.new(_swim_plan()), service)

    assert outcome.status.state is SaveState.SAVED
    assert outcome.status.message == "In intervals.icu gespeichert und zurückgelesen."
    assert outcome.confirmed is not None
    cooldown = outcome.confirmed.nodes[-1]
    assert isinstance(cooldown, StepNode)
    assert cooldown.name == "Cooldown"
    assert cooldown.role is StepRole.COOLDOWN
    assert "intensity=cooldown" not in gateway.create_calls[0]["description"]
    assert len(gateway.create_calls) == 1
