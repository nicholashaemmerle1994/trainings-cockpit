from __future__ import annotations

from datetime import date, timedelta

import pytest

from trainings_cockpit import metrics


def _wellness(days: int, end: date) -> list[dict]:
    rows = []
    for offset in range(days):
        day = end - timedelta(days=offset)
        rows.append(
            {
                "date": day.isoformat(),
                "hrv": 50.0,
                "rhr": 50.0,
                "sleep_s": 8 * 3600.0,
                "sleep_score": 80.0,
                "respiration": 13.0,
                "ctl": 50.0,
                "atl": 50.0,
            }
        )
    return rows


def test_daily_days_computes_ewma_when_intervals_values_missing() -> None:
    today = date(2026, 10, 30)
    activities = [
        {"date": (today - timedelta(days=1)).isoformat(), "load": 100.0},
        {"date": today.isoformat(), "load": 50.0},
    ]
    days = metrics.daily_days([], activities, today - timedelta(days=2), today)
    assert len(days) == 3
    assert days[-1].load == 50.0
    assert days[-1].ctl is not None and days[-1].ctl > 0
    assert days[-1].tsb == round(days[-1].ctl - days[-1].atl, 1)


def test_daily_days_filters_sentinel_values() -> None:
    today = date(2026, 10, 30)
    wellness = [
        {"date": today.isoformat(), "hrv": 255.0, "rhr": 500.0, "sleep_s": 60 * 3600.0}
    ]
    days = metrics.daily_days(wellness, [], today - timedelta(days=1), today)
    today_point = days[-1]
    assert today_point.hrv is None
    assert today_point.rhr is None
    assert today_point.sleep_h is None


def test_recovery_is_in_range_and_explained() -> None:
    today = date(2026, 10, 30)
    wellness = _wellness(90, today)
    days = metrics.daily_days(wellness, [], today - timedelta(days=89), today)
    recovery = metrics.compute_recovery(days, len(days) - 1)

    assert recovery["score"] is not None
    assert 0 <= recovery["score"] <= 100
    assert recovery["band"] in {"green", "amber", "orange", "red"}
    assert {component["key"] for component in recovery["components"]} == {
        "hrv",
        "rhr",
        "sleep",
        "resp",
    }
    assert recovery["confidence"] == 1.0
    assert recovery["explanation"]
    for component in recovery["components"]:
        assert component["today"] is not None
        assert component["average"] is not None
        assert component["baseline"] is not None


def test_recovery_uses_respiration_and_spo2_penalty() -> None:
    today = date(2026, 10, 30)
    rows = []
    for offset in range(70):
        day = today - timedelta(days=offset)
        rows.append(
            {
                "date": day.isoformat(),
                "hrv": 50.0,
                "rhr": 50.0,
                "sleep_s": 8 * 3600.0,
                "sleep_score": 80.0,
                "respiration": 14.0,
                "spo2": 99.0,
            }
        )
    rows[0].update({"respiration": 10.0, "spo2": 92.0})

    days = metrics.daily_days(rows, [], today - timedelta(days=69), today)
    recovery = metrics.compute_recovery(days, len(days) - 1)
    components = {component["key"]: component for component in recovery["components"]}

    assert "resp" in components
    assert components["resp"]["score"] > 68
    assert "spo2" in components
    assert components["spo2"]["score"] < 100

    rows[0]["spo2"] = 99.0
    days = metrics.daily_days(rows, [], today - timedelta(days=69), today)
    recovery = metrics.compute_recovery(days, len(days) - 1)
    assert "spo2" not in {component["key"] for component in recovery["components"]}


def test_recovery_without_data_returns_unknown() -> None:
    days = metrics.daily_days([], [], date(2026, 10, 29), date(2026, 10, 30))
    recovery = metrics.compute_recovery(days, len(days) - 1)
    assert recovery["score"] is None
    assert recovery["band"] == "unknown"


def test_week_summaries_aggregate_sports() -> None:
    activities = [
        {
            "date": "2026-10-27",
            "sport": "Run",
            "moving_s": 3600,
            "load": 50.0,
        },
        {
            "date": "2026-10-28",
            "sport": "Ride",
            "moving_s": 7200,
            "load": 80.0,
        },
    ]
    weeks = metrics.week_summaries([], activities, 4)
    assert len(weeks) == 1
    week = weeks[0]
    assert week["hours"] == 3.0
    assert week["load"] == 130.0
    assert week["sessions"] == 2
    assert week["by_sport"] == {"Run": 1.0, "Ride": 2.0}
    assert week["label"].startswith("KW ")


def test_activity_payload_formats_pace() -> None:
    payload = metrics.activity_payload(
        {
            "id": 7,
            "source_id": "i1",
            "date": "2026-10-27",
            "start_local": "2026-10-27T07:00:00",
            "sport": "Run",
            "name": "Test",
            "moving_s": 1800,
            "distance_m": 5000.0,
            "load": 40.0,
        }
    )
    assert payload["distance_km"] == 5.0
    assert payload["pace_min_km"] == 6.0
    assert payload["sport_label"] == "Laufen"


def test_ohne_nacht_von_heute_kein_rueckfall_auf_gestern() -> None:
    today = date(2026, 10, 31)
    wellness = _wellness(30, today - timedelta(days=1))
    days = metrics.daily_days(wellness, [], today - timedelta(days=120), today)

    recovery = metrics.compute_recovery(days, len(days) - 1)
    assert recovery["score"] is None
    assert recovery["label"] == "Keine Daten"
    assert recovery["components"] == []


def test_sleep_debt_ignores_missing_nights() -> None:
    day = metrics.Day(day=date(2026, 10, 31), load=0.0)
    night = metrics.Day(day=date(2026, 10, 30), load=0.0, sleep_h=7.0)

    assert metrics._sleep_debt([night, day]) == pytest.approx(0.5)


def test_build_weeks_summiert_nach_kalenderwoche(tmp_path) -> None:
    from trainings_cockpit import db

    conn = db.connect(tmp_path / "test.db")
    db.init_db(conn)
    db.upsert_activities(
        conn,
        [
            {
                "id": "a1",
                "start_date_local": "2026-10-28T07:00:00",
                "type": "Run",
                "name": "Lauf",
                "moving_time": 3600,
                "distance": 10000,
                "total_elevation_gain": 50,
            },
            {
                "id": "a2",
                "start_date_local": "2026-10-29T18:00:00",
                "type": "Ride",
                "name": "Rad",
                "moving_time": 7200,
                "distance": 40000,
            },
            {
                "id": "a3",
                "start_date_local": "2026-10-30T20:00:00",
                "type": "WeightTraining",
                "name": "Kraft",
                "moving_time": 1800,
            },
        ],
    )
    wochen = metrics.build_weeks(conn, weeks=1, today=date(2026, 10, 31))
    assert len(wochen) == 1
    woche = wochen[0]
    assert woche["lauf_km"] == 10.0
    assert woche["rad_km"] == 40.0
    assert woche["sonst_min"] == 30
    assert woche["einheiten"] == 3
    assert woche["langer_lauf_km"] == 10.0
    conn.close()


def test_ein_fehlendes_signal_ergibt_keinen_score() -> None:
    today = date(2026, 10, 30)
    wellness = _wellness(90, today)
    for row in wellness:
        if row["date"] == today.isoformat():
            row.pop("respiration")

    days = metrics.daily_days(wellness, [], today - timedelta(days=89), today)
    recovery = metrics.compute_recovery(days, len(days) - 1)

    assert recovery["score"] is None
    assert recovery["label"] == "Keine Daten"
    assert recovery["components"] == []
    assert "Atmung" in recovery["explanation"]


def test_neuer_sensor_wartet_auf_sieben_naechte() -> None:
    today = date(2026, 11, 9)
    wellness = _wellness(90, today)
    days = metrics.daily_days(wellness, [], today - timedelta(days=89), today)

    # Sensorwechsel vor drei Nächten: die Referenz ist noch nicht belastbar.
    epoch = today - timedelta(days=2)
    recovery = metrics.compute_recovery(days, len(days) - 1, epoch)

    assert recovery["score"] is None
    assert recovery["label"] == "Referenz wird aufgebaut"
    assert recovery["components"] == []
    assert recovery["reference"]["nights"] == 3
    assert recovery["reference"]["minimum"] == metrics.REFERENCE_MIN_NIGHTS
    assert "3 von 7" in recovery["explanation"]


def test_neuer_sensor_ignoriert_die_alte_referenz() -> None:
    today = date(2026, 11, 9)
    wellness = _wellness(90, today)
    # Die alte Zeit hat eine ganz andere HRV – sie darf die neue Referenz nicht prägen.
    for row in wellness:
        if row["date"] < (today - timedelta(days=10)).isoformat():
            row["hrv"] = 90.0

    days = metrics.daily_days(wellness, [], today - timedelta(days=89), today)
    epoch = today - timedelta(days=10)
    recovery = metrics.compute_recovery(days, len(days) - 1, epoch)

    hrv = next(c for c in recovery["components"] if c["key"] == "hrv")
    assert hrv["baseline"] == 50.0
    assert recovery["reference"]["nights"] >= metrics.REFERENCE_MIN_NIGHTS
    assert recovery["score"] is not None


def test_ohne_marke_gibt_es_keine_referenzangabe() -> None:
    today = date(2026, 10, 30)
    wellness = _wellness(90, today)
    days = metrics.daily_days(wellness, [], today - timedelta(days=89), today)

    recovery = metrics.compute_recovery(days, len(days) - 1)
    assert recovery["reference"] is None
    assert recovery["score"] is not None


def test_wochenumfang_zaehlt_sieben_tage_und_liefert_sekunden(tmp_path) -> None:
    today = date(2026, 11, 1)
    wellness = _wellness(10, today)
    def activity(day: date, name: str, moving: int, load: int) -> dict:
        # Felder wie sie intervals liefert — so, wie der Sync sie schreibt.
        return {
            "id": f"a-{name}",
            "start_date_local": f"{day.isoformat()}T08:00:00",
            "type": "Run",
            "moving_time": moving,
            "icu_training_load": load,
        }

    activities = [
        # heute und die sechs Tage davor zählen
        activity(today, "heute", 3600, 50),
        activity(today - timedelta(days=6), "vorwoche", 1800, 20),
        # der achte Tag zählt nicht mehr
        activity(today - timedelta(days=7), "alt", 7200, 90),
    ]
    from trainings_cockpit import db

    conn = db.connect(tmp_path / "week.db")
    try:
        db.init_db(conn)
        for row in wellness[-3:]:
            db.upsert_wellness(conn, [{**row, "id": row["date"]}])
        db.upsert_activities(conn, activities)
        overview = metrics.build_overview(conn, today=today)
    finally:
        conn.close()

    assert overview["today"]["load"]["week_seconds"] == 5400
    assert overview["today"]["load"]["week_sessions"] == 2
    assert overview["today"]["load"]["week_load"] == 70
