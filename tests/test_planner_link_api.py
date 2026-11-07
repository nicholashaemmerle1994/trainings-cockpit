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


def _activity(
    conn,
    source_id: str,
    day: str,
    minutes: int = 60,
    sport: str = "Run",
    start: str = "07:00",
) -> int:
    db.upsert_activities(
        conn,
        [
            {
                "id": source_id,
                "start_date_local": f"{day}T{start}:00",
                "type": sport,
                "name": source_id,
                "moving_time": minutes * 60,
                "distance": 10000,
                "icu_training_load": 50,
            }
        ],
    )
    row = conn.execute(
        "SELECT id FROM activity WHERE source_id = ?", (source_id,)
    ).fetchone()
    assert row is not None
    return int(row["id"])


def _event(
    conn,
    event_id: int,
    day: str,
    minutes: int = 60,
    sport: str = "Run",
    name: str | None = None,
) -> None:
    db.upsert_events(
        conn,
        [
            {
                "id": event_id,
                "start_date_local": f"{day}T00:00:00",
                "type": sport,
                "category": "WORKOUT",
                "name": name or f"Plan {event_id}",
                "moving_time": minutes * 60,
            }
        ],
    )


def _kinds(payload: dict) -> list[str]:
    return [entry["kind"] for entry in payload["entries"]]


def test_eindeutige_paarung_erscheint_im_planer_nur_einmal(client: TestClient) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    row_id = _activity(conn, "a", "2026-11-04", minutes=60)
    _event(conn, 501, "2026-11-04", minutes=60, name="Tempo Lauf")
    conn.close()

    payload = client.get("/api/planner", params={"week": "2026-11-02"}).json()

    assert _kinds(payload) == ["linked"]
    entry = payload["entries"][0]
    assert entry["status"] == "completed"
    assert entry["plan_id"] == 501
    assert entry["relationship_id"] == f"auto:501:{row_id}"
    assert [view["name"] for view in entry["activities"]] == ["a"]
    assert payload["summary"]["recorded"]["seconds"] == 3600
    assert payload["summary"]["recorded"]["count"] == 1
    assert payload["summary"]["open_plan"]["count"] == 0
    assert payload["relationship_issues"] == []


def test_trennen_und_wieder_verbinden_bleiben_bestaendig(client: TestClient) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    row_id = _activity(conn, "a", "2026-11-04")
    _event(conn, 501, "2026-11-04", name="Tempo Lauf")
    conn.close()

    context = client.get(f"/api/unit/{row_id}/plan-link").json()
    assert context["linked"]["plan_id"] == 501
    assert context["linked"]["source"] == "auto"
    assert context["candidates"] == []

    separated = client.delete(
        f"/api/unit/{row_id}/plan-link", params={"plan_id": 501}
    ).json()
    assert separated["linked"] is None
    assert len(separated["candidates"]) == 1
    assert separated["candidates"][0]["plan_id"] == 501
    assert separated["candidates"][0]["separated"] is True

    week = client.get("/api/planner", params={"week": "2026-11-02"}).json()
    assert _kinds(week) == ["recorded", "planned"]
    assert week["summary"]["open_plan"]["count"] == 1
    assert week["summary"]["recorded"]["count"] == 1

    linked = client.post(
        f"/api/unit/{row_id}/plan-link", json={"plan_id": 501}
    ).json()
    assert linked["linked"]["plan_id"] == 501
    assert linked["linked"]["source"] == "manual"
    assert linked["candidates"] == []

    week = client.get("/api/planner", params={"week": "2026-11-02"}).json()
    assert _kinds(week) == ["linked"]
    assert week["summary"]["open_plan"]["count"] == 0


def test_mehrere_kandidaten_werden_erst_manuell_verbunden(client: TestClient) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    first = _activity(conn, "a", "2026-11-04", minutes=60, start="07:00")
    second = _activity(conn, "b", "2026-11-04", minutes=30, start="17:00")
    _event(conn, 502, "2026-11-04", minutes=60, name="Lockerer Lauf")
    conn.close()

    week = client.get("/api/planner", params={"week": "2026-11-02"}).json()
    assert _kinds(week) == ["recorded", "recorded", "planned"]
    assert week["summary"]["recorded"]["count"] == 2
    assert week["summary"]["open_plan"]["count"] == 1

    context = client.get(f"/api/unit/{first}/plan-link").json()
    assert context["linked"] is None
    assert [candidate["plan_id"] for candidate in context["candidates"]] == [502]
    assert context["candidates"][0]["separated"] is False

    linked = client.post(
        f"/api/unit/{first}/plan-link", json={"plan_id": 502}
    ).json()
    assert linked["linked"]["source"] == "manual"

    week = client.get("/api/planner", params={"week": "2026-11-02"}).json()
    assert _kinds(week) == ["linked", "recorded"]
    assert week["summary"]["open_plan"]["count"] == 0
    assert week["summary"]["recorded"]["count"] == 2

    # Die Planung ist vergeben; für die zweite Aufzeichnung bleibt sie kein
    # Kandidat, und eine automatische Paarung entsteht nicht.
    second_context = client.get(f"/api/unit/{second}/plan-link").json()
    assert second_context["linked"] is None
    assert second_context["candidates"] == []


def test_ungueltige_und_kreuzwoche_verknuepfungen_werden_abgewiesen(
    client: TestClient,
) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    row_id = _activity(conn, "a", "2026-11-04")
    _event(conn, 501, "2026-11-04")
    _event(conn, 502, "2026-11-11")
    breath = _activity(conn, "b", "2026-11-04", sport="Workout")
    conn.close()

    assert (
        client.post(
            f"/api/unit/{row_id}/plan-link", json={"plan_id": 999999}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/unit/{row_id}/plan-link", json={"plan_id": 502}
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/api/unit/{breath}/plan-link", json={"plan_id": 501}
        ).status_code
        == 400
    )
    assert (
        client.post(f"/api/unit/{row_id}/plan-link", json={}).status_code == 400
    )
    assert client.get("/api/unit/999999/plan-link").status_code == 404


def test_ohne_planung_bleibt_die_einheit_ohne_zuordnung(client: TestClient) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    row_id = _activity(conn, "a", "2026-11-04")
    conn.close()

    context = client.get(f"/api/unit/{row_id}/plan-link").json()

    assert context["linked"] is None
    assert context["candidates"] == []
    assert context["plans_state"] == "empty"
