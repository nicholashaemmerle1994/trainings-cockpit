from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from trainings_cockpit import api, db


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


def _activity(conn, source_id: str, day: str, minutes: int, sport: str = "Run") -> None:
    db.upsert_activities(
        conn,
        [
            {
                "id": source_id,
                "start_date_local": f"{day}T07:00:00",
                "type": sport,
                "name": source_id,
                "moving_time": minutes * 60,
                "distance": 5000,
                "icu_training_load": 30,
            }
        ],
    )


def test_planner_week_has_seven_days_and_separate_sources(client: TestClient) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    _activity(conn, "sa", "2026-10-31", 30)
    _activity(conn, "so", "2026-11-01", 40)
    _activity(conn, "mo", "2026-11-02", 50)
    _activity(conn, "fr", "2026-11-06", 60)
    db.upsert_events(
        conn,
        [
            {
                "id": 1101,
                "start_date_local": "2026-11-08T00:00:00",
                "type": "Run",
                "category": "WORKOUT",
                "name": "Sonntagsplanung",
                "moving_time": 2700,
            }
        ],
    )
    conn.close()

    payload = client.get("/api/planner", params={"week": "2026-11-06"}).json()

    assert payload["from"] == "2026-11-02"
    assert payload["to"] == "2026-11-08"
    assert payload["label"] == "2.–8. November 2026"
    assert [day["date"] for day in payload["days"]] == [
        "2026-11-02",
        "2026-11-03",
        "2026-11-04",
        "2026-11-05",
        "2026-11-06",
        "2026-11-07",
        "2026-11-08",
    ]
    assert [entry["kind"] for entry in payload["entries"]] == [
        "recorded",
        "recorded",
        "planned",
    ]
    assert [entry["name"] for entry in payload["entries"]] == ["mo", "fr", "Sonntagsplanung"]
    assert payload["summary"]["recorded"]["seconds"] == 6600
    assert payload["summary"]["recorded"]["count"] == 2
    assert payload["summary"]["open_plan"]["seconds"] == 2700
    assert payload["summary"]["open_plan"]["count"] == 1
    assert payload["summary"]["open_plan"]["distance_metres"] == 0
    assert payload["summary"]["open_plan"]["has_unknown"] is False
    assert payload["sources"]["plans"]["state"] == "complete"
    assert payload["sources"]["activities"]["state"] == "complete"
    assert payload["query"]["key"] != payload["query"]["dashboard_key"]


def test_frisch_bestaetigtes_event_ohne_dauer_spalte_zeigt_seinen_workout_doc(
    client: TestClient,
) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    raw = {
        "id": 12300,
        "category": "WORKOUT",
        "start_date_local": "2026-11-04T00:00:00",
        "type": "Run",
        "name": "Frisch gespeichert",
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
    db.upsert_events(conn, [raw])
    conn.close()

    payload = client.get("/api/planner", params={"week": "2026-11-02"}).json()
    entry = next(entry for entry in payload["entries"] if entry["name"] == "Frisch gespeichert")

    assert entry["planned"]["minutes"] == 45
    assert entry["planned"]["known_seconds"] == 2700
    assert payload["summary"]["open_plan"]["seconds"] == 2700


def test_planner_koppelt_das_dashboard_nicht_an_die_gewaehlte_woche(client: TestClient) -> None:
    payload = client.get("/api/planner", params={"week": "2026-08-03"}).json()
    dashboard = client.get("/api/overview").json()

    assert payload["query"]["key"].count("2026-08-03") == 1
    assert "2026-08-03" not in dashboard["today"]["date"]
    assert dashboard["today"]["load"]["week_seconds"] == 0


def test_ausfall_der_aktivitaeten_entfernt_keine_planung(
    client: TestClient, monkeypatch
) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.upsert_events(
        conn,
        [
            {
                "id": 1401,
                "start_date_local": "2026-09-01T18:00:00",
                "type": "Run",
                "category": "WORKOUT",
                "name": "Plan sichtbar",
                "moving_time": 1800,
            }
        ],
    )
    conn.close()

    def broken(*args, **kwargs):
        raise RuntimeError("Aktivitätsquelle nicht verfügbar")

    monkeypatch.setattr(db, "training_between", broken)
    payload = client.get("/api/planner", params={"week": "2026-08-31"}).json()

    assert payload["sources"]["activities"]["state"] == "error"
    assert payload["sources"]["plans"]["state"] == "complete"
    assert [entry["name"] for entry in payload["entries"]] == ["Plan sichtbar"]
    assert payload["summary"]["recorded"]["seconds"] is None
    assert payload["summary"]["open_plan"]["seconds"] == 1800


def test_ausfall_der_planungen_entfernt_keine_aktivitaet(
    client: TestClient, monkeypatch
) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    _activity(conn, "partial-a", "2026-08-25", 30)
    conn.close()

    def broken(*args, **kwargs):
        raise RuntimeError("Planquelle nicht verfügbar")

    monkeypatch.setattr(db, "events_between", broken)
    payload = client.get("/api/planner", params={"week": "2026-08-24"}).json()

    assert payload["sources"]["plans"]["state"] == "error"
    assert payload["sources"]["activities"]["state"] == "complete"
    assert [entry["name"] for entry in payload["entries"]] == ["partial-a"]
    assert payload["summary"]["recorded"]["seconds"] == 1800
    assert payload["summary"]["open_plan"]["seconds"] is None
    assert payload["summary"]["open_plan"]["has_unknown"] is True


def test_nicht_gesyncte_woche_ist_nicht_bestaetigt_leer(client: TestClient) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.set_setting(
        conn,
        "synced_range",
        '{"from":"2026-08-03","to":"2026-08-09","activities_to":"2026-08-09",'
        '"events_to":"2027-08-09"}',
    )
    conn.close()

    payload = client.get("/api/planner", params={"week": "2026-08-17"}).json()

    assert payload["sources"]["activities"]["state"] == "unavailable"
    assert payload["sources"]["plans"]["coverage"] == "covered"
    assert payload["summary"]["recorded"]["seconds"] is None
    assert payload["summary"]["recorded"]["count"] is None
    assert payload["days"][0]["entries"] == []


def test_leere_woche_ist_nach_vollstaendigem_lesen_leer(client: TestClient) -> None:
    payload = client.get("/api/planner", params={"week": "2026-08-10"}).json()

    assert payload["sources"]["activities"]["state"] == "empty"
    assert payload["sources"]["plans"]["state"] == "empty"
    assert payload["summary"]["recorded"]["seconds"] == 0
    assert payload["summary"]["open_plan"]["count"] == 0
    assert all(day["entries"] == [] for day in payload["days"])


def test_week_liefert_gezielten_zeitraum(client: TestClient) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    _activity(conn, "alt", "2026-08-03", 30)
    _activity(conn, "neu", "2026-09-01", 45)
    conn.close()

    payload = client.get(
        "/api/week", params={"from": "2026-08-03", "to": "2026-08-09"}
    ).json()

    assert payload["from"] == "2026-08-03"
    assert payload["to"] == "2026-08-09"
    assert payload["seconds"] == 1800
    assert [unit["name"] for unit in payload["units"]] == ["alt"]


def test_ungueltige_woche_wird_abgewiesen(client: TestClient) -> None:
    assert client.get("/api/planner", params={"week": "31.10.2026"}).status_code == 400
    assert client.get("/api/week", params={"from": "2026-09-01"}).status_code == 200


def test_unvollstaendig_bekannter_plan_markiert_die_offene_summe(
    client: TestClient,
) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.upsert_events(
        conn,
        [
            {
                "id": 9107,
                "category": "WORKOUT",
                "start_date_local": "2026-11-08T09:15:00",
                "type": "Ride",
                "name": "Import mit unbekanntem Inhalt",
                "workout_doc": {
                    "steps": [
                        {"text": "Einrollen", "duration": 600},
                        {"text": "Rampe", "duration": 600, "ramp": True},
                    ]
                },
            }
        ],
    )
    conn.close()

    payload = client.get("/api/planner", params={"week": "2026-11-02"}).json()
    open_plan = payload["summary"]["open_plan"]

    assert open_plan["count"] == 1
    assert open_plan["seconds"] == 600
    assert open_plan["has_unknown"] is True


def test_nur_teilweise_abgedeckte_woche_ist_nicht_bestaetigt_leer(
    client: TestClient,
) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.set_setting(
        conn,
        "synced_range",
        '{"from":"2026-08-05","to":"2026-08-20",'
        '"activities_to":"2026-08-20","events_to":"2027-08-20"}',
    )
    conn.close()

    payload = client.get("/api/planner", params={"week": "2026-08-03"}).json()

    assert payload["sources"]["activities"]["coverage"] == "uncovered"
    assert payload["sources"]["activities"]["state"] == "unavailable"
    assert payload["summary"]["recorded"]["seconds"] is None
    assert all(day["entries"] == [] for day in payload["days"])


def test_teilweise_abgedeckte_woche_mit_zeilen_ist_partial(
    client: TestClient,
) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    _activity(conn, "teil", "2026-08-07", 30)
    db.set_setting(
        conn,
        "synced_range",
        '{"from":"2026-08-06","to":"2026-08-20",'
        '"activities_to":"2026-08-20","events_to":"2027-08-20"}',
    )
    conn.close()

    payload = client.get("/api/planner", params={"week": "2026-08-03"}).json()

    assert payload["sources"]["activities"]["state"] == "partial"
    assert payload["summary"]["recorded"]["complete"] is False
    assert payload["summary"]["recorded"]["seconds"] == 1800
    # Die vorhandene Aufzeichnung bleibt sichtbar, auch wenn die Woche
    # nicht vollständig gelesen wurde.
    assert [entry["name"] for entry in payload["entries"]] == ["teil"]


def test_aktuelles_wochenende_gilt_fuer_aufzeichnungen_als_abgedeckt(
    client: TestClient,
) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.set_setting(
        conn,
        "synced_range",
        '{"from":"2025-11-06","to":"2026-11-06",'
        '"activities_to":"2026-11-06","events_to":"2027-11-06"}',
    )
    conn.close()

    payload = client.get("/api/planner", params={"week": "2026-11-02"}).json()

    assert payload["to"] == "2026-11-08"
    assert payload["sources"]["activities"]["coverage"] == "covered"
    assert payload["sources"]["activities"]["state"] == "empty"
    assert payload["summary"]["recorded"]["seconds"] == 0
