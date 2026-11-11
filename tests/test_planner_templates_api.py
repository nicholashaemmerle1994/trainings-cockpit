"""P2: Vorlagen-API — Speichern, Liste, Details, lokale Projektion, Löschen.

Alle Aufrufe bleiben lokal. Der Test blockiert Netzwerk und die Event-Services
ausdrücklich, damit ein versehentlicher Remote-Pfad sofort scheitert.
"""

from __future__ import annotations

import copy
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

import pytest
from fastapi.testclient import TestClient
from planner_fixtures import load_remote

from trainings_cockpit import api, db
from trainings_cockpit.planner import (
    get_template,
    node_shape,
    read_plan_row,
)

F01 = load_remote("simple-zone-run.json")["event"]
F02 = load_remote("repeated-intervals.json")["event"]

#: Eine Radeinheit mit HF-Zone, Watt-Wiederholungen und einem %FTP-Abschnitt.
RIDE_EVENT = {
    "id": 9203,
    "category": "WORKOUT",
    "start_date_local": "2026-11-04T00:00:00",
    "type": "Ride",
    "name": "Radeinheit mit HF und Watt",
    "workout_doc": {
        "steps": [
            {
                "text": "Einrollen",
                "duration": 600,
                "warmup": True,
                "hr": {"units": "hr_zone", "value": 1},
            },
            {
                "text": "Dreimal Arbeit und Erholung",
                "reps": 3,
                "steps": [
                    {
                        "text": "Arbeit",
                        "duration": 600,
                        "power": {"units": "watts", "start": 160, "end": 170},
                    },
                    {
                        "text": "Erholung",
                        "duration": 300,
                        "power": {"units": "watts", "start": 90, "end": 110},
                    },
                ],
            },
            {
                "text": "Schwelle",
                "duration": 600,
                "power": {"units": "%ftp", "start": 85, "end": 95},
            },
            {
                "text": "Ausrollen",
                "duration": 600,
                "cooldown": True,
                "hr": {"units": "hr_zone", "value": 1},
            },
        ]
    },
}

#: Schwimmen mit neutralen Schrittnamen, Distanz, Pace und Zeitpause.
SWIM_EVENT = {
    "id": 9205,
    "category": "WORKOUT",
    "start_date_local": "2026-11-06T00:00:00",
    "type": "Swim",
    "name": "Achtmal 100 Meter",
    "workout_doc": {
        "steps": [
            {
                "text": "Achtmal 100 m",
                "reps": 8,
                "steps": [
                    {
                        "text": "Schwimmzug",
                        "distance": 100,
                        "pace": {"units": "secs/100m", "value": 120},
                    },
                    {"text": "Pause", "duration": 30},
                ],
            }
        ]
    },
}


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TC_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("INTERVALS_API_KEY", "")
    monkeypatch.setenv("TC_GOALS", "[]")
    monkeypatch.setenv("TC_TIME_ZONE", "Europe/Vienna")
    api.get_settings.cache_clear()
    with TestClient(api.app) as test_client:
        yield test_client
    api.get_settings.cache_clear()


def _connect():
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    return conn


def _store_event(event: dict) -> None:
    conn = _connect()
    try:
        db.upsert_events(conn, [event])
    finally:
        conn.close()


def _event_rows() -> list[dict]:
    conn = _connect()
    try:
        return db.events_between(conn, date(2026, 1, 1), date(2027, 1, 1))
    finally:
        conn.close()


def _template_rows() -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM workout_template ORDER BY created_at, template_id"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _count(table: str) -> int:
    conn = _connect()
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])  # noqa: S608
    finally:
        conn.close()


def _scoped_template(template_id: str, *, account: str = "default", athlete: str = "default"):
    conn = _connect()
    try:
        return get_template(
            conn,
            template_id,
            account_id=account,
            athlete_id=athlete,
        )
    finally:
        conn.close()


def _source_plan(event_id: int):
    settings = api.get_settings()
    conn = _connect()
    try:
        row = db.event_by_id(conn, event_id)
        assert row is not None
        return read_plan_row(row, time_zone=settings.time_zone).plan
    finally:
        conn.close()


def _set_scope(*, account: str, athlete: str) -> None:
    conn = _connect()
    try:
        db.set_setting(conn, "account_id", account)
        db.set_setting(conn, "athlete_id", athlete)
    finally:
        conn.close()


def _create_template(client: TestClient, event: dict, name: str = "Vorlage") -> dict:
    _store_event(event)
    response = client.post(
        f"/api/planner/templates/from-plan/{event['id']}",
        json={"name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _block_remote(monkeypatch) -> None:
    def denied(*args, **kwargs):
        del args, kwargs
        raise AssertionError("Vorlagen-API darf keinen Remote-Aufruf auslösen.")

    monkeypatch.setattr(socket, "socket", denied)
    monkeypatch.setattr(socket, "create_connection", denied)

    @contextmanager
    def denied_service(settings):
        del settings
        raise AssertionError("Vorlagen-API darf keinen Event-Service öffnen.")
        yield  # pragma: no cover - nur für den Contextmanager-Vertrag

    monkeypatch.setattr(api, "event_write_service", denied_service)
    monkeypatch.setattr(api, "event_read_service", denied_service)
    monkeypatch.setattr(api, "event_delete_service", denied_service)


# ---------------------------------------------------------------- Speichern


def test_speichern_aus_plan_legt_nur_eine_lokale_vorlage_an(client: TestClient) -> None:
    _store_event(F01)
    before = _event_rows()

    response = client.post(
        "/api/planner/templates/from-plan/9101",
        json={"name": "  Ruhiger Abendlauf  "},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["template_id"].startswith("tpl:")
    assert payload["name"] == "Ruhiger Abendlauf"
    assert payload["sport"] == "Run"
    assert payload["source_event_id"] == "9101"
    assert payload["known"]["seconds"] == 2700
    assert [node["kind"] for node in payload["nodes"]] == ["step"]
    assert payload["nodes"][0]["name"] == "Dauerlauf"
    assert payload["nodes"][0]["target"]["kind"] == "zone"
    assert payload["nodes"][0]["target"]["zone_id"] == "run-hr-2"

    rows = _template_rows()
    assert len(rows) == 1
    assert rows[0]["template_id"] == payload["template_id"]
    assert rows[0]["source_event_id"] == "9101"
    assert _event_rows() == before
    assert _count("planner_operation") == 0

    listing = client.get("/api/planner/templates").json()
    assert [item["template_id"] for item in listing["items"]] == [payload["template_id"]]
    item = listing["items"][0]
    assert "nodes" not in item
    assert item["name"] == "Ruhiger Abendlauf"
    assert item["sport"] == "Run"
    assert item["known_seconds"] == 2700
    assert item["updated_at"]
    assert item["available"] is True

    detail = client.get(f"/api/planner/templates/{payload['template_id']}")
    assert detail.status_code == 200
    assert detail.json()["known"]["seconds"] == 2700
    assert detail.json()["nodes"][0]["node_id"] == payload["nodes"][0]["node_id"]


def test_body_nodes_beeinflussen_die_gespeicherte_vorlage_nicht(client: TestClient) -> None:
    _store_event(F02)

    response = client.post(
        "/api/planner/templates/from-plan/9102",
        json={
            "name": "Nur der Name zählt",
            "nodes": [
                {
                    "kind": "step",
                    "node_id": "node:eingeschleust",
                    "name": "Eingeschleust",
                    "role": "work",
                    "end": {"kind": "time", "seconds": 36000},
                    "target": {"kind": "none"},
                }
            ],
            "sport": "Ride",
            "date": "2027-01-01",
            "source_event_id": "999",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["sport"] == "Run"
    assert payload["source_event_id"] == "9102"
    assert payload["name"] == "Nur der Name zählt"
    assert payload["known"]["seconds"] == 2160
    assert [node["name"] for node in payload["nodes"]] == [
        "Einlaufen",
        "Hauptteil 4x",
        "Auslaufen",
    ]
    assert all(node["name"] != "Eingeschleust" for node in payload["nodes"])
    assert "36000" not in str(payload["nodes"])

    stored = _scoped_template(payload["template_id"])
    assert stored is not None
    source = _source_plan(9102)
    assert [node_shape(node) for node in stored.nodes] == [
        node_shape(node) for node in source.nodes
    ]


@pytest.mark.parametrize(
    ("label", "event", "expected_code", "expected_clone_code"),
    [
        (
            "notizen",
            {**copy.deepcopy(F01), "notes": "Bitte locker bleiben."},
            "source_not_cloneable",
            "notes",
        ),
        (
            "unsupported",
            {
                **copy.deepcopy(F01),
                "workout_doc": {
                    "steps": [
                        {
                            "text": "Rampe",
                            "duration": 300,
                            "ramp": True,
                        }
                    ]
                },
            },
            "source_not_cloneable",
            "unsupported_node",
        ),
        (
            "sport",
            {**copy.deepcopy(F01), "type": "Yoga"},
            "sport_unsupported",
            None,
        ),
    ],
)
def test_ungueltige_quelle_legt_keine_vorlage_an(
    client: TestClient,
    label: str,
    event: dict,
    expected_code: str,
    expected_clone_code: str | None,
) -> None:
    del label
    _store_event(event)

    response = client.post(
        f"/api/planner/templates/from-plan/{event['id']}",
        json={"name": "Nicht speichern"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == expected_code
    assert detail.get("clone_code") == expected_clone_code
    assert _template_rows() == []


def test_ungueltige_quelle_und_name_liefern_keine_zeile(client: TestClient) -> None:
    _store_event(F01)

    missing = client.post("/api/planner/templates/from-plan/9999", json={"name": "X"})
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "not_found"

    for name, code in (
        ("   ", "name_empty"),
        ("x" * 121, "name_too_long"),
        ("Zeile\numbruch", "name_invalid"),
    ):
        response = client.post(
            "/api/planner/templates/from-plan/9101",
            json={"name": name},
        )
        assert response.status_code == 422, name
        assert response.json()["detail"]["code"] == code
    assert _template_rows() == []


# ------------------------------------------------------------------- Scope


def test_liste_details_projektion_und_loeschen_sind_scope_gebunden(
    client: TestClient,
) -> None:
    created = _create_template(client, F01)
    template_id = created["template_id"]
    _set_scope(account="fremd", athlete="default")

    listing = client.get("/api/planner/templates")
    assert listing.status_code == 200
    assert listing.json()["items"] == []
    foreign = client.get(f"/api/planner/templates/{template_id}")
    assert foreign.status_code == 404
    assert foreign.json()["detail"]["code"] == "not_found"
    project = client.post(
        f"/api/planner/templates/{template_id}/project",
        json={"date": "2026-11-17", "draft_id": "draft:new:fremd"},
    )
    assert project.status_code == 404
    deleted = client.delete(f"/api/planner/templates/{template_id}")
    assert deleted.status_code == 404
    assert len(_template_rows()) == 1

    _set_scope(account="default", athlete="anderer")
    assert client.get("/api/planner/templates").json()["items"] == []
    assert client.get(f"/api/planner/templates/{template_id}").status_code == 404

    _set_scope(account="default", athlete="default")
    assert len(client.get("/api/planner/templates").json()["items"]) == 1
    unknown = client.get("/api/planner/templates/tpl:gibt-es-nicht")
    assert unknown.status_code == 404


def test_loeschen_entfernt_nur_die_vorlage(client: TestClient) -> None:
    created = _create_template(client, F01)
    template_id = created["template_id"]
    events_before = _event_rows()

    first = client.delete(f"/api/planner/templates/{template_id}")

    assert first.status_code == 200
    assert first.json() == {
        "deleted": True,
        "template_id": template_id,
        "events_deleted": False,
    }
    assert _template_rows() == []
    assert _event_rows() == events_before
    assert client.delete(f"/api/planner/templates/{template_id}").status_code == 404


# --------------------------------------------------------------- Beschädigt


def test_beschaedigte_zeile_ist_422_und_in_der_liste_corrupt(client: TestClient) -> None:
    created = _create_template(client, F01)
    template_id = created["template_id"]
    conn = _connect()
    try:
        conn.execute(
            "UPDATE workout_template SET nodes_json = '[]' WHERE template_id = ?",
            (template_id,),
        )
        conn.commit()
    finally:
        conn.close()

    detail = client.get(f"/api/planner/templates/{template_id}")
    assert detail.status_code == 422
    assert detail.json()["detail"]["code"] == "corrupt"

    item = client.get("/api/planner/templates").json()["items"][0]
    assert item["template_id"] == template_id
    assert item["available"] is False
    assert item["error_code"] == "corrupt"


# --------------------------------------------------------------- Projektion


def test_projektion_ist_lokal_und_zwei_projektionen_sind_unabhaengig(
    client: TestClient, monkeypatch
) -> None:
    created = _create_template(client, F02, name="Intervalle")
    template_id = created["template_id"]
    events_before = _event_rows()
    _block_remote(monkeypatch)

    first = client.post(
        f"/api/planner/templates/{template_id}/project",
        json={"date": "2026-11-17", "draft_id": "draft:new:eins"},
    )
    second = client.post(
        f"/api/planner/templates/{template_id}/project",
        json={"date": "2026-11-17", "draft_id": "draft:new:zwei"},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    one = first.json()
    two = second.json()

    assert one["kind"] == "planned"
    assert one["date"] == "2026-11-17"
    assert one["time"] is None
    assert one["draft_id"] == "draft:new:eins"
    assert one["local_id"] == "plan:draft:new:eins"
    assert one["draft"]["is_new"] is True
    assert one["draft"]["dirty"] is True
    assert one["template"] == {
        "template_id": template_id,
        "name": "Intervalle",
        "sport": "Run",
    }
    assert one["known"]["seconds"] == 2160
    assert [node["kind"] for node in one["nodes"]] == ["step", "repeat", "step"]
    assert one["nodes"][1]["repetitions"] == 4

    assert two["draft_id"] == "draft:new:zwei"
    assert two["local_id"] != one["local_id"]
    first_ids = [node["node_id"] for node in one["nodes"]]
    second_ids = [node["node_id"] for node in two["nodes"]]
    assert set(first_ids).isdisjoint(second_ids)
    assert set(first_ids).isdisjoint(
        {node["node_id"] for node in created["nodes"]}
    )

    assert _event_rows() == events_before
    assert _count("event") == 1
    assert _count("planner_operation") == 0
    assert _count("workout_template") == 1

    stored = _scoped_template(template_id)
    assert stored is not None
    assert [node_shape(node) for node in stored.nodes] == [
        node_shape(node) for node in _source_plan(9102).nodes
    ]


@pytest.mark.parametrize(
    ("label", "event"),
    [
        ("run", F02),
        ("ride", RIDE_EVENT),
        ("swim", SWIM_EVENT),
    ],
)
def test_run_ride_swim_strukturen_bleiben_erhalten(
    client: TestClient, label: str, event: dict
) -> None:
    created = _create_template(client, event, name=f"Vorlage {label}")
    template_id = created["template_id"]

    response = client.post(
        f"/api/planner/templates/{template_id}/project",
        json={"date": "2026-11-18", "draft_id": f"draft:new:{label}"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sport"] == event["type"]
    nodes = payload["nodes"]

    if label == "run":
        assert [node["kind"] for node in nodes] == ["step", "repeat", "step"]
        assert nodes[0]["target"]["zone_id"] == "run-hr-2"
        repeat = nodes[1]
        assert repeat["repetitions"] == 4
        pace = repeat["children"][0]["target"]
        assert pace["kind"] == "pace"
        assert pace["unit"] == "secondsPerKm"
        assert pace["values"] == {"kind": "range", "min": 330, "max": 345}
        assert repeat["children"][1]["target"]["zone_id"] == "run-hr-1"
        assert payload["known"]["seconds"] == 2160
    elif label == "ride":
        assert [node["kind"] for node in nodes] == ["step", "repeat", "step", "step"]
        assert nodes[0]["target"]["zone_id"] == "ride-hr-1"
        repeat = nodes[1]
        assert repeat["repetitions"] == 3
        work = repeat["children"][0]["target"]
        assert work["kind"] == "power"
        assert work["unit"] == "watts"
        assert work["values"] == {"kind": "range", "min": 160, "max": 170}
        ftp = nodes[2]["target"]
        assert ftp["kind"] == "power"
        assert ftp["unit"] == "percentFtp"
        assert ftp["values"] == {"kind": "range", "min": 85, "max": 95}
        assert nodes[3]["target"]["zone_id"] == "ride-hr-1"
        assert payload["known"]["seconds"] == 4500
    else:
        assert [node["kind"] for node in nodes] == ["repeat"]
        repeat = nodes[0]
        assert repeat["repetitions"] == 8
        swim = repeat["children"][0]
        assert swim["end"] == {"kind": "distance", "metres": 100, "text": "100 m"}
        assert swim["target"]["kind"] == "pace"
        assert swim["target"]["unit"] == "secondsPer100m"
        assert swim["target"]["values"] == {"kind": "value", "value": 120}
        assert repeat["children"][1]["end"]["kind"] == "time"
        assert repeat["children"][1]["end"]["seconds"] == 30
        assert payload["draft"]["valid"] is True


def test_projektion_lehnt_ungueltiges_datum_und_fehlende_draft_id_ab(
    client: TestClient,
) -> None:
    created = _create_template(client, F01)
    template_id = created["template_id"]

    bad_date = client.post(
        f"/api/planner/templates/{template_id}/project",
        json={"date": "2026-13-01", "draft_id": "draft:new:x"},
    )
    missing_id = client.post(
        f"/api/planner/templates/{template_id}/project",
        json={"date": "2026-11-17"},
    )
    empty_id = client.post(
        f"/api/planner/templates/{template_id}/project",
        json={"date": "2026-11-17", "draft_id": "  "},
    )

    assert bad_date.status_code == 422
    assert bad_date.json()["detail"]["code"] == "source_not_cloneable"
    assert bad_date.json()["detail"]["clone_code"] == "invalid_date"
    assert missing_id.status_code == 422
    assert missing_id.json()["detail"]["code"] == "invalid_draft_id"
    assert empty_id.status_code == 422
    assert empty_id.json()["detail"]["code"] == "invalid_draft_id"


def test_alle_vorlagenpfade_ohne_netz_und_ohne_event_schreibpfad(
    client: TestClient, monkeypatch
) -> None:
    _store_event(F01)
    _block_remote(monkeypatch)

    created = client.post(
        "/api/planner/templates/from-plan/9101",
        json={"name": "Offline"},
    )
    assert created.status_code == 201
    template_id = created.json()["template_id"]
    assert client.get("/api/planner/templates").status_code == 200
    assert client.get(f"/api/planner/templates/{template_id}").status_code == 200
    assert (
        client.post(
            f"/api/planner/templates/{template_id}/project",
            json={"date": "2026-11-17", "draft_id": "draft:new:offline"},
        ).status_code
        == 200
    )
    assert client.delete(f"/api/planner/templates/{template_id}").status_code == 200

    assert _count("event") == 1
    assert _count("planner_operation") == 0
    assert _count("workout_template") == 0
