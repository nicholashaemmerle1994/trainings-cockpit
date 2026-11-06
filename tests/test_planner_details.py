from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from planner_fixtures import load_case, load_remote

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


def _event(case_id: str) -> dict:
    path = load_case(case_id)["remoteFixture"]
    return load_remote(str(path).rsplit("/", 1)[-1])["event"]


def _store(client: TestClient, event: dict) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.upsert_events(conn, [event])
    conn.close()


def test_plan_detail_liefert_notizen_rechte_und_aufbau_ohne_schreiben(
    client: TestClient,
) -> None:
    event = _event("F07")
    _store(client, event)

    payload = client.get(f"/api/planner/plan/{event['id']}").json()

    assert payload["name"] == event["name"]
    assert payload["sport_label"] == "Rad"
    assert payload["notes"] == "Importierte Zusatznotiz, absichtlich nicht strukturiert."
    assert payload["rights"]["editability"] == "metadataOnly"
    assert payload["rights"]["can_edit_structure"] is False
    assert payload["rights"]["can_edit_metadata"] is True
    assert payload["rights"]["writes_on_open"] is False
    assert "unknown_content" in payload["rights"]["restriction_codes"]
    assert [node["kind"] for node in payload["nodes"]] == ["step", "unsupported", "unsupported"]
    assert payload["source"]["read_only"] is True

    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    row = db.event_by_id(conn, event["id"])
    conn.close()
    assert row is not None
    assert json.loads(row["raw"]) == event


def test_plan_detail_zeigt_sichere_bekannte_umfaenge(client: TestClient) -> None:
    event = _event("F04")
    _store(client, event)

    payload = client.get(f"/api/plan/{event['id']}").json()

    assert payload["known"]["seconds"] == 1680
    assert payload["known"]["metres"] == 4000
    assert payload["known"]["text"] == "28 min + 4 km"
    assert payload["known"]["executions"] == 10
    assert [node["kind"] for node in payload["nodes"]] == ["step", "repeat", "step"]
    assert payload["nodes"][1]["repetitions"] == 4


def test_plan_detail_404(client: TestClient) -> None:
    assert client.get("/api/planner/plan/424242").status_code == 404
    assert client.get("/api/plan/424242").status_code == 404
