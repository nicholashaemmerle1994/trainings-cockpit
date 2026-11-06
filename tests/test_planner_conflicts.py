"""P21: Externe Änderungen, Löschung und Berechtigung als getrennte Konflikte."""

from __future__ import annotations

import copy
from dataclasses import replace

from planner_fixtures import build_plan_from_case, load_case, load_remote, snapshot_for_case

from trainings_cockpit.planner import (
    CONFLICT_ACTIONS,
    ConflictKind,
    EventWriteService,
    GatewayNotFound,
    SaveCoordinator,
    SaveState,
    TimeEnd,
    WorkoutDraft,
)


class ConflictGateway:
    def __init__(self, events: dict[int, dict]) -> None:
        self.events = copy.deepcopy(events)
        self.read_calls: list[str] = []
        self.update_calls: list[tuple[str, dict]] = []
        self.create_calls: list[dict] = []

    def read_event(self, remote_id: str) -> dict:
        self.read_calls.append(remote_id)
        if int(remote_id) not in self.events:
            raise GatewayNotFound(remote_id)
        return copy.deepcopy(self.events[int(remote_id)])

    def update_event(self, remote_id: str, payload: dict) -> dict:
        self.update_calls.append((remote_id, copy.deepcopy(payload)))
        event = self.events[int(remote_id)]
        event.update(copy.deepcopy(payload))
        return copy.deepcopy(event)

    def create_event(self, payload: dict) -> dict:
        self.create_calls.append(copy.deepcopy(payload))
        raise AssertionError("Ein Konflikt darf keinen Create auslösen")


def _fixture():
    case = load_case("F01")
    plan = build_plan_from_case(case)
    source = snapshot_for_case(case)
    remote = load_remote(str(case["remoteFixture"]).rsplit("/", 1)[-1])["event"]
    return plan, source, copy.deepcopy(remote)


def _activate(draft, service):
    return SaveCoordinator(service).activate(
        draft, account_id="acct", athlete_id="7"
    )


def test_f10_strukturkonflikt_bewahrt_den_lokalen_entwurf() -> None:
    f10 = load_case("F10")
    plan, source, remote = _fixture()
    gateway = ConflictGateway({9101: remote})
    service = EventWriteService(gateway)

    local_step = replace(plan.nodes[0], end=TimeEnd(1800))
    draft = WorkoutDraft.start(plan, source)
    draft.current = replace(
        plan,
        name=f10["localDraft"]["name"],
        nodes=(local_step,),
    )

    # Die externe Struktur ändert sich zwischen Öffnen und Speichern.
    gateway.events[9101]["workout_doc"]["steps"][0]["duration"] = 1500
    gateway.events[9101]["name"] = f10["remoteAfterEdit"]["name"]

    outcome = _activate(draft, service)

    assert f10["expected"]["conflictRecognized"] is True
    assert outcome.status.state is SaveState.CONFLICT
    assert outcome.status.error.value == "conflict"
    assert outcome.status.conflict is not None
    assert outcome.status.conflict.kind is ConflictKind.STRUCTURE
    assert "structure" in outcome.status.conflict.changed_fields
    assert outcome.confirmed is None
    assert gateway.update_calls == []
    assert gateway.create_calls == []
    # Der lokale Entwurf bleibt als eigener Datenstand erhalten.
    assert draft.current.name == "Geplante Einheit lokal"
    assert draft.current.nodes[0].end == TimeEnd(1800)
    # Die Remote-Fassung bleibt ebenfalls als getrennte Version lesbar.
    assert outcome.status.conflict.remote is not None
    assert outcome.status.conflict.remote.name == "Geplante Einheit extern"


def test_externe_loeschung_ist_konflikt_und_legt_nichts_neu_an() -> None:
    f10 = load_case("F10")
    plan, source, _remote = _fixture()
    gateway = ConflictGateway({})
    service = EventWriteService(gateway)
    draft = WorkoutDraft.start(plan, source)
    draft.current = replace(plan, name="Lokal weiterbearbeitet")

    outcome = _activate(draft, service)

    assert f10["expected"]["deletedRemoteIsNotRecreated"] is True
    assert outcome.status.state is SaveState.CONFLICT
    assert outcome.status.conflict is not None
    assert outcome.status.conflict.kind is ConflictKind.DELETED
    assert outcome.status.conflict.remote is None
    assert outcome.status.conflict.remote_id == "9101"
    assert gateway.update_calls == []
    assert gateway.create_calls == []
    assert draft.current.name == "Lokal weiterbearbeitet"


def test_berechtigungsaenderung_wird_getrennt_vom_inhalt_erkannt() -> None:
    plan, source, remote = _fixture()
    remote["read_only"] = True
    gateway = ConflictGateway({9101: remote})
    service = EventWriteService(gateway)
    draft = WorkoutDraft.start(plan, source)
    draft.current = replace(plan, name="Nur Metadaten")

    outcome = _activate(draft, service)

    assert outcome.status.state is SaveState.CONFLICT
    assert outcome.status.conflict is not None
    assert outcome.status.conflict.kind is ConflictKind.PERMISSION
    assert "editability" in outcome.status.conflict.changed_fields
    assert gateway.update_calls == []
    assert gateway.create_calls == []


def test_metadaten_konflikt_erzeugt_keine_generische_baumverschmelzung() -> None:
    plan, source, remote = _fixture()
    gateway = ConflictGateway({9101: remote})
    service = EventWriteService(gateway)
    draft = WorkoutDraft.start(plan, source)
    draft.current = replace(plan, name="Lokal")

    gateway.events[9101]["name"] = "Extern"
    outcome = _activate(draft, service)

    assert outcome.status.state is SaveState.CONFLICT
    assert outcome.status.conflict is not None
    assert outcome.status.conflict.kind is ConflictKind.METADATA
    assert outcome.status.conflict.changed_fields == ("name",)
    assert outcome.status.conflict.baseline is not None
    assert outcome.status.conflict.remote is not None
    assert outcome.status.conflict.baseline.name != outcome.status.conflict.remote.name
    assert gateway.update_calls == []
    assert draft.current.name == "Lokal"


def test_konflikt_aktionen_sind_die_drei_minimalen_wege() -> None:
    plan, source, _remote = _fixture()
    gateway = ConflictGateway({})
    service = EventWriteService(gateway)
    draft = WorkoutDraft.start(plan, source)
    draft.current = replace(plan, name="Lokal")

    outcome = _activate(draft, service)
    conflict = outcome.status.conflict

    assert conflict is not None
    assert conflict.actions == CONFLICT_ACTIONS
    assert conflict.as_dict()["actions"] == [
        "view_remote",
        "return_to_draft",
        "discard_local_use_remote",
    ]
    assert conflict.as_dict()["kind"] == "deleted"


def test_fehlendes_ruecklesen_nach_bestaetigtem_update_bleibt_erhalten() -> None:
    """Ein Lesefehler vor dem Write wird nicht als Konflikt erfunden."""
    plan, source, remote = _fixture()
    gateway = ConflictGateway({9101: remote})
    gateway.read_event = lambda remote_id: (_ for _ in ()).throw(TimeoutError("GET weg"))  # type: ignore[method-assign]
    service = EventWriteService(gateway)
    draft = WorkoutDraft.start(plan, source)
    draft.current = replace(plan, name="Lokal")

    outcome = _activate(draft, service)

    assert outcome.status.state is SaveState.UNKNOWN
    assert gateway.update_calls == []
    assert gateway.create_calls == []
