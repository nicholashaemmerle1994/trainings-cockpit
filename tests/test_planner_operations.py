"""P22: offene Vorgänge, Reload, unklare Antworten und Aufbewahrung."""

from __future__ import annotations

import copy
import json
from dataclasses import replace

from planner_fixtures import build_plan_from_case, load_case

from trainings_cockpit import db
from trainings_cockpit.planner import (
    EventWriteService,
    SaveCoordinator,
    SaveErrorKind,
    SaveSnapshot,
    SaveState,
    WorkoutDraft,
    WriteResult,
    plan_from_json,
    plan_to_json,
    snapshot_from_json,
    snapshot_to_json,
)
from trainings_cockpit.planner.operations import (
    RETENTION_DAYS,
    SqliteOperationStore,
    retention_cutoff,
)


class CreateGateway:
    def __init__(self) -> None:
        self.events: dict[int, dict] = {}
        self.create_calls: list[dict] = []
        self.read_calls: list[str] = []
        self.next_id = 1201
        self.fail_create: BaseException | None = None
        self.store_on_timeout = False
        self.fail_read = False
        self.next_plan = None

    def create_event(self, payload: dict) -> dict:
        self.create_calls.append(copy.deepcopy(payload))
        if self.next_plan is not None:
            event = {
                "id": self.next_id,
                "category": "WORKOUT",
                "start_date_local": payload["start_date_local"],
                "type": self.next_plan.sport,
                "name": payload["name"],
                "external_id": payload["external_id"],
                "workout_doc": {
                    "steps": [
                        {
                            "text": "Dauerlauf",
                            "duration": 2700,
                            "hr": {"units": "hr_zone", "value": 2},
                        }
                    ]
                },
            }
            self.events[self.next_id] = event
        if self.fail_create is not None:
            if not self.store_on_timeout:
                self.events.pop(self.next_id, None)
            raise self.fail_create
        return {"id": self.next_id, "external_id": payload["external_id"]}

    def read_event(self, remote_id: str) -> dict:
        self.read_calls.append(remote_id)
        if self.fail_read:
            raise TimeoutError("Rücklesen weg")
        return copy.deepcopy(self.events[int(remote_id)])

    def update_event(self, remote_id: str, payload: dict) -> dict:
        raise AssertionError("P22 darf kein Update als Create-Ersatz auslösen")

    def find_by_external_id(self, external_id: str, day: str) -> list[dict]:
        del day
        return [
            copy.deepcopy(event)
            for event in self.events.values()
            if event.get("external_id") == external_id
        ]


def _new_plan():
    plan = build_plan_from_case(load_case("F01"))
    return replace(
        plan,
        local_id="plan:draft:f09",
        remote_id=None,
        external_id=None,
        name="Neue Einheit",
        date="2026-11-09",
        local_time=None,
        notes=None,
    )


def _draft(plan, operation_id: str = "op:f09"):
    return WorkoutDraft.new(plan, draft_id="draft:f09", operation_id=operation_id)


def _conn(tmp_path):
    conn = db.connect(tmp_path / "planner.db")
    db.init_db(conn)
    return conn


def test_plan_und_snapshot_roundtrip_erhaelt_struktur_und_identitaet(tmp_path) -> None:
    plan = build_plan_from_case(load_case("F02"))
    restored = plan_from_json(plan_to_json(plan))
    assert plan_to_json(restored) == plan_to_json(plan)
    assert restored.nodes == plan.nodes

    conn = _conn(tmp_path)
    store = SqliteOperationStore(conn)
    coordinator = SaveCoordinator(
        EventWriteService(CreateGateway()), recorder=store
    )
    draft = _draft(_new_plan())
    outcome = coordinator.preview(draft, account_id="acct", athlete_id="7")
    snapshot = outcome.snapshot
    assert snapshot is not None
    restored_snapshot = snapshot_from_json(snapshot_to_json(snapshot))
    assert snapshot_to_json(restored_snapshot) == snapshot_to_json(snapshot)
    conn.close()


def test_vorgang_ist_vor_dem_dispatch_gespeichert(tmp_path) -> None:
    conn = _conn(tmp_path)
    store = SqliteOperationStore(conn)
    plan = _new_plan()
    gateway = CreateGateway()
    gateway.next_plan = plan
    seen: list[tuple[str, str]] = []

    class SpyService(EventWriteService):
        def execute(self, snapshot: SaveSnapshot) -> WriteResult:
            row = db.planner_operation(conn, str(snapshot.operation_id))
            seen.append((row["state"], row["external_id"]))
            return super().execute(snapshot)

    coordinator = SaveCoordinator(SpyService(gateway), recorder=store)
    outcome = coordinator.activate(
        _draft(plan), account_id="acct", athlete_id="7"
    )

    assert outcome.status.state is SaveState.SAVED
    assert seen == [("saving", "tc:planner:acct:7:plan:draft:f09")]
    row = db.planner_operation(conn, "op:f09")
    assert row is not None
    assert row["state"] == "saved"
    assert row["remote_id"] == "1201"
    assert row["account_id"] == "acct"
    assert row["athlete_id"] == "7"
    conn.close()


def test_f09_nach_reload_genau_eine_einheit_und_kein_zweiter_create(tmp_path) -> None:
    case = load_case("F09")
    conn = _conn(tmp_path)
    store = SqliteOperationStore(conn)
    plan = _new_plan()
    gateway = CreateGateway()
    gateway.next_plan = plan
    gateway.fail_create = TimeoutError("Antwort verloren")
    gateway.store_on_timeout = True
    service = EventWriteService(gateway)
    coordinator = SaveCoordinator(service, recorder=store)

    first = coordinator.activate(_draft(plan), account_id="acct", athlete_id="7")

    assert first.status.state is SaveState.UNKNOWN
    assert len(gateway.create_calls) == 1
    row = db.planner_operation(conn, "op:f09")
    assert row is not None
    assert row["state"] == "unknown"
    assert row["external_id"] == "tc:planner:acct:7:plan:draft:f09"

    # App-Neustart: neuer Koordinator, derselbe persistierte Vorgang.
    reloaded = SaveCoordinator(service, recorder=store)
    restored = reloaded.restore_open(account_id="acct", athlete_id="7")
    assert [item.status.state for item in restored] == [SaveState.UNKNOWN]

    result = reloaded.reconcile("op:f09")

    assert result.status.state is SaveState.SAVED
    assert result.status.remote_id == "1201"
    assert len(gateway.create_calls) == 1
    key = next(iter(gateway.events))
    assert len(gateway.events) == 1
    assert gateway.events[key]["external_id"] == "tc:planner:acct:7:plan:draft:f09"
    assert case["expected"]["noSecondCreate"] is True
    assert case["expected"]["remoteEventsForOperation"] == 1
    conn.close()


def test_bestaetigtes_create_mit_fehlgeschlagenem_read_behaelt_remote_id(tmp_path) -> None:
    conn = _conn(tmp_path)
    store = SqliteOperationStore(conn)
    plan = _new_plan()
    gateway = CreateGateway()
    gateway.next_plan = plan
    gateway.fail_read = True
    service = EventWriteService(gateway)
    coordinator = SaveCoordinator(service, recorder=store)

    first = coordinator.activate(_draft(plan), account_id="acct", athlete_id="7")

    assert first.status.state is SaveState.SAVED_UNVERIFIED
    assert first.status.remote_id == "1201"
    row = db.planner_operation(conn, "op:f09")
    assert row is not None
    assert row["state"] == "savedUnverified"
    assert row["remote_id"] == "1201"

    reloaded = SaveCoordinator(service, recorder=store)
    restored = reloaded.restore_open(account_id="acct", athlete_id="7")
    assert [item.status.state for item in restored] == [SaveState.SAVED_UNVERIFIED]
    assert restored[0].status.remote_id == "1201"

    gateway.fail_read = False
    result = reloaded.reconcile("op:f09")

    assert result.status.state is SaveState.SAVED
    assert result.status.remote_id == "1201"
    assert len(gateway.create_calls) == 1
    conn.close()


def test_persistenzfehler_vor_dem_senden_verhindert_den_write() -> None:
    calls: list[str] = []

    class BrokenRecorder:
        def save(self, snapshot, state):
            raise OSError("Platte voll")

        def update(self, snapshot, state, *, confirmed=False, remote_id=None, external_id=None):
            raise AssertionError("darf nicht erreicht werden")

        def open_operations(self, *, account_id, athlete_id):
            return []

    class SpyService:
        def execute(self, snapshot):
            calls.append("execute")
            return WriteResult(SaveState.SAVED, "ok")

        def reconcile(self, snapshot):
            raise AssertionError("kein Abgleich")

    coordinator = SaveCoordinator(SpyService(), recorder=BrokenRecorder())
    outcome = coordinator.activate(_draft(_new_plan()), account_id="acct", athlete_id="7")

    assert outcome.status.state is SaveState.FAILED
    assert outcome.status.error is SaveErrorKind.RECONCILIATION
    assert outcome.status.persistence_error is not None
    assert calls == []


def test_metadatenfehler_nach_bestaetigtem_write_wiederholt_keinen_create(tmp_path) -> None:
    plan = _new_plan()
    gateway = CreateGateway()
    gateway.next_plan = plan
    calls = [0]

    class FailingUpdateStore(SqliteOperationStore):
        def update(self, snapshot, state, *, confirmed=False, remote_id=None, external_id=None):
            calls[0] += 1
            raise OSError("Metadaten kaputt")

    conn = _conn(tmp_path)
    coordinator = SaveCoordinator(
        EventWriteService(gateway), recorder=FailingUpdateStore(conn)
    )
    outcome = coordinator.activate(_draft(plan), account_id="acct", athlete_id="7")

    assert outcome.status.state is SaveState.SAVED
    assert outcome.status.persistence_error is not None
    assert len(gateway.create_calls) == 1
    assert calls[0] == 1
    conn.close()


def test_accounttrennung_und_aufbewahrung(tmp_path) -> None:
    conn = _conn(tmp_path)
    store = SqliteOperationStore(conn)
    plan = _new_plan()
    snapshot = SaveCoordinator(
        EventWriteService(CreateGateway())
    ).preview(_draft(plan), account_id="acct", athlete_id="7").snapshot
    assert snapshot is not None
    store.save(snapshot, SaveState.UNKNOWN)

    assert len(store.open_operations(account_id="acct", athlete_id="7")) == 1
    assert store.open_operations(account_id="other", athlete_id="7") == []

    # Ein abgeschlossener, alter Vorgang wird bereinigt; ein offener bleibt.
    old = "2020-01-01T00:00:00"
    db.upsert_planner_operation(
        conn,
        operation_id="op:old-saved",
        account_id="acct",
        athlete_id="7",
        local_id="plan:old",
        draft_id="draft:old",
        remote_id="42",
        external_id="tc:old",
        mode="update",
        kind="metadata",
        state="saved",
        payload_json="{}",
        snapshot_json=json.dumps(
            snapshot_to_json(
                replace(snapshot, operation_id="op:old-saved", local_id="plan:old")
            )
        ),
        editor_shape_json=None,
        editor_shape_state="prepared",
        created_at=old,
    )
    conn.execute(
        "UPDATE planner_operation SET updated_at = ? WHERE operation_id = 'op:old-saved'",
        (old,),
    )
    conn.commit()

    cutoff = retention_cutoff("2026-11-06T12:00:00")
    removed = store.purge_completed(now=cutoff)

    assert removed == 1
    assert db.planner_operation(conn, "op:old-saved") is None
    assert db.planner_operation(conn, "op:f09") is not None
    assert RETENTION_DAYS == 7
    conn.close()


def test_editorshape_wird_erst_nach_bestaetigung_veroeffentlicht(tmp_path) -> None:
    conn = _conn(tmp_path)
    store = SqliteOperationStore(conn)
    plan = _new_plan()
    coordinator = SaveCoordinator(EventWriteService(CreateGateway()))
    snapshot = coordinator.preview(_draft(plan), account_id="acct", athlete_id="7").snapshot
    assert snapshot is not None
    prepared = replace(
        snapshot,
        editor_shape={"version": 1, "nodes": [{"kind": "repeat", "repetitions": 4}]},
    )

    store.save(prepared, SaveState.SAVING)
    row = db.planner_operation(conn, "op:f09")
    assert row is not None
    assert row["editor_shape_state"] == "prepared"
    assert row["editor_shape_json"] is not None

    store.update(prepared, SaveState.SAVED, confirmed=True)
    row = db.planner_operation(conn, "op:f09")
    assert row is not None
    assert row["editor_shape_state"] == "confirmed"
    conn.close()
