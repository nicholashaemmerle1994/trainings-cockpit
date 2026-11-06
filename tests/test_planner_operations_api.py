"""P22: offene Vorgänge über die vorhandene App-Persistenz und API."""

from __future__ import annotations

import copy
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from planner_fixtures import build_plan_from_case, load_case

from trainings_cockpit import api, db
from trainings_cockpit.planner import (
    EventWriteService,
    GatewayNotFound,
    SaveCoordinator,
    SaveState,
    WorkoutDraft,
)
from trainings_cockpit.planner.operations import SqliteOperationStore


class ReconcileGateway:
    def __init__(self, event: dict) -> None:
        self.events = {int(event["id"]): copy.deepcopy(event)}
        self.calls: list[str] = []
        self.find_calls: list[str] = []

    def read_event(self, remote_id: str) -> dict:
        self.calls.append(remote_id)
        return copy.deepcopy(self.events[int(remote_id)])

    def create_event(self, payload: dict) -> dict:
        raise AssertionError("Ein Abgleich darf keinen Create auslösen")

    def update_event(self, remote_id: str, payload: dict) -> dict:
        raise AssertionError("Ein Abgleich darf keinen Write auslösen")

    def find_by_external_id(self, external_id: str, day: str) -> list[dict]:
        del day
        self.find_calls.append(external_id)
        return [
            copy.deepcopy(event)
            for event in self.events.values()
            if event.get("external_id") == external_id
        ]


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TC_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("INTERVALS_API_KEY", "")
    monkeypatch.setenv("TC_GOALS", "[]")
    monkeypatch.setenv("TC_TIME_ZONE", "Europe/Vienna")
    api.get_settings.cache_clear()
    from trainings_cockpit.planner import SaveCoordinator

    SaveCoordinator.reset_shared_state()
    with TestClient(api.app) as test_client:
        yield test_client
    SaveCoordinator.reset_shared_state()
    api.get_settings.cache_clear()


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


def _remote_event(external_id: str) -> dict:
    return {
        "id": 9201,
        "category": "WORKOUT",
        "start_date_local": "2026-11-09T00:00:00",
        "type": "Run",
        "name": "Neue Einheit",
        "external_id": external_id,
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


def _store_unknown(client: TestClient) -> str:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    draft = WorkoutDraft.new(
        _new_plan(), draft_id="draft:f09", operation_id="op:f09"
    )
    coordinator = SaveCoordinator(EventWriteService(ReconcileGateway(_remote_event("x"))))
    outcome = coordinator.preview(draft, account_id="default", athlete_id="default")
    snapshot = outcome.snapshot
    assert snapshot is not None
    SqliteOperationStore(conn).save(snapshot, SaveState.UNKNOWN)
    conn.close()
    return str(snapshot.external_id)


def test_offener_vorgang_ueberlebt_reload_und_wird_abgeglichen(
    client: TestClient, monkeypatch
) -> None:
    external_id = _store_unknown(client)
    assert external_id
    gateway = ReconcileGateway(_remote_event(external_id))
    service = EventWriteService(gateway)

    @contextmanager
    def fake_service(settings):
        del settings
        yield service

    monkeypatch.setattr(api, "event_write_service", fake_service)

    listing = client.get("/api/planner/operations").json()
    assert listing["account_id"] == "default"
    assert listing["athlete_id"] == "default"
    assert [item["operation_id"] for item in listing["items"]] == ["op:f09"]
    assert listing["items"][0]["state"] == "unknown"
    assert "payload" not in listing["items"][0]

    result = client.post("/api/planner/operations/op:f09/reconcile").json()

    assert result["status"]["state"] == "saved"
    assert result["status"]["remote_id"] == "9201"
    assert result["status"]["reconciliation_required"] is False
    assert result["confirmed"]["remote_id"] == "9201"
    assert result["week"] == "2026-11-09"
    assert result["time_zone"] == "Europe/Vienna"
    week = client.get("/api/planner", params={"week": "2026-11-09"}).json()
    assert [entry["name"] for entry in week["entries"]] == ["Neue Einheit"]
    assert week["entries"][0]["planned"]["minutes"] == 45
    assert gateway.calls == []
    assert len(gateway.find_calls) == 1
    # Abgeschlossen: erscheint nicht mehr als offener Vorgang.
    assert client.get("/api/planner/operations").json()["items"] == []


def test_fremder_vorgang_wird_nicht_abgeglichen(
    client: TestClient, monkeypatch
) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    draft = WorkoutDraft.new(
        _new_plan(), draft_id="draft:foreign", operation_id="op:foreign"
    )
    snapshot = (
        SaveCoordinator(EventWriteService(ReconcileGateway(_remote_event("x"))))
        .preview(draft, account_id="anderer-account", athlete_id="default")
        .snapshot
    )
    assert snapshot is not None
    SqliteOperationStore(conn).save(snapshot, SaveState.UNKNOWN)
    conn.close()

    @contextmanager
    def fake_service(settings):
        del settings
        raise AssertionError("fremder Vorgang darf keinen Adapter öffnen")

    monkeypatch.setattr(api, "event_write_service", fake_service)
    response = client.post("/api/planner/operations/op:foreign/reconcile")

    assert response.status_code == 404
    assert client.get("/api/planner/operations").json()["items"] == []


class MissingGateway:
    """Quelle kennt das Event nicht mehr und findet auch keine externe Identität."""

    def read_event(self, remote_id: str) -> dict:
        raise GatewayNotFound(remote_id)

    def create_event(self, payload: dict) -> dict:
        raise AssertionError("Ein Abgleich darf keinen Create auslösen")

    def update_event(self, remote_id: str, payload: dict) -> dict:
        raise AssertionError("Ein Abgleich darf keinen Write auslösen")

    def find_by_external_id(self, external_id: str, day: str) -> list[dict]:
        del external_id, day
        return []


def test_verschwundenes_event_wird_verworfen_und_lokal_geraeumt(
    client: TestClient, monkeypatch
) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    draft = WorkoutDraft.new(
        _new_plan(), draft_id="draft:f09", operation_id="op:f09"
    )
    snapshot = (
        SaveCoordinator(EventWriteService(ReconcileGateway(_remote_event("x"))))
        .preview(draft, account_id="default", athlete_id="default")
        .snapshot
    )
    assert snapshot is not None
    SqliteOperationStore(conn).save(
        replace(snapshot, remote_id="9201"), SaveState.UNKNOWN
    )
    db.upsert_events(
        conn,
        [
            {
                "id": 9201,
                "start_date_local": "2026-11-09T00:00:00",
                "type": "Run",
                "category": "WORKOUT",
                "name": "Neue Einheit",
            }
        ],
    )
    assert db.event_by_id(conn, 9201) is not None
    conn.close()

    service = EventWriteService(MissingGateway())

    @contextmanager
    def fake_service(settings):
        del settings
        yield service

    monkeypatch.setattr(api, "event_write_service", fake_service)

    result = client.post("/api/planner/operations/op:f09/reconcile").json()

    assert result["status"]["state"] == "failed"
    assert result["status"]["error"] == "not_found"
    assert result["status"]["remote_id"] == "9201"
    assert "nicht vorhanden" in result["status"]["message"]
    assert client.get("/api/planner/operations").json()["items"] == []

    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    try:
        assert db.event_by_id(conn, 9201) is None
    finally:
        conn.close()
    week = client.get("/api/planner", params={"week": "2026-11-09"}).json()
    assert all(entry["name"] != "Neue Einheit" for entry in week["entries"])
