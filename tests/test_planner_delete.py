"""TB-16: geplante Einheiten löschen, auch wenn die Quelle sie nicht mehr kennt."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from planner_fixtures import load_remote

from trainings_cockpit import api, db
from trainings_cockpit.planner import (
    EventDeleteService,
    GatewayNotFound,
    IntervalsEventAdapter,
)

F01 = load_remote("simple-zone-run.json")["event"]


class DeleteGateway:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.error: Exception | None = None

    def delete_event(self, remote_id: str) -> object:
        self.calls.append(remote_id)
        if self.error is not None:
            raise self.error
        return 1


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TC_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("INTERVALS_API_KEY", "test")
    monkeypatch.setenv("TC_GOALS", "[]")
    monkeypatch.setenv("TC_TIME_ZONE", "Europe/Vienna")
    api.get_settings.cache_clear()
    with TestClient(api.app) as test_client:
        yield test_client
    api.get_settings.cache_clear()


def _use_gateway(monkeypatch, gateway: DeleteGateway) -> None:
    service = EventDeleteService(gateway)

    @contextmanager
    def fake_service(settings):
        del settings
        yield service

    monkeypatch.setattr(api, "event_delete_service", fake_service)


def _store_event() -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.upsert_events(conn, [F01])
    conn.close()


def _event_rows() -> list[dict]:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    rows = conn.execute("SELECT * FROM event").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def test_loeschen_entfernt_die_einheit_remote_und_lokal(
    client: TestClient, monkeypatch
) -> None:
    _store_event()
    gateway = DeleteGateway()
    _use_gateway(monkeypatch, gateway)

    response = client.delete("/api/planner/plan/9101")
    payload = response.json()

    assert response.status_code == 200
    assert payload == {
        "deleted": True,
        "event_id": 9101,
        "week": "2026-11-02",
        "remote": "deleted",
        "message": "Die Einheit wurde in intervals.icu und im Trainingskalender gelöscht.",
    }
    assert gateway.calls == ["9101"]
    assert _event_rows() == []


def test_extern_geloeschte_einheit_laesst_sich_trotzdem_entfernen(
    client: TestClient, monkeypatch
) -> None:
    """AC: nicht auffindbar heißt nicht „nicht löschbar“."""
    _store_event()
    gateway = DeleteGateway()
    gateway.error = GatewayNotFound("9101")
    _use_gateway(monkeypatch, gateway)

    response = client.delete("/api/planner/plan/9101")
    payload = response.json()

    assert response.status_code == 200
    assert payload["remote"] == "missing"
    assert payload["deleted"] is True
    assert _event_rows() == []


def test_quellenfehler_laesst_den_lokalen_bestand_stehen(
    client: TestClient, monkeypatch
) -> None:
    _store_event()
    gateway = DeleteGateway()
    gateway.error = RuntimeError("intervals.icu ist nicht erreichbar")
    _use_gateway(monkeypatch, gateway)

    response = client.delete("/api/planner/plan/9101")

    assert response.status_code == 502
    assert "nicht erreichbar" in response.json()["detail"]
    assert [row["id"] for row in _event_rows()] == [9101]


def test_unbekannte_einheit_ist_404(client: TestClient, monkeypatch) -> None:
    gateway = DeleteGateway()
    _use_gateway(monkeypatch, gateway)

    response = client.delete("/api/planner/plan/9999")

    assert response.status_code == 404
    assert gateway.calls == []


def test_adapter_sendet_genau_die_event_id_an_bulk_delete() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.refs: list[dict] | None = None

        def event(self, event_id: int) -> dict:
            return {"id": event_id}

        def update_event(self, event_id: int, event: dict) -> dict:
            return {"id": event_id}

        def upsert_events(self, events: list[dict]) -> list[dict]:
            return events

        def delete_events(self, refs: list[dict]) -> int:
            self.refs = refs
            return len(refs)

    client = FakeClient()
    adapter = IntervalsEventAdapter(client)

    adapter.delete_event("9101")

    assert client.refs == [{"id": 9101}]
