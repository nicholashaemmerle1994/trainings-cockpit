from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from planner_fixtures import load_case, load_remote

from trainings_cockpit import api, db

PROFILE = {
    "Run": {
        "max_hr": 190,
        "zones": [131, 155, 167, 176, 190],
    }
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


def _event() -> dict:
    path = load_case("F01")["remoteFixture"]
    return load_remote(str(path).rsplit("/", 1)[-1])["event"]


def _store(client: TestClient, event: dict, *, profile: dict | None = PROFILE) -> None:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.upsert_events(conn, [event])
    if profile is not None:
        db.set_setting(conn, "sport_profile", json.dumps(profile))
    conn.close()


def _detail(client: TestClient, event_id: int) -> dict:
    response = client.get(f"/api/planner/plan/{event_id}")
    assert response.status_code == 200
    return response.json()


def _buffer(node: dict, path: str, kind: str, raw: str) -> dict:
    return {
        "node_id": node["node_id"],
        "field_path": path,
        "kind": kind,
        "raw": raw,
    }


def test_detail_liefert_zonen_profil_und_getrennte_adapterfaehigkeit(
    client: TestClient,
) -> None:
    event = _event()
    _store(client, event)

    payload = _detail(client, event["id"])

    zones = payload["zone_options"]
    assert zones["available"] is True
    assert zones["zone_set_id"] == "run-hr"
    assert [zone["id"] for zone in zones["zones"]] == [
        "run-hr-1",
        "run-hr-2",
        "run-hr-3",
        "run-hr-4",
        "run-hr-5",
    ]
    assert zones["zones"][1]["label"] == "Zone 2"
    assert zones["zones"][1]["low"] == 131
    assert zones["zones"][1]["high"] == 155

    targets = payload["capabilities"]["targets"]
    assert targets["heartRateZone"]["local"] is True
    assert targets["heartRateZone"]["editable"] is True
    assert targets["heartRateBpm"]["local"] is True
    assert targets["heartRateBpm"]["editable"] is False
    assert targets["heartRateBpm"]["gate"] == "absolute_hr"
    assert payload["capabilities"]["write"]["available"] is False

    snapshot = payload["source_snapshot"]
    assert snapshot["remote_id"] == str(event["id"])
    assert snapshot["relevant_content_hash"].startswith("sha256:")
    assert snapshot["raw_workout_text"] == event["description"]


def test_entwurf_rechnet_1_5_km_zu_1500_m_und_aktualisiert_graph(
    client: TestClient,
) -> None:
    event = _event()
    _store(client, event)
    detail = _detail(client, event["id"])
    node = detail["nodes"][0]
    body = {
        "name": "Dauerlauf am Nachmittag",
        "nodes": [
            {
                **node,
                "name": "Einlaufen",
                "end": {"kind": "open"},
                "target": {
                    "kind": "zone",
                    "metric": "heartRate",
                    "zone_id": "run-hr-2",
                    "zone_set_id": "run-hr",
                },
            }
        ],
        "field_buffers": {
            f"{node['node_id']}:end.value": _buffer(
                node, "end.value", "distance", "1,5 km"
            ),
            f"{node['node_id']}:name": _buffer(node, "name", "text", "Einlaufen"),
        },
    }

    response = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)

    assert response.status_code == 200
    draft = response.json()
    assert draft["known"]["metres"] == 1500
    assert draft["known"]["text"] == "1,5 km"
    assert draft["graph"]["axis"]["mode"] == "distance"
    assert draft["nodes"][0]["name"] == "Einlaufen"
    assert draft["nodes"][0]["end"]["kind"] == "distance"
    assert draft["nodes"][0]["end"]["metres"] == 1500
    assert draft["draft"]["dirty"] is True
    assert draft["draft"]["valid"] is True
    assert draft["draft"]["field_states"][f"{node['node_id']}:end.value"]["parsed"] == 1500


def test_unfertiger_wert_bleibt_roh_und_oeffnet_das_ende(client: TestClient) -> None:
    event = _event()
    _store(client, event)
    detail = _detail(client, event["id"])
    node = detail["nodes"][0]
    body = {
        "name": detail["name"],
        "nodes": [{**node, "end": {"kind": "open"}}],
        "field_buffers": {
            f"{node['node_id']}:end.value": _buffer(
                node, "end.value", "duration", "5:"
            )
        },
    }

    response = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)

    assert response.status_code == 200
    draft = response.json()
    state = draft["draft"]["field_states"][f"{node['node_id']}:end.value"]
    assert state["validity"] == "invalid"
    assert state["message"]
    assert draft["known"]["has_unknown"] is True
    assert draft["graph"]["axis"]["mode"] == "schematic"
    assert draft["draft"]["valid"] is False
    assert "open_end" in {issue["code"] for issue in draft["draft"]["issues"]}


def test_gleicher_gueltiger_wert_ist_nicht_dirty(client: TestClient) -> None:
    event = _event()
    _store(client, event)
    detail = _detail(client, event["id"])
    node = detail["nodes"][0]
    body = {
        "name": detail["name"],
        "nodes": [node],
        "field_buffers": {
            f"{node['node_id']}:end.value": _buffer(node, "end.value", "duration", "45")
        },
    }

    response = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)

    assert response.status_code == 200
    draft = response.json()
    assert draft["draft"]["has_field_input"] is True
    assert draft["draft"]["dirty"] is False
    assert draft["draft"]["valid"] is True


def test_entwurf_schreibt_nichts_in_die_gespeicherte_basis(client: TestClient) -> None:
    event = _event()
    _store(client, event)
    detail = _detail(client, event["id"])
    node = detail["nodes"][0]
    body = {
        "name": "Nur lokal",
        "nodes": [{**node, "name": "Nur lokal"}],
        "field_buffers": {},
    }
    response = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)
    assert response.status_code == 200

    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    row = db.event_by_id(conn, event["id"])
    conn.close()
    assert row is not None
    assert json.loads(row["raw"]) == event
    assert _detail(client, event["id"])["name"] == event["name"]


def test_absolutes_bpm_ziel_bleibt_lesbar_aber_gesperrt(client: TestClient) -> None:
    event = {
        **_event(),
        "id": 9199,
        "workout_doc": {
            "steps": [
                {
                    "text": "Schwelle",
                    "duration": 600,
                    "hr": {"units": "bpm", "start": 170, "end": 175},
                }
            ]
        },
    }
    _store(client, event)

    detail = _detail(client, event["id"])

    node = detail["nodes"][0]
    assert node["kind"] == "unsupported"
    assert "HF-Ziel" in node["reason"] or "HF-Ziel" in node["label"]
    capability = detail["capabilities"]["targets"]["heartRateBpm"]
    assert capability["local"] is True
    assert capability["editable"] is False
    assert capability["synchronizable"] is False


def test_fremder_feldpuffer_wird_abgewiesen(client: TestClient) -> None:
    event = _event()
    _store(client, event)
    detail = _detail(client, event["id"])
    node = detail["nodes"][0]
    body = {
        "name": detail["name"],
        "nodes": [node],
        "field_buffers": {
            "node:fremd:end.value": _buffer(node, "end.value", "duration", "45")
        },
    }

    response = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)

    assert response.status_code == 422


def test_ohne_profil_werden_keine_zonen_erfunden(client: TestClient) -> None:
    event = _event()
    _store(client, event, profile=None)

    detail = _detail(client, event["id"])

    assert detail["zone_options"]["available"] is False
    assert detail["zone_options"]["zones"] == []
    assert detail["zone_options"]["max_hr"] is None


def test_unbekannte_zonenreferenz_bleibt_erhalten(client: TestClient) -> None:
    event = _event()
    _store(client, event)
    detail = _detail(client, event["id"])
    node = detail["nodes"][0]
    body = {
        "name": detail["name"],
        "nodes": [
            {
                **node,
                "target": {
                    "kind": "zone",
                    "metric": "heartRate",
                    "zone_id": "run-hr-99",
                    "zone_set_id": "run-hr",
                },
            }
        ],
        "field_buffers": {},
    }

    response = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)

    assert response.status_code == 200
    draft = response.json()
    assert draft["nodes"][0]["target"]["zone_id"] == "run-hr-99"
    assert draft["nodes"][0]["target"]["text"] == "Zone 99"
    assert "run-hr-99" not in {
        zone["id"] for zone in draft["zone_options"]["zones"]
    }
