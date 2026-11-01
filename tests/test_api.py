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
