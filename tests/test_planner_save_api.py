"""P23: Produktspeichern, bestätigte Übernahme und Sync ohne Doppelzählung."""

from __future__ import annotations

import copy
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

import pytest
from fastapi.testclient import TestClient
from planner_fixtures import load_remote

from trainings_cockpit import api, db
from trainings_cockpit.planner import EventWriteService, GatewayNotFound

F01 = load_remote("simple-zone-run.json")["event"]


class SaveGateway:
    def __init__(self, events: dict[int, dict] | None = None) -> None:
        self.events = copy.deepcopy(events or {})
        self.update_calls: list[tuple[str, dict]] = []
        self.create_calls: list[dict] = []
        self.read_calls: list[str] = []
        self.next_id = 1201

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
        # Der vorhandene Client nutzt einen Upsert; dieselbe externe Identität
        # aktualisiert dieselbe Remote-Einheit, statt eine zweite anzulegen.
        for event in self.events.values():
            if event.get("external_id") == payload.get("external_id"):
                event.update(copy.deepcopy(payload))
                return copy.deepcopy(event)
        event = {
            "id": self.next_id,
            "category": "WORKOUT",
            "start_date_local": payload["start_date_local"],
            "type": "Run",
            "name": payload["name"],
            "external_id": payload["external_id"],
            "workout_doc": {
                "steps": [{"text": "Dauerlauf", "duration": 2700}],
            },
        }
        self.events[self.next_id] = event
        return copy.deepcopy(event)

    def find_by_external_id(self, external_id: str, day: str) -> list[dict]:
        del day
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


def _use_gateway(monkeypatch, gateway: SaveGateway) -> None:
    service = EventWriteService(gateway)

    @contextmanager
    def fake_service(settings):
        del settings
        yield service

    monkeypatch.setattr(api, "event_write_service", fake_service)


def _store_event(event: dict) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.upsert_events(conn, [event])
    conn.close()


def _event_rows() -> list[dict]:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    rows = db.events_between(conn, date(2026, 1, 1), date(2027, 1, 1))
    conn.close()
    return rows


def _draft_body(client: TestClient, event_id: int, **overrides) -> dict:
    detail = client.get(f"/api/planner/plan/{event_id}").json()
    body = {"name": detail["name"], "nodes": detail["nodes"]}
    body.update(overrides)
    return body


def test_gespeicherte_aenderung_erscheint_genau_einmal_und_ohne_zweiten_write(
    client: TestClient, monkeypatch
) -> None:
    _store_event(F01)
    gateway = SaveGateway({int(F01["id"]): F01})
    _use_gateway(monkeypatch, gateway)
    body = _draft_body(client, 9101, name="Ruhiger Abendlauf")

    response = client.post("/api/planner/plan/9101/save", json=body)
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"]["state"] == "saved"
    assert payload["confirmed"]["name"] == "Ruhiger Abendlauf"
    assert payload["event_id"] == "9101"
    assert payload["week"] == "2026-11-02"
    assert payload["old_week"] == "2026-11-02"
    assert len(gateway.update_calls) == 1
    rows = _event_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == 9101
    assert rows[0]["name"] == "Ruhiger Abendlauf"

    # Derselbe bestätigte Stand erneut geöffnet und gespeichert: kein Write.
    second = client.post("/api/planner/plan/9101/save", json=body).json()
    assert second["status"]["state"] == "clean"
    assert len(gateway.update_calls) == 1

    # Ein Sync mit derselben tatsächlichen Event-ID aktualisiert dieselbe Zeile.
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.upsert_events(conn, [gateway.events[9101]])
    db.upsert_events(conn, [gateway.events[9101]])
    assert conn.execute("SELECT COUNT(*) FROM event").fetchone()[0] == 1
    conn.close()
    assert len(_event_rows()) == 1


def test_terminwechsel_aktualisiert_alte_und_neue_woche(
    client: TestClient, monkeypatch
) -> None:
    _store_event(F01)
    gateway = SaveGateway({int(F01["id"]): F01})
    _use_gateway(monkeypatch, gateway)
    body = _draft_body(client, 9101, date="2026-11-12")

    payload = client.post("/api/planner/plan/9101/save", json=body).json()

    assert payload["status"]["state"] == "saved"
    assert payload["old_week"] == "2026-11-02"
    assert payload["week"] == "2026-11-09"
    old = client.get("/api/planner", params={"week": "2026-11-02"}).json()
    new = client.get("/api/planner", params={"week": "2026-11-09"}).json()
    assert old["entries"] == []
    assert [entry["name"] for entry in new["entries"]] == [F01["name"]]


def test_konflikt_liefert_die_drei_aktionen_und_schreibt_nicht(
    client: TestClient, monkeypatch
) -> None:
    _store_event(F01)
    gateway = SaveGateway({int(F01["id"]): F01})
    _use_gateway(monkeypatch, gateway)
    body = _draft_body(client, 9101, name="Lokal")

    external = copy.deepcopy(F01)
    external["name"] = "Extern"
    external["workout_doc"]["steps"][0]["duration"] = 1500
    gateway.events[9101] = external

    payload = client.post("/api/planner/plan/9101/save", json=body).json()

    assert payload["status"]["state"] == "conflict"
    assert payload["status"]["conflict"]["kind"] == "structure"
    assert payload["status"]["conflict"]["actions"] == [
        "view_remote",
        "return_to_draft",
        "discard_local_use_remote",
    ]
    assert payload["confirmed"] is None
    assert gateway.update_calls == []
    assert _event_rows()[0]["name"] == F01["name"]


def test_neue_einheit_wird_genau_einmal_angelegt(
    client: TestClient, monkeypatch
) -> None:
    gateway = SaveGateway()
    _use_gateway(monkeypatch, gateway)
    body = {
        "draft_id": "draft:neu-1",
        "sport": "Run",
        "date": "2026-11-11",
        "name": "Abendlauf",
        "template": "simple",
    }

    first = client.post("/api/planner/draft/save", json=body).json()

    assert first["status"]["state"] == "saved"
    assert first["event_id"] == "1201"
    assert first["week"] == "2026-11-09"
    rows = _event_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == 1201
    assert rows[0]["name"] == "Abendlauf"
    week = client.get("/api/planner", params={"week": "2026-11-09"}).json()
    saved = next(entry for entry in week["entries"] if entry["name"] == "Abendlauf")
    assert saved["planned"]["minutes"] == 45
    assert saved["planned"]["known_seconds"] == 2700

    # Ein Wiederholungsversuch derselben Anlage wird als bereits bestätigter
    # Stand erkannt und erzeugt weder einen zweiten Request noch eine Einheit.
    second = client.post("/api/planner/draft/save", json=body).json()
    assert second["status"]["state"] == "saved"
    assert second["event_id"] == "1201"
    assert len(gateway.create_calls) == 1
    assert len(gateway.events) == 1
    assert len(_event_rows()) == 1


def test_aktivitaetssync_zaehlt_neue_aufzeichnung_nur_einmal(
    client: TestClient,
) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    row = {
        "id": "act-sync-1",
        "start_date_local": "2026-11-03T07:00:00",
        "type": "Run",
        "name": "Neue Aufzeichnung",
        "moving_time": 1800,
        "distance": 5000,
        "icu_training_load": 30,
    }
    db.upsert_activities(conn, [row])
    db.upsert_activities(conn, [row])
    assert conn.execute("SELECT COUNT(*) FROM activity").fetchone()[0] == 1
    conn.close()

    week = client.get("/api/planner", params={"week": "2026-11-02"}).json()
    assert week["summary"]["recorded"]["seconds"] == 1800
    assert week["summary"]["recorded"]["count"] == 1
    overview = client.get("/api/overview").json()
    assert overview["today"]["load"]["week_seconds"] == 1800

    # Eine korrigierte Aufzeichnung behält ihre kanonische Zeile und
    # aktualisiert Woche, Dashboard und Aktivitätsdetail gemeinsam.
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.upsert_activities(conn, [{**row, "moving_time": 2400}])
    assert conn.execute("SELECT COUNT(*) FROM activity").fetchone()[0] == 1
    row_id = conn.execute("SELECT id FROM activity").fetchone()[0]
    conn.close()
    corrected = client.get("/api/planner", params={"week": "2026-11-02"}).json()
    assert corrected["summary"]["recorded"]["seconds"] == 2400
    assert corrected["summary"]["recorded"]["count"] == 1
    unit = client.get(f"/api/unit/{row_id}").json()
    assert unit["duration_min"] == 40


def test_keine_beziehung_und_kein_write_durch_darstellung(
    client: TestClient, monkeypatch
) -> None:
    _store_event(F01)
    gateway = SaveGateway({int(F01["id"]): F01})
    _use_gateway(monkeypatch, gateway)

    week = client.get("/api/planner", params={"week": "2026-11-02"}).json()
    assert [entry["kind"] for entry in week["entries"]] == ["planned"]
    assert week["summary"]["recorded"]["count"] == 0
    assert week["summary"]["open_plan"]["count"] == 1
    assert gateway.update_calls == []
    assert gateway.create_calls == []


def test_remote_uebernehmen_liest_nur_und_sortiert_die_aktuelle_version_ein(
    client: TestClient, monkeypatch
) -> None:
    _store_event(F01)
    remote = copy.deepcopy(F01)
    remote["name"] = "Aktuell remote"
    gateway = SaveGateway({int(F01["id"]): remote})
    _use_gateway(monkeypatch, gateway)

    class Reader:
        def event(self, event_id):
            assert event_id == 9101
            return copy.deepcopy(remote)

    @contextmanager
    def fake_read(settings):
        del settings
        yield Reader()

    monkeypatch.setattr(api, "event_read_service", fake_read)
    payload = client.get("/api/planner/plan/9101/remote").json()

    assert payload["name"] == "Aktuell remote"
    assert gateway.update_calls == []
    assert gateway.create_calls == []
    assert _event_rows()[0]["name"] == "Aktuell remote"
    assert len(_event_rows()) == 1


def test_planerwoche_traegt_account_und_athlet_fuer_den_cache(
    client: TestClient,
) -> None:
    payload = client.get("/api/planner", params={"week": "2026-11-02"}).json()
    assert payload["account_id"] == "default"
    assert payload["athlete_id"] == "default"
    assert "default" in payload["query"]["key"]
