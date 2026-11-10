from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from trainings_cockpit import api, db


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("TC_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("INTERVALS_API_KEY", "")
    monkeypatch.setenv("TC_GOALS", "[]")
    api.get_settings.cache_clear()

    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    today = date.today()
    db.upsert_activities(
        conn,
        [
            {
                "id": "i1",
                "start_date_local": f"{today.isoformat()}T07:00:00",
                "type": "Run",
                "name": "Testlauf",
                "moving_time": 1800,
                "distance": 5000,
                "average_heartrate": 150,
                "icu_training_load": 40,
            }
        ],
    )
    db.upsert_wellness(
        conn,
        [
            {
                "id": (today - timedelta(days=offset)).isoformat(),
                "hrv": 50,
                "restingHR": 48,
                "sleepSecs": 8 * 3600,
                "awakeSleepSeconds": 20 * 60,
                "respiration": 13.0,
                "sleepScore": 80,
                "ctl": 50,
                "atl": 45,
            }
            for offset in range(30)
        ],
    )
    db.set_setting(conn, "athlete_name", "Nicholas Pahr")
    conn.close()

    with TestClient(api.app) as test_client:
        yield test_client

    api.get_settings.cache_clear()


def test_overview_returns_dashboard_payload(client: TestClient) -> None:
    response = client.get("/api/overview")
    assert response.status_code == 200
    payload = response.json()

    assert payload["athlete"]["name"] == "Nicholas Pahr"
    assert payload["today"]["recovery"]["score"] is not None
    # Fitness rechnet das Cockpit aus den eigenen Aktivitäten (D-34), nicht aus
    # den Tageswerten von intervals.
    ctl = payload["today"]["load"]["ctl"]
    assert ctl is not None and 0 < ctl < 200
    assert len(payload["series"]["load"]) == 90
    assert payload["activities"][0]["sport_label"] == "Laufen"
    assert payload["goals"] == []


def test_activities_can_be_filtered_by_sport(client: TestClient) -> None:
    response = client.get("/api/activities", params={"sport": "Run"})
    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "Testlauf"

    empty = client.get("/api/activities", params={"sport": "Swim"})
    assert empty.json()["items"] == []


def test_health_reports_counts(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["activities"] == 1
    assert payload["wellness"] == 30


def test_sync_requires_key(client: TestClient) -> None:
    response = client.post("/api/sync")
    assert response.status_code == 400


def test_fuel_defaults_to_last_known_weight(client: TestClient) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.upsert_wellness(
        conn,
        [
            {
                "id": date.today().isoformat(),
                "hrv": 50,
                "restingHR": 48,
                "sleepSecs": 8 * 3600,
                "awakeSleepSeconds": 20 * 60,
                "respiration": 13.0,
                "weight": 81.2,
            }
        ],
    )
    conn.close()

    response = client.get("/api/fuel", params={"minutes": 180, "mode": "race"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["input"]["weight_kg"] == 81.2
    assert payload["per_hour"]["carbs"] > 0
    assert payload["modes"][0]["key"] == "locker"


def test_fuel_rejects_unknown_mode(client: TestClient) -> None:
    assert client.get("/api/fuel", params={"mode": "rennen"}).status_code == 400


def test_fuel_can_use_maple_syrup(client: TestClient) -> None:
    response = client.get(
        "/api/fuel", params={"minutes": 240, "mode": "race", "source": "syrup", "shot": 50}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["input"]["source"] == "syrup"
    assert payload["syrup"]["shots"] > 0
    assert payload["sources"][1]["key"] == "syrup"


def test_fuel_rejects_unknown_source(client: TestClient) -> None:
    assert client.get("/api/fuel", params={"source": "cola"}).status_code == 400


def test_overview_liefert_warnregeln_und_abzug(client: TestClient) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.upsert_wellness(
        conn,
        [
            {
                "id": date.today().isoformat(),
                "hrv": 40,
                "restingHR": 56,
                "sleepSecs": 3 * 3600,
                "awakeSleepSeconds": 6 * 60,
                "respiration": 13.0,
            }
        ],
    )
    conn.close()

    recovery = client.get("/api/overview").json()["today"]["recovery"]

    assert recovery["date"] == date.today().isoformat()
    assert recovery["adjustment"] == -15
    assert recovery["score"] is not None
    assert {rule["id"] for rule in recovery["triggeredRules"]} == {
        "hrv_rhr",
        "hrv_sleep",
        "rhr_sleep",
        "triple_low",
    }
    assert all(
        set(rule) == {"id", "label", "adjustment"} for rule in recovery["triggeredRules"]
    )


def test_vendor_score_can_be_saved(client: TestClient) -> None:
    heute = date.today().isoformat()
    response = client.post("/api/vendor-score", params={"day": heute, "score": 51})
    assert response.status_code == 200
    assert response.json()["saved"] == 51

    overview = client.get("/api/overview").json()
    assert overview["today"]["vendor"] == 51
    assert overview["series"]["recovery"][-1]["vendor"] == 51


def test_vendor_score_survives_a_sync_overwrite(tmp_path, monkeypatch) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    heute = date.today().isoformat()
    db.set_vendor_score(conn, heute, 51)
    db.upsert_wellness(
        conn,
        [{"id": heute, "hrv": 29, "restingHR": 62, "sleepSecs": 23760}],
    )
    assert db.vendor_scores(conn)[heute] == 51
    conn.close()


def test_vendor_score_rejects_bad_input(client: TestClient) -> None:
    assert (
        client.post("/api/vendor-score", params={"day": "31.10.2026", "score": 51}).status_code
        == 400
    )
    assert client.post("/api/vendor-score", params={"day": "2026-10-31", "score": 140}).status_code


def test_week_lists_the_units_of_the_last_seven_days(client: TestClient) -> None:
    payload = client.get("/api/week").json()

    assert payload["seconds"] == 1800
    assert payload["load"] == 40
    assert payload["units"][0]["name"] == "Testlauf"
    assert payload["units"][0]["row_id"] > 0


def test_unit_zeigt_zonen_und_quelle(client: TestClient) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.upsert_activities(
        conn,
        [
            {
                "id": "i2",
                "start_date_local": f"{date.today().isoformat()}T06:00:00",
                "type": "Ride",
                "name": "Testfahrt",
                "moving_time": 3600,
                "elapsed_time": 4000,
                "distance": 30000,
                "icu_training_load": 60,
                "icu_hr_zone_times": [0, 0, 1800, 1800, 0, 0, 0],
                "source": "WAHOO",
            }
        ],
    )
    row_id = conn.execute("SELECT id FROM activity WHERE source_id = 'i2'").fetchone()["id"]
    conn.close()

    payload = client.get(f"/api/unit/{row_id}").json()

    assert payload["name"] == "Testfahrt"
    assert payload["origin"] == "Wahoo"
    assert payload["zone_source"] == "intervals.icu"
    assert [zone["zone"] for zone in payload["zones"] if zone["share"] > 0] == [3, 4]
    assert payload["total_min"] == 67


def test_unit_kennt_keine_unbekannte_zeile(client: TestClient) -> None:
    assert client.get("/api/unit/999999").status_code == 404


def test_dazugekommene_einheit_steht_auf_der_karte(client: TestClient) -> None:
    """Was heute ohne Plan passiert ist, gehört auf dieselbe Karte (D-43)."""
    payload = client.get("/api/overview").json()

    assert [unit["name"] for unit in payload["unplanned"]] == ["Testlauf"]
    assert payload["unplanned"][0]["minutes"] == 30


def test_geplante_einheit_zaehlt_nicht_als_dazugekommen(client: TestClient) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.upsert_events(
        conn,
        [
            {
                "id": 42,
                "start_date_local": f"{date.today().isoformat()}T07:00:00",
                "type": "Run",
                "category": "WORKOUT",
                "name": "Dauerlauf",
                "moving_time": 1800,
            }
        ],
    )
    conn.close()

    payload = client.get("/api/overview").json()
    assert payload["unplanned"] == []
    assert payload["sessions"][0]["done"] is True


def test_atemuebung_zaehlt_nicht_als_einheit(client: TestClient) -> None:
    """Eine Entspannungsübung ist keine Trainingseinheit (D-44)."""
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.upsert_activities(
        conn,
        [
            {
                "id": "i-entspannung",
                "start_date_local": f"{date.today().isoformat()}T22:30:00",
                "type": "Workout",
                "name": "Entsp. u. konzentr. (kurz)",
                "moving_time": 333,
            }
        ],
    )
    conn.close()

    payload = client.get("/api/overview").json()
    week = client.get("/api/week").json()

    assert [unit["name"] for unit in payload["unplanned"]] == ["Testlauf"]
    assert payload["today"]["load"]["week_sessions"] == 1
    assert payload["today"]["load"]["week_seconds"] == 1800
    assert [unit["name"] for unit in week["units"]] == ["Testlauf"]


def _set_epoch(days_ago: int) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.set_wellness_epoch(conn, date.today() - timedelta(days=days_ago))
    conn.close()


def test_bevel_feld_erscheint_waehrend_die_referenz_entsteht(client: TestClient) -> None:
    _set_epoch(2)

    payload = client.get("/api/overview").json()

    assert payload["today"]["recovery"]["vendor_prompt"] is True


def test_bevel_feld_verschwindet_nach_dem_vergleichsfenster(client: TestClient) -> None:
    """Eine Woche nach voller Referenz ist der Abgleich vorbei (D-52)."""
    _set_epoch(40)

    payload = client.get("/api/overview").json()

    assert payload["today"]["recovery"]["vendor_prompt"] is False


def test_ohne_sensorwechsel_kein_bevel_feld(client: TestClient) -> None:
    payload = client.get("/api/overview").json()

    assert payload["today"]["recovery"]["vendor_prompt"] is False


def test_overview_marks_today_plan_source_only_when_known(client: TestClient) -> None:
    payload = client.get("/api/overview").json()
    # Ohne Event und ohne Abdeckungsmarke bleibt der lokale Bestand maßgeblich:
    # Die Planung ist bekannt leer, nicht „nicht verfügbar“.
    assert payload["today"]["plan_source"] == {
        "state": "empty",
        "complete": True,
        "count": 0,
        "coverage": "unknown",
    }

    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.set_setting(
        conn,
        "synced_range",
        '{"from":"2025-01-01","to":"2025-02-01",'
        '"activities_to":"2025-02-01","events_to":"2025-02-01"}',
    )
    conn.close()

    payload = client.get("/api/overview").json()
    assert payload["today"]["plan_source"]["state"] == "unavailable"
    assert payload["today"]["plan_source"]["complete"] is False
    assert payload["today"]["plan_source"]["coverage"] == "uncovered"


def test_overview_counts_today_plan_as_complete(client: TestClient) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.upsert_events(
        conn,
        [
            {
                "id": 4242,
                "start_date_local": f"{date.today().isoformat()}T18:00:00",
                "type": "Run",
                "name": "Abendlauf",
                "category": "WORKOUT",
            }
        ],
    )
    conn.close()

    payload = client.get("/api/overview").json()
    source = payload["today"]["plan_source"]
    assert source["state"] == "complete"
    assert source["complete"] is True
    assert source["count"] == 1
