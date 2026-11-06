"""P01: Fachliche Fixtures F01–F15 und Fähigkeitsmatrix.

Die Tests prüfen die Testdaten selbst: Vollständigkeit, reproduzierbare
Erwartungen, getrennte Sportprofile und die belegte Grenze des vorhandenen
Adapters. Sie brauchen weder UI noch Netzwerk und keine Produktivdaten.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest
from planner_fixtures import (
    FIXTURE_DIR,
    case_paths,
    load_case,
    load_cases,
    load_matrix,
    load_profiles,
    load_remote,
)

EXPECTED_CASES = {f"F{number:02d}" for number in range(1, 16)}
EXPECTED_REMOTE = {
    "simple-zone-run.json",
    "repeated-intervals.json",
    "distance-step.json",
    "unknown-content.json",
}


def _case(case_id: str) -> dict[str, Any]:
    return load_case(case_id)


def _activities_in(case: dict[str, Any], start: str, end: str) -> list[dict[str, Any]]:
    return [row for row in case["activities"] if start <= row["date"] <= end]


def _plans_in(case: dict[str, Any], start: str, end: str) -> list[dict[str, Any]]:
    return [row for row in case["plans"] if start <= row["date"] <= end]


def test_alle_faelle_f01_bis_f15_sind_vorhanden_und_eindeutig() -> None:
    cases = load_cases()
    ids = [case["case"] for case in cases]

    assert set(ids) == EXPECTED_CASES
    assert len(ids) == len(set(ids)) == 15
    assert [path.name for path in case_paths()] == sorted(path.name for path in case_paths())

    for case in cases:
        assert case["title"].strip()
        assert case["kind"].strip()
        assert isinstance(case["expected"], dict) and case["expected"]


def test_remote_beispiele_sind_vorhanden_und_anonymisiert() -> None:
    files = {path.name for path in (FIXTURE_DIR / "remote").glob("*.json")}
    assert EXPECTED_REMOTE <= files

    for name in EXPECTED_REMOTE:
        payload = load_remote(name)
        event = payload["event"]
        assert payload["kind"] == "remote-event"
        assert event["id"] > 0
        assert event["description"]
        assert event.get("external_id", "").startswith("fixture:")
        assert "workout_doc" in event

    simple = load_remote("simple-zone-run.json")["event"]
    assert simple["workout_doc"]["steps"][0]["hr"] == {"units": "hr_zone", "value": 2}
    assert simple["workout_doc"]["steps"][0]["duration"] == 45 * 60

    repeats = load_remote("repeated-intervals.json")["event"]
    repeat = repeats["workout_doc"]["steps"][1]
    assert repeat["reps"] == 4
    assert len(repeat["steps"]) == 2

    distance = load_remote("distance-step.json")["event"]
    step = distance["workout_doc"]["steps"][1]["steps"][0]
    assert step["distance"] == 1000
    assert step["duration_source"] == "estimated"
    assert step["pace"]["units"] == "min/km"


def test_unbekannter_import_bleibt_vollstaendig_im_remote_beispiel() -> None:
    event = load_remote("unknown-content.json")["event"]
    doc = event["workout_doc"]
    ramp = doc["steps"][1]

    assert ramp["ramp"] is True
    assert ramp["cadence"] == {"min": 85, "max": 95}
    assert ramp["targets"][0]["kind"] == "power"
    assert ramp["targets"][1]["kind"] == "cadence"
    assert doc["steps"][2]["lap_button"] is True
    assert doc["unknown_doc_field"] == {"keep": ["a", "b", 3]}
    assert event["weather"]["wind"] == "unbekannt"
    assert "Leerlauf" in event["description"]


def test_sportprofile_sind_separat_und_explizit() -> None:
    profiles = load_profiles()

    assert profiles["accountId"] == "fixture-account"
    assert profiles["athleteId"] == "fixture-athlete"
    assert profiles["timeZone"] == "Europe/Vienna"
    assert set(profiles["sports"]) == {"Run", "Ride", "Swim"}

    seen: set[tuple[str, str]] = set()
    for sport, profile in profiles["sports"].items():
        assert profile["profileId"]
        assert profile["maxHrBpm"] > 0
        for key in ("hrZoneSet", "paceZoneSet", "powerZoneSet"):
            zone_set = profile.get(key)
            if zone_set is None:
                continue
            assert isinstance(zone_set["id"], str) and zone_set["id"]
            assert zone_set["zones"]
            low_key = "minBpm" if key == "hrZoneSet" else (
                "minSeconds" if key == "paceZoneSet" else "minPercentFtp"
            )
            high_key = "maxBpm" if key == "hrZoneSet" else (
                "maxSeconds" if key == "paceZoneSet" else "maxPercentFtp"
            )
            for zone in zone_set["zones"]:
                assert isinstance(zone["id"], str) and zone["id"]
                assert zone[low_key] <= zone[high_key]
                assert (sport, zone["id"]) not in seen
                seen.add((sport, zone["id"]))

    assert profiles["sports"]["Ride"]["powerZoneSet"]["zones"][2]["id"] == "ride-power-sweetspot"
    assert not "ride-power-sweetspot".isdigit()


def test_zeit_dauer_und_distanz_sind_in_kanonischen_einheiten() -> None:
    for case_id in ("F01", "F02", "F03", "F04", "F05"):
        case = _case(case_id)
        nodes = case["plans"][0]["nodes"] if "plans" in case else case["plan"]["nodes"]
        for node in _walk(nodes):
            if node["kind"] != "step":
                continue
            end = node["end"]
            if end["kind"] == "time":
                assert isinstance(end["seconds"], int) and end["seconds"] > 0
            else:
                assert end["kind"] == "distance"
                assert isinstance(end["metres"], (int, float)) and end["metres"] > 0
            target = node.get("target", {"kind": "none"})
            if target["kind"] in {"heartRate", "power", "pace"}:
                assert target["values"]["kind"] in {"value", "range"}


def _walk(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for node in nodes:
        out.append(node)
        if node["kind"] == "repeat":
            out.extend(_walk(node["children"]))
    return out


def test_f01_bis_f07_tragen_ihre_fachlichen_erwartungen() -> None:
    expected_duration = {
        "F01": 2700,
        "F02": 2160,
        "F03": 3900,
        "F04": 1680,
        "F05": 240,
    }
    for case_id, seconds in expected_duration.items():
        case = _case(case_id)
        expected = case["expected"]
        key = "durationSeconds" if "durationSeconds" in expected else "knownDurationSeconds"
        assert expected[key] == seconds

    assert _case("F04")["expected"]["distanceMetres"] == 4000
    assert _case("F05")["expected"]["distanceMetres"] == 800
    assert _case("F05")["expected"]["paceUnit"] == "secondsPer100m"
    assert _case("F02")["expected"]["executedSteps"] == 10
    assert _case("F03")["expected"]["executedSteps"] == 8

    f06 = _case("F06")
    assert len(f06["plans"]) == 3
    assert f06["expected"]["executedStepsPerPlan"] == [0, 0, 0]

    f07 = _case("F07")
    assert f07["expected"]["unsupportedNodes"] == 2
    assert f07["expected"]["editability"] == "metadataOnly"
    assert f07["expected"]["mayEditStructure"] is False
    assert all(
        node.get("sourceRef")
        for node in _walk(f07["plan"]["nodes"])
        if node["kind"] == "unsupported"
    )


def test_f11_hat_getrennte_dashboard_und_planerzeitraeume() -> None:
    case = _case("F11")
    expected = case["expected"]
    dashboard = expected["dashboard"]
    planner = expected["planner"]

    dashboard_rows = _activities_in(case, dashboard["from"], dashboard["to"])
    planner_rows = _activities_in(case, planner["from"], planner["to"])
    planner_plans = _plans_in(case, planner["from"], planner["to"])

    assert sum(row["movingSeconds"] for row in dashboard_rows) == dashboard["seconds"] == 10800
    assert sum(row["movingSeconds"] for row in planner_rows) == planner["recordedSeconds"] == 6600
    assert sum(row["durationSeconds"] for row in planner_plans) == planner["openPlanSeconds"]
    assert dashboard["from"] != planner["from"]
    assert dashboard["volumeHasNoNavigation"] is True
    assert dashboard["volumeHasNoChevron"] is True
    assert dashboard["volumeHasNoKeyboardAction"] is True
    assert expected["entry"] == "planner-tab"
    assert expected["oldUrlCompatibility"] == "compatible-redirect"
    assert planner["openPlanSeparate"] is True


def test_f12_trennt_plan_und_aktivitaet_trotz_gleicher_numerischer_id() -> None:
    case = _case("F12")
    expected = case["expected"]
    p1, p2 = case["plans"]
    a1 = case["activities"][0]

    assert p1["remoteId"] == a1["activityId"] == expected["planId"] == expected["activityId"]
    assert expected["sameNumericIdDistinct"] is True
    assert expected["activityMinutes"] == a1["movingSeconds"] // 60 == 42
    assert expected["activityLoad"] == a1["load"] == 40
    assert expected["openPlanMinutes"] == p2["durationSeconds"] // 60 == 30
    assert expected["linkedEntries"] == 1
    assert expected["canonicalActivityCountedOnce"] is True

    canonical_sources = a1["sourceRefs"]
    assert len(canonical_sources) == 2
    assert len({(ref["source"], ref["sourceId"]) for ref in canonical_sources}) == 2

    relationship = case["relationships"][0]
    assert relationship["status"] == "confirmed"
    assert relationship["completionConfirmed"] is True
    assert relationship["activityIds"] == ["123"]

    variants = {variant["name"]: variant for variant in case["variants"]}
    multi = variants["mehrere Aufzeichnungen pro Plan"]
    assert len(multi["relationship"]["activityIds"]) == 2
    partial = variants["Beziehung ohne bestätigten Abschluss"]
    assert partial["relationship"]["completionConfirmed"] is False
    assert partial["expected"]["planRemainsOpen"] is True


def test_f13_haelt_plantag_und_aktivitaetstag_getrennt() -> None:
    case = _case("F13")
    plan = case["plans"][0]
    activity = case["activities"][0]
    expected = case["expected"]

    assert plan["date"] == "2026-11-08"
    assert activity["date"] == "2026-11-09"
    assert expected["planWeek"]["recordedSecondsAdded"] == 0
    assert expected["planWeek"]["planCountedAsOpen"] is False
    assert expected["activityWeek"]["planReachable"] is True
    assert expected["activityWeek"]["planDateStill"] == plan["date"]
    assert expected["nameMatchingNotUsed"] is True


def test_f14_unterscheidet_vollstaendig_leer_von_nicht_verfuegbar() -> None:
    case = _case("F14")
    weeks = case["weeks"]

    paginated = weeks[0]
    rows = [row for page in paginated["activityPages"] for row in page]
    assert len(paginated["activityPages"]) == 2
    assert len(rows) == paginated["expected"]["activityCount"] == 3
    assert paginated["activityFullyLoaded"] is True

    empty = weeks[1]
    assert empty["activityPages"] == [[]]
    assert empty["expected"]["state"] == "empty"
    assert empty["expected"]["activityCount"] == 0

    unavailable = weeks[2]
    assert unavailable["activitySourceAvailable"] is False
    assert unavailable["expected"]["activityCount"] is None
    assert unavailable["expected"]["mustNotShowZero"] is True

    plans_failed = weeks[3]
    assert plans_failed["activitySourceAvailable"] is True
    assert plans_failed["planSourceAvailable"] is False
    assert plans_failed["expected"]["state"] == "partial"

    activities_failed = weeks[4]
    assert activities_failed["activitySourceAvailable"] is False
    assert activities_failed["expected"]["planCount"] == 1

    stale = case["staleResponse"]["expected"]
    assert stale["currentWeekUnchanged"] is True
    assert stale["lateResponseDiscardedOrKeyed"] is True


def test_f15_bewahrt_bestehende_aktivitaetsdetails_und_sportarten() -> None:
    case = _case("F15")
    activities = case["activities"]
    expected = case["expected"]

    assert [row["sport"] for row in activities] == expected["sports"]
    assert "WeightTraining" in expected["sports"]
    assert expected["historyNotFilteredByCreateSports"] is True
    assert expected["withoutRelationshipNoArtificialPlanLink"] is True
    assert expected["planEditDoesNotWriteActivity"] is True

    for row in activities:
        assert row["rowId"] > 0
        assert row["activityId"]
        assert row["movingSeconds"] > 0
        for field in expected["fieldsPreserved"]:
            assert field in row
        if row["distanceMetres"] is not None:
            assert row["distanceMetres"] >= 0
        if row["hrZoneSeconds"]:
            assert len(row["hrZoneSeconds"]) == 5

    strength = next(row for row in activities if row["sport"] == "WeightTraining")
    assert strength["distanceMetres"] is None
    assert strength["elevationMetres"] is None


def test_faehigkeitsmatrix_ist_vollstaendig_und_nennt_fehlende_nachweise() -> None:
    matrix = load_matrix()
    statuses = set(matrix["statusValues"])
    capabilities = matrix["capabilities"]
    ids = [row["id"] for row in capabilities]

    assert statuses == {"belegt", "offen", "nicht unterstützt", "gesperrt"}
    assert len(ids) == 15
    assert len(ids) == len(set(ids))
    assert {row["label"] for row in capabilities} >= {
        "Zeitabschnitte",
        "Distanzabschnitte",
        "Einfache Wiederholungen",
        "HF-Standardzonen",
        "Absolute Pace und Pacebereich",
        "Watt und Wattbereich",
        "% FTP",
        "Leistungszonen",
        "Absolute bpm-Werte",
        "Benutzerdefinierte Zonen",
        "Mehrere Ziele in einem Schritt",
        "Rampen, Lap-Taste, Spezialschritte",
        "Verschachtelte Wiederholungen",
        "Globale Zielpriorität",
        "Letzte Erholung auslassen (als Gruppe)",
    }

    for row in capabilities:
        for column in ("read", "display", "edit", "write"):
            assert row[column] in statuses
        if row["write"] in {"offen", "gesperrt"}:
            assert row["missingProof"].strip(), row["id"]

    supported_writes = {
        "time",
        "distance",
        "simple-repeat",
        "hr-standard-zone",
        "absolute-pace",
        "watts",
        "percent-ftp",
    }
    assert {
        row["id"] for row in capabilities if row["write"] == "belegt"
    } == supported_writes

    blocked_writes = {
        "power-zones",
        "absolute-bpm",
        "custom-zones",
        "nested-repeats",
        "global-target-priority",
        "skip-final-recovery",
    }
    assert {
        row["id"] for row in capabilities if row["write"] == "gesperrt"
    } == blocked_writes
    assert {
        row["id"] for row in capabilities if row["write"] == "nicht unterstützt"
    } == {"multiple-targets", "ramps-lap-special"}

    findings = {row["id"] for row in matrix["adapterFindings"]}
    assert {
        "read-event",
        "read-workout-doc",
        "write-product-path",
        "live-write-proof",
        "relationship",
    } <= findings
    assert "kein Live-Schreibzugriff" in matrix["writeScope"]
    assert "nicht ausgeführt" in matrix["liveProof"]
    assert matrix["observedAt"] == "2026-11-06"


def test_fixtures_sind_reproduzierbar_und_enthalten_keine_zugangsdaten() -> None:
    forbidden = ("INTERVALS_API_KEY", "GARMIN_PERSONAL_API_KEY", "Bearer ", "api_key")
    for path in sorted(FIXTURE_DIR.rglob("*.json")):
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{marker} in {path.name}"

    for case in load_cases():
        for key in ("today", "date", "from", "to"):
            value = case.get(key)
            if isinstance(value, str):
                date.fromisoformat(value)

    # Kein Fixture hängt an zufälligen aktuellen Trainingsdaten.
    for case in load_cases():
        assert "date.today" not in json.dumps(case)


@pytest.mark.parametrize("case_id", sorted(EXPECTED_CASES))
def test_jeder_fall_ist_lesbar_und_hat_eine_feste_id(case_id: str) -> None:
    case = _case(case_id)
    assert case["case"] == case_id
    assert case_id in json.dumps(case, ensure_ascii=False)
