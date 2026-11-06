"""P19: Update bestehender Einheiten, Event-ID und fachlicher Rundlauf."""

from __future__ import annotations

import copy
import re
from dataclasses import replace

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
    Editability,
    EventWriteService,
    GatewayConflict,
    GatewayNotFound,
    PaceTarget,
    PowerTarget,
    RepeatNode,
    SaveCoordinator,
    SaveState,
    StepNode,
    TimeEnd,
    Value,
    WorkoutDraft,
    ZoneTarget,
    plan_shape,
    serialize_workout_text,
)


def _zone_number(zone_id: str) -> int:
    match = re.search(r"-(\d+)$", zone_id)
    assert match, zone_id
    return int(match.group(1))


def _step_doc(step: StepNode) -> dict:
    doc: dict = {"text": step.name}
    if isinstance(step.end, TimeEnd):
        doc["duration"] = int(step.end.seconds)
    elif isinstance(step.end, DistanceEnd):
        doc["distance"] = int(step.end.metres)
    else:
        raise AssertionError("offenes Ende ist nicht testbar")
    target = step.target
    if isinstance(target, ZoneTarget):
        doc["hr"] = {"units": "hr_zone", "value": _zone_number(target.zone_id)}
    elif isinstance(target, PaceTarget):
        values = target.values
        if isinstance(values, Value):
            start = end = values.value / 60
        else:
            start, end = values.min / 60, values.max / 60
        doc["pace"] = {
            "units": "min/km" if target.unit.value == "secondsPerKm" else "min/100m",
            "start": start,
            "end": end,
        }
    elif isinstance(target, PowerTarget):
        values = target.values
        if isinstance(values, Value):
            start = end = values.value
        else:
            start, end = values.min, values.max
        doc["power"] = {
            "units": "w" if target.unit.value == "watts" else "%ftp",
            "start": start,
            "end": end,
        }
    if step.role.value != "steady":
        doc["intensity"] = {
            "warmup": "warmup",
            "work": "active",
            "recovery": "rest",
            "cooldown": "cooldown",
        }[step.role.value]
    return doc


def _node_doc(node) -> dict:
    if isinstance(node, StepNode):
        return _step_doc(node)
    assert isinstance(node, RepeatNode)
    return {
        "text": node.name,
        "reps": node.repetitions,
        "steps": [_node_doc(child) for child in node.children],
        **({"skip_final_recovery": True} if node.skip_final_recovery else {}),
    }


def event_from_plan(plan, *, event_id: int, external_id: str | None = None) -> dict:
    start = (
        f"{plan.date}T{plan.local_time}:00"
        if plan.local_time
        else f"{plan.date}T00:00:00"
    )
    return {
        "id": event_id,
        "category": "WORKOUT",
        "start_date_local": start,
        "type": plan.sport,
        "name": plan.name,
        "description": serialize_workout_text(plan),
        "external_id": external_id or plan.external_id,
        "workout_doc": {"steps": [_node_doc(node) for node in plan.nodes]},
    }


class ControlledGateway:
    def __init__(self, events: dict[int, dict]) -> None:
        self.events = copy.deepcopy(events)
        self.update_calls: list[tuple[str, dict]] = []
        self.create_calls: list[dict] = []
        self.read_calls: list[str] = []
        self.fail_update: BaseException | None = None
        self.fail_read: BaseException | None = None
        self.fail_read_after_update = 0
        self.update_doc: dict | None = None
        self.response_id: int | None = None
        self.activities: dict[str, dict] = {"act-1": {"id": "act-1", "name": "Lauf"}}

    def read_event(self, remote_id: str) -> dict:
        self.read_calls.append(remote_id)
        if self.fail_read is not None:
            raise self.fail_read
        if self.fail_read_after_update > 0:
            self.fail_read_after_update -= 1
            raise TimeoutError("Rücklesen zu spät")
        return copy.deepcopy(self.events[int(remote_id)])

    def update_event(self, remote_id: str, payload: dict) -> dict:
        self.update_calls.append((remote_id, copy.deepcopy(payload)))
        if self.fail_update is not None:
            raise self.fail_update
        if int(remote_id) not in self.events:
            raise GatewayNotFound(remote_id)
        event = self.events[int(remote_id)]
        event.update(copy.deepcopy(payload))
        event["id"] = (
            self.response_id if self.response_id is not None else int(remote_id)
        )
        if self.update_doc is not None:
            event["workout_doc"] = copy.deepcopy(self.update_doc)
        return copy.deepcopy(event)

    def create_event(self, payload: dict) -> dict:
        self.create_calls.append(copy.deepcopy(payload))
        raise AssertionError("P19 darf keinen Create auslösen")


def _fixture(case_id: str):
    case = load_case(case_id)
    plan = build_plan_from_case(case)
    source = snapshot_for_case(case)
    remote = load_remote(str(case["remoteFixture"]).rsplit("/", 1)[-1])["event"]
    return plan, source, remote


def _activate(draft, service, *, writable: bool = True):
    return SaveCoordinator(service).activate(
        draft, account_id="acct", athlete_id="7", writable=writable
    )


def test_namensaenderung_behaelt_event_id_und_aufbau() -> None:
    plan, source, remote = _fixture("F01")
    gateway = ControlledGateway({int(remote["id"]): remote})
    service = EventWriteService(gateway)
    draft = WorkoutDraft.start(plan, source)
    draft.current = replace(plan, name="Ruhiger Abendlauf")

    outcome = _activate(draft, service)

    assert outcome.status.state is SaveState.SAVED
    assert outcome.confirmed is not None
    assert len(gateway.update_calls) == 1
    remote_id, payload = gateway.update_calls[0]
    assert remote_id == "9101"
    assert payload == {"name": "Ruhiger Abendlauf"}
    assert outcome.confirmed.name == "Ruhiger Abendlauf"
    assert plan_shape(outcome.confirmed)["nodes"] == plan_shape(plan)["nodes"]


def test_datumsaenderung_behaelt_uhrzeit_und_event_id() -> None:
    plan, source, remote = _fixture("F01")
    remote = copy.deepcopy(remote)
    remote["start_date_local"] = "2026-11-03T09:15:00"
    plan = replace(plan, local_time="09:15")
    gateway = ControlledGateway({9101: remote})
    service = EventWriteService(gateway)
    draft = WorkoutDraft.start(plan, source)
    draft.current = replace(plan, date="2026-11-12")

    outcome = _activate(draft, service)

    assert outcome.status.state is SaveState.SAVED
    _, payload = gateway.update_calls[0]
    assert payload == {"start_date_local": "2026-11-12T09:15:00"}
    assert outcome.confirmed.date == "2026-11-12"
    assert outcome.confirmed.local_time == "09:15"
    assert plan_shape(outcome.confirmed)["nodes"] == plan_shape(plan)["nodes"]


def test_strukturaenderung_gemischter_ziele_rundlauf() -> None:
    plan, source, remote = _fixture("F02")
    repeat = next(node for node in plan.nodes if isinstance(node, RepeatNode))
    work = repeat.children[0]
    changed = replace(plan, nodes=(
        plan.nodes[0],
        replace(repeat, children=(replace(work, end=TimeEnd(180)), *repeat.children[1:])),
        plan.nodes[2],
    ))
    gateway = ControlledGateway({9102: remote})
    gateway.update_doc = event_from_plan(changed, event_id=9102)["workout_doc"]
    service = EventWriteService(gateway)
    draft = WorkoutDraft.start(plan, source)
    draft.current = changed

    outcome = _activate(draft, service)

    assert outcome.status.state is SaveState.SAVED
    _, payload = gateway.update_calls[0]
    assert set(payload) == {"description"}
    assert "Belastung 3m 5:30-5:45/km Pace" in payload["description"]
    assert outcome.confirmed is not None
    assert plan_shape(outcome.confirmed)["nodes"] == plan_shape(changed)["nodes"]
    assert len(outcome.confirmed.nodes[1].children) == 2


def test_404_wird_nicht_zu_einer_neuanlage() -> None:
    plan, source, remote = _fixture("F01")
    gateway = ControlledGateway({9101: remote})
    gateway.fail_update = GatewayNotFound("9101")
    service = EventWriteService(gateway)
    draft = WorkoutDraft.start(plan, source)
    draft.current = replace(plan, name="Verschwunden")

    outcome = _activate(draft, service)

    assert outcome.status.state is SaveState.FAILED
    assert outcome.status.error.value == "not_found"
    assert draft.current.name == "Verschwunden"
    assert gateway.create_calls == []
    assert gateway.update_calls


def test_fehlende_berechtigung_schreibt_nichts() -> None:
    plan, source, remote = _fixture("F01")
    gateway = ControlledGateway({9101: remote})
    service = EventWriteService(gateway)
    draft = WorkoutDraft.start(plan, source)
    draft.current = replace(plan, name="Ohne Recht")

    outcome = _activate(draft, service, writable=False)

    assert outcome.status.state is SaveState.FAILED
    assert outcome.status.error.value == "permission"
    assert gateway.update_calls == []
    assert gateway.create_calls == []


def test_fehlendes_ruecklesen_ist_nicht_gleich_fehler() -> None:
    plan, source, remote = _fixture("F01")
    gateway = ControlledGateway({9101: remote})
    gateway.fail_read_after_update = 1
    service = EventWriteService(gateway)
    draft = WorkoutDraft.start(plan, source)
    draft.current = replace(plan, name="Write angekommen")

    outcome = _activate(draft, service)

    assert outcome.status.state is SaveState.SAVED_UNVERIFIED
    assert outcome.status.remote_id == "9101"
    assert outcome.confirmed is None
    assert len(gateway.update_calls) == 1
    assert gateway.create_calls == []


def test_abweichender_rundlauf_wird_nicht_bestaetigt() -> None:
    plan, source, remote = _fixture("F02")
    repeat = next(node for node in plan.nodes if isinstance(node, RepeatNode))
    work = repeat.children[0]
    changed = replace(plan, nodes=(
        plan.nodes[0],
        replace(repeat, children=(replace(work, end=TimeEnd(180)), *repeat.children[1:])),
        plan.nodes[2],
    ))
    gateway = ControlledGateway({9102: remote})
    service = EventWriteService(gateway)
    draft = WorkoutDraft.start(plan, source)
    draft.current = changed

    outcome = _activate(draft, service)

    assert outcome.status.state is SaveState.SAVED_UNVERIFIED
    assert outcome.confirmed is None
    assert "Rundlauf" in outcome.status.message
    assert len(gateway.update_calls) == 1


def test_aktionsreferenz_erreicht_den_update_dienst_nicht() -> None:
    plan, source, remote = _fixture("F01")
    gateway = ControlledGateway({9101: remote})
    service = EventWriteService(gateway)
    activity = ActivityReference(ActivityId("9101"), "acct", "7")

    outcome = _activate(activity, service)

    assert outcome.status.state is SaveState.INVALID
    assert gateway.update_calls == []
    assert gateway.create_calls == []


def test_plan_aus_aktivitaetsdetail_aendert_nur_den_plan() -> None:
    plan, source, remote = _fixture("F01")
    gateway = ControlledGateway({9101: remote})
    before_activity = copy.deepcopy(gateway.activities)
    service = EventWriteService(gateway)
    draft = WorkoutDraft.start(plan, source)
    draft.current = replace(plan, name="Nur der Plan")

    outcome = _activate(draft, service)

    assert outcome.status.state is SaveState.SAVED
    assert gateway.activities == before_activity
    assert [call[0] for call in gateway.update_calls] == ["9101"]


def test_konflik_vorabpruefung_verhindert_den_write() -> None:
    plan, source, remote = _fixture("F01")
    gateway = ControlledGateway({9101: remote})

    def conflict(snapshot):
        raise GatewayConflict("Remote wurde geändert")

    service = EventWriteService(gateway, preflight=conflict)
    draft = WorkoutDraft.start(plan, source)
    draft.current = replace(plan, name="Nicht überschreiben")

    outcome = _activate(draft, service)

    assert outcome.status.state is SaveState.CONFLICT
    assert outcome.status.error.value == "conflict"
    assert gateway.update_calls == []
    assert gateway.create_calls == []


def test_antwort_mit_fremder_event_id_wird_nicht_uebernommen() -> None:
    plan, source, remote = _fixture("F01")
    gateway = ControlledGateway({9101: remote})
    gateway.response_id = 9999
    service = EventWriteService(gateway)
    draft = WorkoutDraft.start(plan, source)
    draft.current = replace(plan, name="Falsche Antwort")

    outcome = _activate(draft, service)

    assert outcome.status.state is SaveState.FAILED
    assert outcome.status.error.value == "identity"
    assert outcome.status.remote_id == "9101"
    assert outcome.confirmed is None
    assert gateway.create_calls == []


def test_nicht_editierbarer_plan_wird_vor_dem_write_abgewiesen() -> None:
    plan, source, remote = _fixture("F01")
    gateway = ControlledGateway({9101: remote})
    service = EventWriteService(gateway)
    read_only = replace(
        plan,
        editability=Editability.READ_ONLY,
        editability_reason="Remote gesperrt",
    )
    draft = WorkoutDraft.start(read_only, source)

    outcome = _activate(draft, service)

    assert outcome.status.state is SaveState.INVALID
    assert gateway.update_calls == []
