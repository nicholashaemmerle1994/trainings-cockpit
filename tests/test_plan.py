"""Tests für den Plan: Schritte, Schätzung, Verpflegung, Ist-Abgleich."""

from __future__ import annotations

import json
from datetime import date

import pytest

from trainings_cockpit import db, plan

SPEEDS = {"bike": 24.0, "run": 8.6, "swim": 2.6}


def make_event(
    steps: list[dict],
    *,
    sport: str = "Ride",
    day: str = "2026-11-01",
    distance: float | None = None,
    duration: int | None = None,
    load: float | None = 100.0,
) -> dict:
    raw = {"id": 7, "type": sport, "start_date_local": f"{day}T00:00:00", "workout_doc": {"steps": steps}}
    return {
        "id": 7,
        "date": day,
        "sport": sport,
        "name": "Test",
        "load": load,
        "duration_s": duration,
        "distance_m": distance,
        "intensity": 70.0,
        "raw": json.dumps(raw),
    }


def watts(low: int, high: int, minutes: int) -> dict:
    return {"power": {"start": low, "end": high, "units": "w"}, "duration": minutes * 60}


def test_dauer_ziel_schaetzt_die_distanz() -> None:
    event = make_event([watts(60, 100, 10), watts(120, 140, 50)])
    out = plan.planned(event, SPEEDS)

    assert out["primary"] == "duration"
    assert out["minutes"] == 60
    assert out["km"] == 24.0  # 60 min bei 24 km/h
    assert out["estimated"] == "distanz"


def test_distanz_ziel_schaetzt_die_dauer() -> None:
    event = make_event(
        [{"hr": {"units": "hr_zone", "value": 2}, "distance": 3000, "duration": 1213}],
        sport="Run",
        distance=3000.0,
    )
    out = plan.planned(event, SPEEDS)

    assert out["primary"] == "distance"
    assert out["km"] == 3.0
    assert out["minutes"] == 20  # 3 km bei 8,6 km/h, gerundet
    assert out["estimated"] == "dauer"


def test_wiederholungen_werden_ausgeklappt() -> None:
    steps = [
        watts(60, 100, 10),
        {
            "reps": 3,
            "text": "Hauptteil 3x",
            "steps": [watts(160, 170, 10), watts(90, 110, 5)],
        },
        watts(60, 100, 10),
    ]
    out = plan.planned(make_event(steps), SPEEDS)

    assert len(out["steps"]) == 8
    assert [s["label"] for s in out["steps"]][0] == "Aufwärmen"
    assert [s["label"] for s in out["steps"]][-1] == "Auslaufen"
    assert sum(1 for s in out["steps"] if s["work"]) == 3


def test_arbeit_ist_die_spitze_nicht_das_aufwaermen() -> None:
    steps = [watts(70, 75, 10), watts(75, 80, 30), watts(70, 75, 5)]
    out = plan.planned(make_event(steps, sport="Run"), SPEEDS)

    assert [s["work"] for s in out["steps"]] == [False, True, False]


def test_ohne_schritte_bleibt_die_achse_leer() -> None:
    event = {"id": 1, "date": "2026-11-01", "sport": "Ride", "load": 10, "duration_s": 3600, "distance_m": None, "intensity": None, "raw": None}
    out = plan.planned(event, SPEEDS)

    assert out["steps"] == []
    assert out["axis"] is None
    assert out["minutes"] == 60
    assert out["km"] == 24.0


def test_achse_hat_runde_marken() -> None:
    steps = [watts(60, 100, 10), watts(120, 140, 150), watts(60, 100, 5)]
    out = plan.planned(make_event(steps), SPEEDS)

    axis = out["axis"]
    assert axis is not None
    assert axis["unit"] == "W"
    assert 3 <= len(axis["ticks"]) <= 5
    assert axis["ticks"] == sorted(axis["ticks"])
    assert all(axis["from"] <= tick <= axis["to"] for tick in axis["ticks"])


def test_prozentziele_tragen_ihre_basis() -> None:
    steps = [{"power": {"start": 87, "end": 95, "units": "%ftp"}, "duration": 600}]
    out = plan.planned(make_event(steps), SPEEDS)

    assert out["axis"] is not None
    assert out["axis"]["unit"] == "% FTP"
    assert out["steps"][0]["target"] == "87–95 % FTP"


def test_herzfrequenzzone_wird_zur_spanne() -> None:
    event = make_event(
        [{"hr": {"units": "hr_zone", "value": 2}, "distance": 5000, "duration": 2000}],
        sport="Run",
        distance=5000.0,
    )
    out = plan.planned(event, SPEEDS)

    # Die Distanz steht in der eigenen Spalte, das Ziel nennt nur die Zone.
    assert out["steps"][0]["distance_km"] == 5.0
    assert out["steps"][0]["target"] == "Z2"
    assert out["steps"][0]["lo"] == 60
    assert out["steps"][0]["hi"] == 70


def test_pace_in_sekunden_wird_zu_min_pro_km_und_zaehlt_zur_distanz() -> None:
    event = make_event(
        [
            {
                "distance": 12000,
                "duration": 4860,
                "hr": {"units": "hr_zone", "value": 2},
            },
            {
                "distance": 5000,
                "duration": 1700,
                "pace": {"units": "secs", "start": 335, "end": 344},
            },
            {
                "distance": 1000,
                "duration": 400,
                "hr": {"units": "hr_zone", "value": 2},
            },
        ],
        sport="Run",
        distance=18000.0,
    )
    out = plan.planned(event, SPEEDS)

    assert out["km"] == 18.0
    assert out["steps"][1]["distance_km"] == 5.0
    assert out["steps"][1]["target"] == "5:35–5:44 min/km"
    # Die Achse läuft in HF-Prozent; ein Pace-Band gehört nicht hinein.
    assert out["steps"][1]["lo"] is None
    assert out["steps"][1]["hi"] is None


def test_pace_ohne_hf_bleibt_lesbar_ohne_gemeinsame_achse() -> None:
    event = make_event(
        [
            {
                "distance": 5000,
                "duration": 1700,
                "pace": {"units": "secs", "value": 335},
            }
        ],
        sport="Run",
        distance=5000.0,
    )
    out = plan.planned(event, SPEEDS)

    assert out["axis"] is None
    assert out["steps"][0]["target"] == "5:35 min/km"
    assert out["km"] == 5.0


PROFILE = {"max_hr": 190, "zones": [132, 155, 167, 174, 190], "ftp": 195, "indoor_ftp": 185}


def test_prozent_der_hf_werden_zu_schlaegen() -> None:
    event = make_event(
        [{"hr": {"start": 70, "end": 75, "units": "%hr"}, "duration": 600}],
        sport="Run",
    )
    out = plan.planned(event, SPEEDS, PROFILE)

    assert out["steps"][0]["target"] == "133–142 bpm"
    assert out["axis"] is not None
    assert out["axis"]["unit"] == "bpm"
    assert out["axis"]["from"] <= 133
    assert out["axis"]["to"] >= 142


def test_zone_wird_zu_ihren_grenzen_in_schlaegen() -> None:
    event = make_event(
        [{"hr": {"units": "hr_zone", "value": 2}, "distance": 3000, "duration": 1213}],
        sport="Run",
    )
    out = plan.planned(event, SPEEDS, PROFILE)

    assert out["steps"][0]["target"] == "132–155 bpm"
    assert out["steps"][0]["lo"] == 132
    assert out["steps"][0]["hi"] == 155


def test_prozent_der_schwelle_werden_zu_watt() -> None:
    event = make_event([{"power": {"start": 87, "end": 95, "units": "%ftp"}, "duration": 600}])
    out = plan.planned(event, SPEEDS, PROFILE)

    # 87 % und 95 % von 195 W
    assert out["steps"][0]["target"] == "170–185 W"
    assert out["steps"][0]["lo"] == 170
    assert out["steps"][0]["hi"] == 185
    assert out["axis"] is not None
    assert out["axis"]["unit"] == "W"


def test_drinnen_gilt_die_ftp_des_ergometers() -> None:
    event = make_event(
        [{"power": {"start": 90, "end": 100, "units": "%ftp"}, "duration": 600}],
        sport="VirtualRide",
    )
    out = plan.planned(event, SPEEDS, PROFILE)

    # 90 % und 100 % von 185 W (indoor_ftp); 166,5 rundet auf 166
    assert out["steps"][0]["target"] == "166–185 W"


def test_ohne_profil_bleibt_prozent_der_schwelle() -> None:
    event = make_event([{"power": {"start": 87, "end": 95, "units": "%ftp"}, "duration": 600}])
    out = plan.planned(event, SPEEDS)

    assert out["steps"][0]["target"] == "87–95 % FTP"
    assert out["axis"] is not None
    assert out["axis"]["unit"] == "% FTP"


def test_ohne_profil_bleibt_es_bei_prozent() -> None:
    event = make_event(
        [{"hr": {"start": 70, "end": 75, "units": "%hr"}, "duration": 600}],
        sport="Run",
    )
    out = plan.planned(event, SPEEDS)

    assert out["steps"][0]["target"] == "70–75 % HF"
    assert out["axis"] is not None
    assert out["axis"]["unit"] == "% HF"


def test_verpflegung_erst_ab_sechzig_minuten() -> None:
    assert plan.fuel_for(59) is None
    assert plan.fuel_for(60) is not None

    fuel = plan.fuel_for(165)
    assert fuel is not None
    assert fuel["carbs_g"] > 0
    assert fuel["rate"] > 0
    assert fuel["water_ml"] > 0


@pytest.mark.parametrize("sport,family", [("Ride", "bike"), ("VirtualRun", "run"), ("OpenWaterSwim", "swim")])
def test_sportarten_haben_eine_familie(sport: str, family: str) -> None:
    assert plan.sport_family(sport) == family


def test_ist_abgleich_findet_die_einheit_am_selben_tag(tmp_path) -> None:
    conn = db.connect(tmp_path / "plan.db")
    try:
        db.init_db(conn)
        db.upsert_activities(
            conn,
            [
                {
                    "id": "a1",
                    "start_date_local": "2026-11-01T08:05:00",
                    "type": "VirtualRide",
                    "moving_time": 9796,
                    "distance": 73652.0,
                    "icu_training_load": 154,
                    "icu_intensity": 75.1,
                }
            ],
        )
        event = make_event([watts(60, 100, 10), watts(120, 140, 150)], duration=9900)
        out = plan.session(conn, event, SPEEDS)
    finally:
        conn.close()

    assert out["actual"] is not None
    assert out["actual"]["minutes"] == 163
    assert out["actual"]["km"] == 73.7
    assert out["actual"]["intensity"] == 75


def test_session_row_ist_die_kurzfassung_fuer_die_karte(tmp_path) -> None:
    conn = db.connect(tmp_path / "row.db")
    try:
        db.init_db(conn)
        event = make_event([watts(60, 100, 10), watts(120, 140, 90)], duration=6000)
        out = plan.session_row(conn, event, SPEEDS)
    finally:
        conn.close()

    assert out["minutes"] == 100
    assert out["km"] == 40.0
    assert out["estimated"] == "distanz"
    assert out["primary"] == "duration"
    assert out["row_id"] is None
    assert out["done"] is False
    assert out["load"] == 100.0


def test_session_row_nennt_die_aufzeichnung_der_erledigten_einheit(tmp_path) -> None:
    conn = db.connect(tmp_path / "row-done.db")
    try:
        db.init_db(conn)
        db.upsert_activities(
            conn,
            [
                {
                    "id": "a1",
                    "start_date_local": "2026-11-01T08:00:00",
                    "type": "Ride",
                    "name": "Testfahrt",
                    "moving_time": 6000,
                    "distance": 40000,
                }
            ],
        )
        event = make_event([watts(60, 100, 10), watts(120, 140, 90)], duration=6000)
        out = plan.session_row(conn, event, SPEEDS)
        row = db.activities_between(
            conn, date.fromisoformat("2026-11-01"), date.fromisoformat("2026-11-01")
        )[0]
    finally:
        conn.close()

    assert out["done"] is True
    assert out["row_id"] == row["id"]


def test_speeds_nimmt_den_median_der_eigenen_fahrten(tmp_path) -> None:
    conn = db.connect(tmp_path / "speeds.db")
    try:
        db.init_db(conn)
        rows = [
            # drei Ausfahrten: 20, 24 und 28 km/h
            {"id": "r1", "start_date_local": "2026-10-21T08:00:00", "type": "Ride", "moving_time": 3600, "distance": 20000},
            {"id": "r2", "start_date_local": "2026-10-22T08:00:00", "type": "Ride", "moving_time": 3600, "distance": 24000},
            {"id": "r3", "start_date_local": "2026-10-23T08:00:00", "type": "Ride", "moving_time": 3600, "distance": 28000},
        ]
        db.upsert_activities(conn, rows)
        assert plan.speeds(conn, today=date(2026, 11, 1))["bike"] == 24.0
    finally:
        conn.close()
