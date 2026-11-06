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
    assert targets["heartRateZone"]["synchronizable"] is True
    assert targets["pace"]["synchronizable"] is True
    assert targets["powerWatts"]["synchronizable"] is True
    assert targets["powerPercentFtp"]["synchronizable"] is True
    assert targets["powerZone"]["synchronizable"] is False
    assert targets["heartRateBpm"]["local"] is True
    assert targets["heartRateBpm"]["editable"] is False
    assert targets["heartRateBpm"]["gate"] == "absolute_hr"
    assert payload["capabilities"]["write"]["available"] is True

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
                node, "end.value", "distance", "1,5"
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
    assert draft["nodes"][0]["target"]["text"] == "HF Zone 99"
    assert "run-hr-99" not in {
        zone["id"] for zone in draft["zone_options"]["zones"]
    }


def _event_for(case_id: str) -> dict:
    path = load_case(case_id)["remoteFixture"]
    return load_remote(str(path).rsplit("/", 1)[-1])["event"]


def _find_node(nodes: list[dict], **fields) -> dict | None:
    for node in nodes:
        if all(node.get(field) == value for field, value in fields.items()):
            return node
        if node.get("kind") == "repeat":
            found = _find_node(node.get("children") or [], **fields)
            if found:
                return found
    return None


def _target_buffer(
    node: dict,
    path: str,
    kind: str,
    raw: str,
    *,
    target_kind: str,
    unit: str | None = None,
) -> dict:
    return {
        **_buffer(node, path, kind, raw),
        "target_kind": target_kind,
        "unit": unit,
    }


def test_p13_pace_einzelwert_bereich_und_zieltext_aus_einer_quelle(
    client: TestClient,
) -> None:
    event = _event_for("F02")
    _store(client, event)
    detail = _detail(client, event["id"])
    work = _find_node(detail["nodes"], role="work")
    assert work is not None
    body = {
        "name": detail["name"],
        "nodes": detail["nodes"],
        "field_buffers": {
            f"{work['node_id']}:target.value": _target_buffer(
                work,
                "target.value",
                "pace",
                "5:20",
                target_kind="pace",
                unit="secondsPerKm",
            )
        },
    }

    single = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)
    assert single.status_code == 200
    single_draft = single.json()
    single_work = _find_node(single_draft["nodes"], role="work")
    assert single_work["target"]["kind"] == "pace"
    assert single_work["target"]["values"] == {
        "kind": "value",
        "value": 320.0,
    }
    assert single_work["target"]["text"] == "Pace 5:20 min/km"
    pace_segment = next(
        segment
        for segment in single_draft["graph"]["segments"]
        if segment["node_id"] == single_work["node_id"]
    )
    assert pace_segment["target_text"] == "Pace 5:20 min/km"

    body["field_buffers"] = {
        f"{work['node_id']}:target.min": _target_buffer(
            work, "target.min", "pace", "5:30", target_kind="pace", unit="secondsPerKm"
        ),
        f"{work['node_id']}:target.max": _target_buffer(
            work, "target.max", "pace", "5:45", target_kind="pace", unit="secondsPerKm"
        ),
    }
    ranged = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)
    assert ranged.status_code == 200
    ranged_work = _find_node(ranged.json()["nodes"], role="work")
    assert ranged_work["target"]["values"] == {
        "kind": "range",
        "min": 330.0,
        "max": 345.0,
    }
    assert ranged_work["target"]["text"] == "Pace 5:30–5:45 min/km"


def test_p13_watt_prozent_ftp_und_null_watt_bleiben_unterscheidbar(
    client: TestClient,
) -> None:
    event = _event()
    _store(client, event)
    detail = _detail(client, event["id"])
    node = detail["nodes"][0]

    def draft_for(path: str, kind: str, raw: str, target_kind: str, unit: str) -> dict:
        body = {
            "name": detail["name"],
            "nodes": [{**node, "target": {"kind": "none", "text": "Ohne Ziel"}}],
            "field_buffers": {
                f"{node['node_id']}:{path}": _target_buffer(
                    node, path, kind, raw, target_kind=target_kind, unit=unit
                )
            },
        }
        response = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)
        assert response.status_code == 200
        return response.json()["nodes"][0]["target"]

    watts = draft_for("target.value", "decimal", "0", "power", "watts")
    assert watts["kind"] == "power"
    assert watts["unit"] == "watts"
    assert watts["values"] == {"kind": "value", "value": 0.0}
    assert watts["text"] == "Leistung 0 W"

    ftp = draft_for("target.min", "decimal", "60", "power", "percentFtp")
    assert ftp["kind"] == "none"
    # Ein einzelner Bereichsrand bleibt unvollständig und erfindet keinen Wert.
    detail_body = {
        "name": detail["name"],
        "nodes": [{**node, "target": {"kind": "none", "text": "Ohne Ziel"}}],
        "field_buffers": {
            f"{node['node_id']}:target.min": _target_buffer(
                node, "target.min", "decimal", "60", target_kind="power", unit="percentFtp"
            ),
            f"{node['node_id']}:target.max": _target_buffer(
                node, "target.max", "decimal", "90", target_kind="power", unit="percentFtp"
            ),
        },
    }
    range_response = client.post(
        f"/api/planner/plan/{event['id']}/draft", json=detail_body
    )
    assert range_response.status_code == 200
    range_target = range_response.json()["nodes"][0]["target"]
    assert range_target["kind"] == "power"
    assert range_target["unit"] == "percentFtp"
    assert range_target["text"] == "Leistung 60–90 % FTP"


def test_p13_zielwechsel_uebernimmt_keine_zahlen_der_alten_einheit(
    client: TestClient,
) -> None:
    event = _event()
    _store(client, event)
    detail = _detail(client, event["id"])
    node = detail["nodes"][0]
    body = {
        "name": detail["name"],
        "nodes": [{**node, "target": {"kind": "none", "text": "Ohne Ziel"}}],
        "field_buffers": {
            f"{node['node_id']}:target.value": _target_buffer(
                node, "target.value", "decimal", "", target_kind="power", unit="watts"
            )
        },
    }

    response = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)

    assert response.status_code == 200
    draft = response.json()
    target = draft["nodes"][0]["target"]
    assert target == {"kind": "none", "text": "Ohne Ziel"}
    assert draft["draft"]["valid"] is False
    state = draft["draft"]["field_states"][f"{node['node_id']}:target.value"]
    assert state["validity"] == "incomplete"
    assert "fehlt" in state["message"].lower()


def test_p13_5_75_und_vertauschte_pacegrenzen_werden_erklaert(
    client: TestClient,
) -> None:
    event = _event()
    _store(client, event)
    detail = _detail(client, event["id"])
    node = detail["nodes"][0]
    body = {
        "name": detail["name"],
        "nodes": [{**node, "target": {"kind": "none", "text": "Ohne Ziel"}}],
        "field_buffers": {
            f"{node['node_id']}:target.value": _target_buffer(
                node, "target.value", "pace", "5:75", target_kind="pace",
                unit="secondsPerKm",
            )
        },
    }
    invalid = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)
    assert invalid.status_code == 200
    state = invalid.json()["draft"]["field_states"][f"{node['node_id']}:target.value"]
    assert state["validity"] == "invalid"
    assert "Sekunden" in state["message"]

    body["field_buffers"] = {
        f"{node['node_id']}:target.min": _target_buffer(
            node, "target.min", "pace", "5:45", target_kind="pace",
            unit="secondsPerKm",
        ),
        f"{node['node_id']}:target.max": _target_buffer(
            node, "target.max", "pace", "5:30", target_kind="pace",
            unit="secondsPerKm",
        ),
    }
    swapped = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)
    assert swapped.status_code == 200
    swapped_body = swapped.json()
    max_state = swapped_body["draft"]["field_states"][
        f"{node['node_id']}:target.max"
    ]
    assert max_state["validity"] == "invalid"
    assert "schnellere Pace" in max_state["message"]
    assert swapped_body["nodes"][0]["target"]["kind"] == "none"


def test_p13_leistungszonen_bleiben_hinter_der_faehigkeitsmatrix(
    client: TestClient,
) -> None:
    event = _event()
    _store(client, event)
    detail = _detail(client, event["id"])

    power_zone = detail["capabilities"]["targets"]["powerZone"]
    assert power_zone["local"] is False
    assert power_zone["editable"] is False
    assert power_zone["gate"] == "power_zone"
    assert "Fähigkeitsmatrix" in power_zone["reason"]
    assert detail["capabilities"]["targets"]["pace"]["editable"] is True
    assert detail["capabilities"]["targets"]["powerWatts"]["editable"] is True
    assert detail["capabilities"]["targets"]["powerPercentFtp"]["editable"] is True


def test_p14_entfernen_hinzufuegen_und_verschieben_bleiben_lokal(
    client: TestClient,
) -> None:
    event = _event_for("F02")
    _store(client, event)
    detail = _detail(client, event["id"])
    group = _find_node(detail["nodes"], kind="repeat")
    assert group is not None
    body = {
        "name": detail["name"],
        "nodes": [node for node in detail["nodes"] if node["node_id"] != group["node_id"]],
        "field_buffers": {},
    }

    removed = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)
    assert removed.status_code == 200
    removed_draft = removed.json()
    assert removed_draft["known"]["seconds"] == 1200
    assert removed_draft["known"]["executions"] == 2
    assert removed_draft["draft"]["valid"] is True
    assert [node["node_id"] for node in removed_draft["nodes"]] == [
        node["node_id"] for node in detail["nodes"] if node["node_id"] != group["node_id"]
    ]

    new_id = "node:draft:p14-new"
    body["nodes"] = [
        *removed_draft["nodes"],
        {
            "kind": "step",
            "node_id": new_id,
            "name": "Neuer Abschnitt",
            "role": "steady",
            "end": {"kind": "open", "text": "Ende offen"},
            "target": {"kind": "none", "text": "Ohne Ziel"},
        },
    ]
    added = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)
    assert added.status_code == 200
    added_draft = added.json()
    assert added_draft["nodes"][-1]["node_id"] == new_id
    assert "open_end" in {issue["code"] for issue in added_draft["draft"]["issues"]}
    assert added_draft["draft"]["valid"] is False

    body["nodes"] = []
    empty = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)
    assert empty.status_code == 200
    empty_draft = empty.json()
    assert empty_draft["nodes"] == []
    assert empty_draft["draft"]["valid"] is False
    assert "empty_workout" in {issue["code"] for issue in empty_draft["draft"]["issues"]}


def test_p14_verschieben_behaelt_alle_knoten_ids(client: TestClient) -> None:
    event = _event_for("F02")
    _store(client, event)
    detail = _detail(client, event["id"])
    reversed_ids = [node["node_id"] for node in reversed(detail["nodes"])]
    body = {
        "name": detail["name"],
        "nodes": list(reversed(detail["nodes"])),
        "field_buffers": {},
    }

    response = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)

    assert response.status_code == 200
    draft = response.json()
    assert [node["node_id"] for node in draft["nodes"]] == reversed_ids
    assert draft["known"]["seconds"] == 2160


def test_p15_f02_skip_und_drei_minuten_variante(client: TestClient) -> None:
    event = _event_for("F02")
    _store(client, event)
    detail = _detail(client, event["id"])
    group = _find_node(detail["nodes"], kind="repeat")
    work = _find_node(detail["nodes"], role="work")

    body = {
        "name": detail["name"],
        "nodes": [
            {**node, "skip_final_recovery": True}
            if node["node_id"] == group["node_id"]
            else node
            for node in detail["nodes"]
        ],
        "field_buffers": {},
    }
    skipped = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)
    assert skipped.status_code == 200
    skipped_draft = skipped.json()
    assert skipped_draft["known"]["seconds"] == 2040
    assert skipped_draft["known"]["executions"] == 9
    assert skipped_draft["draft"]["valid"] is True

    body["nodes"] = detail["nodes"]
    body["field_buffers"] = {
        f"{work['node_id']}:end.value": _buffer(
            work, "end.value", "duration", "3"
        )
    }
    three_minutes = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)
    assert three_minutes.status_code == 200
    three_draft = three_minutes.json()
    assert three_draft["known"]["seconds"] == 2400
    assert three_draft["known"]["executions"] == 10


def test_p15_gruppenname_und_wiederholungszahl_werden_bearbeitet(
    client: TestClient,
) -> None:
    event = _event_for("F02")
    _store(client, event)
    detail = _detail(client, event["id"])
    group = _find_node(detail["nodes"], kind="repeat")

    body = {
        "name": detail["name"],
        "nodes": detail["nodes"],
        "field_buffers": {
            f"{group['node_id']}:name": _buffer(group, "name", "text", "Serie"),
            f"{group['node_id']}:repetitions": _buffer(
                group, "repetitions", "integer", "5"
            ),
        },
    }
    response = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)

    assert response.status_code == 200
    draft = response.json()
    updated = _find_node(draft["nodes"], kind="repeat")
    assert updated["name"] == "Serie"
    assert updated["repetitions"] == 5
    assert draft["known"]["seconds"] == 2400
    assert draft["known"]["executions"] == 12


def test_p15_f06_drei_varianten_werden_im_entwurf_abgewiesen(
    client: TestClient,
) -> None:
    event = _event()
    _store(client, event)
    detail = _detail(client, event["id"])
    empty_repeat = {
        "kind": "repeat",
        "node_id": "node:f06-empty",
        "name": "Leere Gruppe",
        "repetitions": 3,
        "skip_final_recovery": False,
        "children": [],
    }
    only_recovery = {
        "kind": "repeat",
        "node_id": "node:f06-recovery",
        "name": "Nur Erholung",
        "repetitions": 1,
        "skip_final_recovery": True,
        "children": [
            {
                "kind": "step",
                "node_id": "node:f06-recovery-child",
                "name": "Erholung",
                "role": "recovery",
                "end": {"kind": "time", "seconds": 30},
                "target": {"kind": "none", "text": "Ohne Ziel"},
            }
        ],
    }
    variants = [
        ("keine Wurzelbausteine", []),
        ("Wiederholungsgruppe ohne Kinder", [empty_repeat]),
        ("nur ausgelassene Erholung", [only_recovery]),
    ]

    for label, nodes in variants:
        response = client.post(
            f"/api/planner/plan/{event['id']}/draft",
            json={"name": detail["name"], "nodes": nodes, "field_buffers": {}},
        )
        assert response.status_code == 200, label
        draft = response.json()
        assert draft["draft"]["valid"] is False, label
        codes = {issue["code"] for issue in draft["draft"]["issues"]}
        assert "no_executed_steps" in codes or "empty_workout" in codes, label
        assert draft["known"]["executions"] == 0, label


def test_p13_importierte_zusatzziele_bleiben_erhalten(client: TestClient) -> None:
    event = _event_for("F07")
    _store(client, event)
    detail = _detail(client, event["id"])
    body = {
        "name": detail["name"],
        "nodes": detail["nodes"],
        "field_buffers": {},
    }

    response = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)

    assert response.status_code == 200
    draft = response.json()
    assert [node["kind"] for node in draft["nodes"]] == ["step", "unsupported", "unsupported"]
    assert detail["source_snapshot"]["raw_workout_text"] == event["description"]
    assert draft["source_snapshot"]["raw_workout_text"] == event["description"]


def test_p15_ungueltige_und_zu_grosse_wiederholungszahl_blockieren(
    client: TestClient,
) -> None:
    event = _event_for("F02")
    _store(client, event)
    detail = _detail(client, event["id"])
    group = _find_node(detail["nodes"], kind="repeat")

    for raw, expected in [
        ("0", "mindestens 1"),
        ("2,5", "ganze Zahl"),
        ("9007199254740992", "höchstens"),
    ]:
        body = {
            "name": detail["name"],
            "nodes": detail["nodes"],
            "field_buffers": {
                f"{group['node_id']}:repetitions": _buffer(
                    group, "repetitions", "integer", raw
                )
            },
        }
        response = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)
        assert response.status_code == 200, raw
        state = response.json()["draft"]["field_states"][
            f"{group['node_id']}:repetitions"
        ]
        assert state["validity"] == "invalid", raw
        assert expected in state["message"], raw


def _new_body(**overrides) -> dict:
    body = {
        "draft_id": "draft:test-new-1",
        "sport": "Run",
        "date": "2026-11-11",
        "name": "",
        "template": "simple",
    }
    body.update(overrides)
    return body


def _event_count(client: TestClient) -> int:
    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    count = conn.execute("SELECT COUNT(*) FROM event").fetchone()[0]
    conn.close()
    return count


def test_neuer_entwurf_ist_lokal_und_hat_keine_remote_id(client: TestClient) -> None:
    _store(client, _event())
    before = _event_count(client)

    response = client.post("/api/planner/draft/new", json=_new_body())

    assert response.status_code == 200
    draft = response.json()
    assert draft["kind"] == "planned"
    assert draft["id"] is None
    assert draft["remote_id"] is None
    assert draft["local_id"] == "plan:draft:test-new-1"
    assert draft["source_snapshot"] is None
    assert draft["source"]["name"] == "Lokaler Entwurf"
    assert draft["source"]["read_only"] is False
    assert draft["name"] == "Dauerlauf"
    assert draft["date"] == "2026-11-11"
    assert draft["draft"]["is_new"] is True
    assert draft["draft"]["base_local_id"] is None
    assert draft["draft"]["remote_id"] is None
    assert draft["draft"]["valid"] is True
    assert draft["draft"]["write"]["available"] is True
    assert len(draft["nodes"]) == 1
    assert draft["nodes"][0]["end"] == {"kind": "time", "seconds": 2700, "text": "45 min"}
    assert draft["nodes"][0]["target"]["zone_id"] == "run-hr-2"
    assert _event_count(client) == before


def test_neuer_entwurf_ohne_profil_erfindet_keine_zone(client: TestClient) -> None:
    _store(client, _event(), profile=None)

    response = client.post("/api/planner/draft/new", json=_new_body())

    assert response.status_code == 200
    draft = response.json()
    assert draft["nodes"][0]["target"]["kind"] == "none"
    assert draft["zone_options"]["available"] is False


def test_neuer_wiederholungsentwurf_hat_vier_mal_zwei_minuten(client: TestClient) -> None:
    _store(client, _event())

    response = client.post(
        "/api/planner/draft/new",
        json=_new_body(
            draft_id="draft:test-new-repeat",
            name="Intervalle am Abend",
            template="repeat",
        ),
    )

    assert response.status_code == 200
    draft = response.json()
    assert draft["name"] == "Intervalle am Abend"
    assert draft["nodes"][0]["kind"] == "repeat"
    assert draft["nodes"][0]["repetitions"] == 4
    assert [child["role"] for child in draft["nodes"][0]["children"]] == [
        "work",
        "recovery",
    ]
    assert draft["known"]["seconds"] == 16 * 60
    assert draft["known"]["executions"] == 8


def test_leer_beginnen_liefert_leeren_lokalen_editor(client: TestClient) -> None:
    _store(client, _event())

    response = client.post(
        "/api/planner/draft/new",
        json=_new_body(draft_id="draft:test-new-empty", template="empty"),
    )

    assert response.status_code == 200
    draft = response.json()
    assert draft["nodes"] == []
    assert draft["name"] == "Neue Einheit"
    assert draft["draft"]["valid"] is False
    assert "empty_workout" in {issue["code"] for issue in draft["draft"]["issues"]}


def test_neuer_entwurf_lehnt_remote_id_und_ungueltige_sportart_ab(
    client: TestClient,
) -> None:
    _store(client, _event())
    before = _event_count(client)

    remote = client.post(
        "/api/planner/draft/new",
        json=_new_body(remote_id="9101"),
    )
    sport = client.post(
        "/api/planner/draft/new",
        json=_new_body(draft_id="draft:test-new-sport", sport="Golf"),
    )
    date = client.post(
        "/api/planner/draft/new",
        json=_new_body(draft_id="draft:test-new-date", date="11.11.2026"),
    )

    assert remote.status_code == 422
    assert sport.status_code == 422
    assert date.status_code == 422
    assert _event_count(client) == before


def test_name_und_termin_aendern_die_lokale_basis_nicht(client: TestClient) -> None:
    event = _event()
    _store(client, event)
    detail = _detail(client, event["id"])
    node = detail["nodes"][0]
    body = {
        "name": "Verschobener Dauerlauf",
        "date": "2026-11-05",
        "nodes": [node],
        "field_buffers": {},
    }

    response = client.post(f"/api/planner/plan/{event['id']}/draft", json=body)

    assert response.status_code == 200
    draft = response.json()
    assert draft["name"] == "Verschobener Dauerlauf"
    assert draft["date"] == "2026-11-05"
    assert draft["time"] is None
    assert draft["remote_id"] == str(event["id"])
    assert draft["source_snapshot"]["raw_workout_text"] == event["description"]
    assert _detail(client, event["id"])["name"] == event["name"]
