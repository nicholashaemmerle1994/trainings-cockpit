"""P5–P7: Vorschau, persistenter Copy-Job und sequentieller Advance.

Die Tests nutzen ausschließlich einen kontrollierten Gateway. Es gibt keinen
Netzwerkzugriff und keinen echten intervals.icu-Schreibtest.
"""

from __future__ import annotations

import copy
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from planner_fixtures import load_remote

from trainings_cockpit import api, db
from trainings_cockpit.planner import EventWriteService, GatewayNotFound

F01 = load_remote("simple-zone-run.json")["event"]
F02 = load_remote("repeated-intervals.json")["event"]


class CopyGateway:
    def __init__(self) -> None:
        self.events: dict[int, dict] = {}
        self.create_calls: list[dict] = []
        self.read_calls: list[str] = []
        self.next_id = 3001
        self.fail_after_create = False
        self.fail_on_call: int | None = None
        self.block_create = threading.Event()
        self.create_started = threading.Event()
        self._lock = threading.Lock()

    def read_event(self, remote_id: str) -> dict:
        self.read_calls.append(remote_id)
        if int(remote_id) not in self.events:
            raise GatewayNotFound(remote_id)
        return copy.deepcopy(self.events[int(remote_id)])

    def update_event(self, remote_id: str, payload: dict) -> dict:
        del remote_id, payload
        raise AssertionError("Copy darf kein Update auslösen.")

    def create_event(self, payload: dict) -> dict:
        self.create_started.set()
        if self.block_create.is_set():
            self.block_create.wait(5)
        self.create_calls.append(copy.deepcopy(payload))
        if self.fail_on_call is not None and len(self.create_calls) == self.fail_on_call:
            raise TimeoutError("Antwort nach dem Anlegen verloren")
        event = copy.deepcopy(payload)
        event["id"] = self.next_id
        event.setdefault("category", "WORKOUT")
        event["workout_doc"] = copy.deepcopy(F01["workout_doc"])
        self.next_id += 1
        with self._lock:
            self.events[int(event["id"])] = event
        if self.fail_after_create:
            raise TimeoutError("Antwort nach dem Anlegen verloren")
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


def _connect():
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    return conn


def _store(event: dict, day: str | None = None) -> None:
    current = copy.deepcopy(event)
    if day is not None:
        current["start_date_local"] = f"{day}T00:00:00"
    conn = _connect()
    try:
        db.upsert_events(conn, [current])
        db.set_setting(
            conn,
            "synced_range",
            '{"from":"2025-01-01","events_to":"2027-12-31","activities_to":"2026-11-11"}',
        )
    finally:
        conn.close()


def _use_gateway(monkeypatch, gateway: CopyGateway) -> None:
    service = EventWriteService(gateway)

    @contextmanager
    def fake_service(settings):
        del settings
        yield service

    monkeypatch.setattr(api, "event_write_service", fake_service)


def _count(table: str) -> int:
    conn = _connect()
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])  # noqa: S608
    finally:
        conn.close()


def _preview(client: TestClient, *, source="2026-11-02", weeks=1, target="2026-11-09"):
    return client.post(
        "/api/planner/copy/preview",
        json={"source_start": source, "weeks": weeks, "target_start": target},
    )


def _start(
    client: TestClient,
    *,
    request_id="copy-request-0001",
    source="2026-11-02",
    weeks=1,
    target="2026-11-09",
):
    return client.post(
        "/api/planner/copy/jobs",
        json={
            "source_start": source,
            "weeks": weeks,
            "target_start": target,
            "client_request_id": request_id,
        },
    )


def _block_network(monkeypatch) -> None:
    def denied(*args, **kwargs):
        del args, kwargs
        raise AssertionError("Copy darf ohne kontrollierten Adapter kein Netzwerk öffnen.")

    monkeypatch.setattr(socket, "socket", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


# ---------------------------------------------------------------- Vorschau


def test_vorschau_ist_lesend_und_zeigt_nur_offene_planungen(client: TestClient) -> None:
    _store(F01, "2026-11-02")
    _store(F02, "2026-11-03")
    response = _preview(client)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["blockers"] == []
    assert [item["source_event_id"] for item in data["items"]] == ["9101", "9102"]
    assert data["coverage"] == {"source": "covered", "target": "covered"}
    assert data["existing_target_count"] == 0
    assert _count("planner_copy_job") == 0
    assert _count("planner_copy_item") == 0


def test_bereits_absolvierte_einheit_wird_nicht_kopiert(client: TestClient) -> None:
    _store(F01, "2026-11-02")
    conn = _connect()
    try:
        db.upsert_activities(
            conn,
            [
                {
                    "source": "garmin",
                    "source_id": "activity-1",
                    "date": "2026-11-02",
                    "start_local": "2026-11-02T08:00:00",
                    "sport": "Run",
                    "name": "Ruhiger Dauerlauf",
                    "duration_s": 2700,
                    "moving_s": 2700,
                    "distance_m": 15000,
                    "elevation_m": None,
                    "avg_hr": None,
                    "max_hr": None,
                    "avg_power": None,
                    "np": None,
                    "calories": None,
                    "load": None,
                    "intensity": None,
                    "raw": "{}",
                }
            ],
            mapped=True,
        )
    finally:
        conn.close()
    response = _preview(client)
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert any(item["code"] == "no_items" for item in response.json()["blockers"])


def test_fehlende_coverage_blockiert_und_erfindet_keine_leere_woche(client: TestClient) -> None:
    _store(F01, "2026-11-02")
    conn = _connect()
    try:
        db.set_setting(
            conn,
            "synced_range",
            '{"from":"2026-11-10","events_to":"2026-11-30","activities_to":"2026-11-11"}',
        )
    finally:
        conn.close()
    response = _preview(client)
    assert response.status_code == 200
    data = response.json()
    assert any(item["code"] == "source_coverage" for item in data["blockers"])
    assert data["coverage"]["source"] == "uncovered"


def test_ueberlappung_und_ungueltige_weeks_werden_abgelehnt(client: TestClient) -> None:
    _store(F01, "2026-11-02")
    overlap = _preview(client, target="2026-11-05")
    assert overlap.status_code == 200
    assert any(item["code"] == "overlap" for item in overlap.json()["blockers"])
    invalid = _preview(client, weeks=5)
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_weeks"


def test_vier_wochen_und_bestehende_zielplanung_bleiben(client: TestClient) -> None:
    _store(F01, "2026-11-02")
    _store({**F02, "id": 9302}, "2026-11-16")
    response = _preview(client, weeks=4, target="2026-12-07")
    assert response.status_code == 200
    data = response.json()
    assert data["weeks"] == 4
    assert data["target_end"] == "2027-01-03"
    assert data["existing_target_count"] == 0
    existing = _preview(client, weeks=1, target="2026-11-16")
    assert existing.status_code == 200
    assert existing.json()["existing_target_count"] == 1
    assert any(item["code"] == "existing_target" for item in existing.json()["warnings"])


# ------------------------------------------------------------------- Start


def test_start_persistiert_vor_dem_ersten_write_und_ist_idempotent(
    client: TestClient, monkeypatch
) -> None:
    _block_network(monkeypatch)
    _store(F01, "2026-11-02")
    first = _start(client)
    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["created"] is True
    assert payload["job"]["total"] == 1
    assert payload["job"]["pending"] == 1
    assert payload["job"]["state"] == "queued"
    assert _count("planner_copy_job") == 1
    assert _count("planner_copy_item") == 1
    assert _count("event") == 1

    second = _start(client)
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["job"]["job_id"] == payload["job"]["job_id"]
    assert _count("planner_copy_item") == 1


def test_advance_legt_sequentiell_an_und_zielplant_bestaetigt(
    client: TestClient, monkeypatch
) -> None:
    gateway = CopyGateway()
    _use_gateway(monkeypatch, gateway)
    _store(F01, "2026-11-02")
    _store({**F01, "id": 9103}, "2026-11-03")
    job = _start(client).json()["job"]
    assert gateway.create_calls == []

    first = client.post(f"/api/planner/copy/jobs/{job['job_id']}/advance")
    assert first.status_code == 200, first.text
    assert first.json()["job"]["created"] == 1
    assert first.json()["job"]["pending"] == 1
    assert len(gateway.create_calls) == 1

    second = client.post(f"/api/planner/copy/jobs/{job['job_id']}/advance")
    assert second.status_code == 200
    data = second.json()
    assert data["job"]["state"] == "completed"
    assert data["job"]["created"] == 2
    assert data["job"]["can_advance"] is False
    assert len(gateway.create_calls) == 2
    assert all(item["state"] == "created" for item in data["items"])
    assert _count("event") == 4


def test_zwei_wochen_werden_als_ein_block_kopiert(
    client: TestClient, monkeypatch
) -> None:
    gateway = CopyGateway()
    _use_gateway(monkeypatch, gateway)
    _store(F01, "2026-11-02")
    _store({**F01, "id": 9104}, "2026-11-09")
    preview = _preview(client, weeks=2, target="2026-11-16")
    assert preview.status_code == 200, preview.text
    assert preview.json()["source_end"] == "2026-11-15"
    assert preview.json()["target_end"] == "2026-11-29"
    assert [item["target_date"] for item in preview.json()["items"]] == [
        "2026-11-16",
        "2026-11-23",
    ]
    job = _start(client, weeks=2, target="2026-11-16").json()["job"]
    assert job["weeks"] == 2
    assert job["total"] == 2
    for _ in range(2):
        response = client.post(f"/api/planner/copy/jobs/{job['job_id']}/advance")
        assert response.status_code == 200
    assert response.json()["job"]["state"] == "completed"
    assert response.json()["job"]["created"] == 2


def test_doppelter_advance_parallel_ist_nur_einmal_aktiv(client: TestClient, monkeypatch) -> None:
    gateway = CopyGateway()
    gateway.block_create.set()
    _use_gateway(monkeypatch, gateway)
    _store(F01, "2026-11-02")
    job = _start(client).json()["job"]
    results: list[int] = []

    def run() -> None:
        response = client.post(f"/api/planner/copy/jobs/{job['job_id']}/advance")
        results.append(response.status_code)

    worker = threading.Thread(target=run)
    worker.start()
    assert gateway.create_started.wait(3)
    second = client.post(f"/api/planner/copy/jobs/{job['job_id']}/advance")
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "copy_busy"
    gateway.block_create.clear()
    worker.join(5)
    assert results == [200]
    assert len(gateway.create_calls) == 1


def test_unklarer_create_wird_nur_lesend_abgeglichen(client: TestClient, monkeypatch) -> None:
    gateway = CopyGateway()
    gateway.fail_after_create = True
    _use_gateway(monkeypatch, gateway)
    _store(F01, "2026-11-02")
    job = _start(client).json()["job"]

    first = client.post(f"/api/planner/copy/jobs/{job['job_id']}/advance")
    assert first.status_code == 200
    assert first.json()["items"][0]["state"] == "unknown"
    assert first.json()["job"]["can_advance"] is True
    assert len(gateway.create_calls) == 1
    open_jobs = client.get("/api/planner/copy/jobs?state=open").json()["jobs"]
    assert [entry["job_id"] for entry in open_jobs] == [job["job_id"]]

    from trainings_cockpit.planner import SaveCoordinator

    SaveCoordinator.reset_shared_state()
    second = client.post(f"/api/planner/copy/jobs/{job['job_id']}/advance")
    assert second.status_code == 200
    assert second.json()["items"][0]["state"] == "created"
    assert len(gateway.create_calls) == 1, "kein zweiter Create auf unklarem Zustand"


def test_offener_vorgang_aus_abgebrochenem_prozess_wird_gelesen(
    client: TestClient, monkeypatch
) -> None:
    """Ein offener planner_operation-Vorgang wird beim Fortsetzen gelesen.

    Der Remote-Create ist angekommen, die Item-Bestätigung fehlt. Ein zweiter
    Lauf darf nicht erneut senden, sondern muss den vorhandenen Vorgang
    lesend zuordnen.
    """
    gateway = CopyGateway()
    gateway.fail_after_create = True
    _use_gateway(monkeypatch, gateway)
    _store(F01, "2026-11-02")
    job = _start(client).json()["job"]
    first = client.post(f"/api/planner/copy/jobs/{job['job_id']}/advance")
    assert first.status_code == 200
    assert first.json()["items"][0]["state"] == "unknown"
    assert len(gateway.create_calls) == 1
    gateway.fail_after_create = False
    resumed = client.post(f"/api/planner/copy/jobs/{job['job_id']}/advance")
    assert resumed.status_code == 200
    assert resumed.json()["items"][0]["state"] == "created"
    assert len(gateway.create_calls) == 1


def test_preview_start_konflikt_legt_nichts_an(client: TestClient, monkeypatch) -> None:
    _use_gateway(monkeypatch, CopyGateway())
    _store(F01, "2026-11-02")
    assert _preview(client).status_code == 200
    conn = _connect()
    try:
        db.delete_event(conn, 9101)
    finally:
        conn.close()
    response = _start(client)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "preview_changed"
    assert _count("planner_copy_job") == 0
    assert _count("planner_copy_item") == 0


def test_bereits_kopierte_quelle_wird_nicht_dupliziert(client: TestClient, monkeypatch) -> None:
    gateway = CopyGateway()
    _use_gateway(monkeypatch, gateway)
    _store(F01, "2026-11-02")
    job = _start(client).json()["job"]
    client.post(f"/api/planner/copy/jobs/{job['job_id']}/advance")
    again = _preview(client)
    assert again.status_code == 200
    assert again.json()["items"][0]["status"] == "already_copied"
    assert _start(client, request_id="copy-request-0002").status_code == 409
    assert len(gateway.create_calls) == 1


def test_teilweise_kopie_rollt_nichts_zurueck(client: TestClient, monkeypatch) -> None:
    gateway = CopyGateway()
    gateway.fail_on_call = 2
    _use_gateway(monkeypatch, gateway)
    _store(F01, "2026-11-02")
    _store({**F01, "id": 9103}, "2026-11-03")
    job = _start(client).json()["job"]
    first = client.post(f"/api/planner/copy/jobs/{job['job_id']}/advance")
    assert first.status_code == 200
    second = client.post(f"/api/planner/copy/jobs/{job['job_id']}/advance")
    assert second.status_code == 200
    data = second.json()
    assert data["job"]["state"] == "partial"
    assert data["job"]["created"] == 1
    assert data["job"]["unknown"] == 1
    assert _count("event") == 3, "die erste angelegte Einheit bleibt erhalten"


def test_bestehende_zielplanung_bleibt_bei_der_kopie_unveraendert(
    client: TestClient, monkeypatch
) -> None:
    gateway = CopyGateway()
    _use_gateway(monkeypatch, gateway)
    _store(F01, "2026-11-02")
    _store({**F01, "id": 9401, "name": "Bestehende Zielplanung"}, "2026-11-09")
    job = _start(client).json()["job"]
    client.post(f"/api/planner/copy/jobs/{job['job_id']}/advance")
    conn = _connect()
    try:
        row = db.event_by_id(conn, 9401)
        assert row is not None
        assert row["name"] == "Bestehende Zielplanung"
        assert row["date"] == "2026-11-09"
    finally:
        conn.close()


def test_kalenderarithmetik_ueber_monat_jahr_und_sommerzeit(client: TestClient) -> None:
    _store(F01, "2026-03-23")
    spring = _preview(client, source="2026-03-23", weeks=2, target="2026-04-06")
    assert spring.status_code == 200
    body = spring.json()
    assert body["source_end"] == "2026-04-05"
    assert body["target_end"] == "2026-04-19"
    assert [item["target_date"] for item in body["items"]] == ["2026-04-06"]
    _store({**F01, "id": 9501}, "2026-12-28")
    winter = _preview(client, source="2026-12-28", weeks=2, target="2027-01-11")
    assert winter.status_code == 200
    assert winter.json()["target_end"] == "2027-01-24"


def test_fremder_scope_sieht_den_job_nicht(client: TestClient, monkeypatch) -> None:
    _use_gateway(monkeypatch, CopyGateway())
    _store(F01, "2026-11-02")
    job = _start(client).json()["job"]
    conn = _connect()
    try:
        db.set_setting(conn, "account_id", "anderer-account")
    finally:
        conn.close()
    response = client.get(f"/api/planner/copy/jobs/{job['job_id']}")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"
