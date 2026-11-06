from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from planner_fixtures import build_plan_from_case, load_case, load_remote

from trainings_cockpit import api, db
from trainings_cockpit.planner import (
    DistanceEnd,
    PlannedWorkout,
    RepeatNode,
    StepNode,
    StepRole,
    TimeEnd,
    ZoneMetric,
    ZoneTarget,
    build_workout_profile_data,
)
from trainings_cockpit.planner.remote import read_remote_event


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


def test_plan_detail_liefert_notizen_rechte_und_aufbau_ohne_schreiben(    client: TestClient,
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
    assert payload["graph"]["axis"]["mode"] == "schematic"

    settings = api.get_settings()
    conn = db.connect(settings.db_path)
    row = db.event_by_id(conn, event["id"])
    conn.close()
    assert row is not None
    assert json.loads(row["raw"]) == event


def test_f02_hat_getrennte_hf_und_pace_spuren(client: TestClient) -> None:
    event = _event("F02")
    _store(client, event)

    payload = client.get(f"/api/plan/{event['id']}").json()
    graph = payload["graph"]

    assert graph["axis"]["mode"] == "time"
    assert graph["axis"]["total_text"] == "36 min"
    assert graph["totals"]["total_executions"] == 10
    assert graph["totals"]["text"] == "36 min."
    assert [track["key"] for track in graph["tracks"]] == [
        "heartRate:zone",
        "pace:secondsPerKm",
    ]
    assert graph["tracks"][1]["direction"] == "faster-up"
    pace = graph["tracks"][1]
    assert pace["domain"]["max"] > pace["domain"]["min"]
    work = [segment for segment in graph["segments"] if segment["role"] == "work"]
    assert len(work) == 4
    assert all(segment["target_text"] == "Pace 5:30–5:45 min/km" for segment in work)
    assert all(
        segment["node_id"] == "node:event:9102:workout_doc-steps-1-steps-0"
        for segment in work
    )


def test_f04_und_f05_bleiben_schematisch_mit_getrennten_teilmengen(
    client: TestClient,
) -> None:
    event = _event("F04")
    _store(client, event)
    payload = client.get(f"/api/planner/plan/{event['id']}").json()
    graph = payload["graph"]
    assert graph["axis"]["mode"] == "schematic"
    assert graph["totals"]["text"] == "28 min + 4 km."
    assert "pace:secondsPerKm" in {track["key"] for track in graph["tracks"]}
    assert graph["segments"]
    for segment in graph["segments"]:
        assert 0 <= segment["start_fraction"] <= 1
        assert 0 <= segment["width_fraction"] <= 1

    f05 = build_workout_profile_data(build_plan_from_case(load_case("F05")))
    assert f05["axis"]["mode"] == "schematic"
    assert f05["totals"]["text"] == "800 m + 4 min."
    assert "pace:secondsPer100m" in {track["key"] for track in f05["tracks"]}
    assert f05["segments"]


def test_f03_hat_getrennte_hf_und_watt_spur() -> None:
    plan = build_plan_from_case(load_case("F03"))
    graph = build_workout_profile_data(plan)
    tracks = {track["key"]: track for track in graph["tracks"]}

    assert set(tracks) == {"heartRate:zone", "power:watts"}
    assert tracks["power:watts"]["domain"]["min"] >= 0
    assert "W" in tracks["power:watts"]["label"]
    assert "Herzfrequenz" in tracks["heartRate:zone"]["label"]
    assert graph["axis"]["total_text"] == "1 h 5 min"


def test_profil_komprimiert_grosse_wiederholung_ohne_summenaenderung() -> None:
    plan = PlannedWorkout(
        local_id="plan:event:test",
        name="Viele Wiederholungen",
        sport="Run",
        date="2026-11-02",
        time_zone="Europe/Vienna",
        nodes=(
            RepeatNode(
                id="node:test:repeat",
                name="Serie",
                repetitions=200,
                children=(
                    StepNode(
                        id="node:test:work",
                        name="Arbeit",
                        end=TimeEnd(120),
                        role=StepRole.WORK,
                        target=ZoneTarget(ZoneMetric.HEART_RATE, "run-hr-4"),
                    ),
                    StepNode(
                        id="node:test:recovery",
                        name="Erholung",
                        end=TimeEnd(60),
                        role=StepRole.RECOVERY,
                        target=ZoneTarget(ZoneMetric.HEART_RATE, "run-hr-1"),
                    ),
                ),
            ),
        ),
    )

    graph = build_workout_profile_data(plan, max_executions=7)

    assert graph["totals"]["seconds"] == 200 * (120 + 60)
    assert graph["totals"]["total_executions"] == 400
    assert graph["totals"]["compressed_executions"] > 0
    assert graph["compressions"]
    assert len(graph["segments"]) <= 10
    assert any(segment["kind"] == "compression" for segment in graph["segments"])
    assert graph["axis"]["total_text"] == "10 h"


def test_explizite_null_watt_bleibt_eigene_vorgabe() -> None:
    remote = read_remote_event(
        {
            "id": 9001,
            "category": "WORKOUT",
            "start_date_local": "2026-11-02T00:00:00",
            "type": "Ride",
            "name": "Nullwatt",
            "workout_doc": {
                "steps": [
                    {
                        "text": "Leerlauf",
                        "duration": 600,
                        "power": {"units": "watts", "start": 0, "end": 0},
                    }
                ]
            },
        },
        fetched_at="2026-11-02T10:00:00+01:00",
        time_zone="Europe/Vienna",
    )
    graph = build_workout_profile_data(remote.plan)
    segment = graph["segments"][0]

    assert segment["target"]["values"]["kind"] == "value"
    assert segment["target"]["values"]["value"] == 0
    assert segment["target_text"] == "Leistung 0 W"


def test_plan_detail_404(client: TestClient) -> None:
    assert client.get("/api/planner/plan/424242").status_code == 404
    assert client.get("/api/plan/424242").status_code == 404


def test_graph_bleibt_ohne_ziel_und_mit_einem_abschnitt_lesbar() -> None:
    plan = PlannedWorkout(
        local_id="plan:event:eins",
        name="Ein Abschnitt",
        sport="Run",
        date="2026-11-02",
        time_zone="Europe/Vienna",
        nodes=(
            StepNode(
                id="node:test:eins",
                name="Locker",
                end=DistanceEnd(1000),
                role=StepRole.STEADY,
            ),
        ),
    )
    graph = build_workout_profile_data(plan)

    assert graph["axis"]["mode"] == "distance"
    assert graph["totals"]["text"] == "1 km."
    assert graph["tracks"][0]["key"] == "none:none"
    assert graph["tracks"][0]["segments"][0]["target_text"] == "Ohne Ziel"
    assert graph["text_alternative"]
