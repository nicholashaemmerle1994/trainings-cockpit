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
                "sleep_awake_s": 20 * 60.0,
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


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (100, "green-top"),
        (85, "green-top"),
        (84, "green"),
        (70, "green"),
        (69, "amber"),
        (55, "amber"),
        (54, "orange"),
        (40, "orange"),
        (39, "red"),
        (0, "red"),
    ],
)
def test_band_boundaries(score: float, band: str) -> None:
    assert metrics._band(score)[0] == band


def test_green_top_sentence() -> None:
    assert metrics.BAND_SENTENCES["green-top"] == "Du bist heute sehr gut erholt."


def test_band_uses_displayed_score() -> None:
    # Der Ring zeigt ganze Zahlen; ein Rohwert knapp unter 85 darf nicht als
    # „85" mit dem Band „Gut erholt" erscheinen.
    assert metrics._score_band(84.4) == (84, "green", "Gut erholt")
    assert metrics._score_band(84.6) == (85, "green-top", "Sehr gut erholt")
    assert metrics._score_band(85.4) == (85, "green-top", "Sehr gut erholt")
    assert metrics._score_band(69.5) == (70, "green", "Gut erholt")


def test_recovery_score_and_band_agree_with_the_displayed_number() -> None:
    # Der Ring zeigt ganze Zahlen; das Band wird aus derselben Zahl gebildet
    # (D-62). Den Grenzfall 84,4/84,6 deckt `_score_band` ab.
    today = date(2026, 10, 30)
    wellness = _wellness(90, today)
    days = metrics.daily_days(wellness, [], today - timedelta(days=89), today)
    recovery = metrics.compute_recovery(days, len(days) - 1, epoch=today - timedelta(days=100))

    assert recovery["score"] is not None
    assert recovery["band"] == metrics._band(recovery["score"])[0]


def test_recovery_is_in_range_and_explained() -> None:
    today = date(2026, 10, 30)
    wellness = _wellness(90, today)
    days = metrics.daily_days(wellness, [], today - timedelta(days=89), today)
    recovery = metrics.compute_recovery(days, len(days) - 1)

    assert recovery["score"] is not None
    assert 0 <= recovery["score"] <= 100
    assert recovery["band"] in {"green-top", "green", "amber", "orange", "red"}
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


def test_recovery_uses_respiration_but_not_spo2() -> None:
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
                "sleep_awake_s": 20 * 60.0,
                "respiration": 14.0,
                "spo2": 99.0,
            }
        )
    rows[0].update({"respiration": 10.0, "spo2": 92.0})

    days = metrics.daily_days(rows, [], today - timedelta(days=69), today)
    recovery = metrics.compute_recovery(days, len(days) - 1)
    components = {component["key"]: component for component in recovery["components"]}

    assert "resp" in components
    # Niedrigere Atmung ist besser und liegt klar unter dem Üblichen.
    assert components["resp"]["score"] > 80
    # SpO2 ist seit v2 kein Bestandteil des Scores mehr (D-89).
    assert "spo2" not in components
    assert {component["weight"] for component in recovery["components"]} == {
        35.0,
        25.0,
        30.0,
        10.0,
    }


def test_recovery_without_data_returns_unknown() -> None:
    days = metrics.daily_days([], [], date(2026, 10, 29), date(2026, 10, 30))
    recovery = metrics.compute_recovery(days, len(days) - 1)
    assert recovery["score"] is None
    assert recovery["band"] == "unknown"
    assert recovery["label"] == "Referenz wird aufgebaut"
    assert recovery["reference"]["nights"] == 0


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


def test_fehlende_heutige_nacht_ergibt_keinen_wert() -> None:
    """Kein Wert von gestern: fehlt die heutige Nacht, gibt es keinen Score (D-26)."""
    today = date(2026, 10, 31)
    wellness = _wellness(30, today - timedelta(days=1))
    days = metrics.daily_days(wellness, [], today - timedelta(days=120), today)

    recovery = metrics.compute_recovery(days, len(days) - 1)
    assert recovery["score"] is None
    assert recovery["label"] == "Keine Daten"
    assert recovery["date"] is None
    assert recovery["components"] == []
    assert "die HRV" in recovery["explanation"]


def test_unvollstaendige_heutige_nacht_ergibt_keinen_wert() -> None:
    """Auch eine halbe heutige Nacht wird nicht mit gestern aufgefüllt (D-26)."""
    today = date(2026, 10, 31)
    wellness = _wellness(30, today)
    wellness[0].pop("respiration")
    wellness[0]["hrv"] = 99.0
    days = metrics.daily_days(wellness, [], today - timedelta(days=120), today)

    recovery = metrics.compute_recovery(days, len(days) - 1)
    assert recovery["score"] is None
    assert recovery["label"] == "Keine Daten"
    assert recovery["date"] is None
    assert recovery["components"] == []
    assert "Atmung" in recovery["explanation"]


def test_alte_vollstaendige_nacht_ist_kein_aktueller_wert() -> None:
    """Auch eine alte vollständige Nacht ersetzt die heutige nicht."""
    today = date(2026, 11, 10)
    old = today - timedelta(days=40)
    wellness = _wellness(40, old)
    # Heute und gestern haben nur die HRV, keine vollständige Nacht.
    wellness.append({"date": today.isoformat(), "hrv": 50.0})
    wellness.append({"date": (today - timedelta(days=1)).isoformat(), "hrv": 50.0})

    days = metrics.daily_days(wellness, [], today - timedelta(days=120), today)
    recovery = metrics.compute_recovery(days, len(days) - 1)

    assert recovery["score"] is None
    assert recovery["label"] == "Keine Daten"
    assert recovery["date"] is None
    assert "der Ruhepuls" in recovery["explanation"]


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
    # Keine vollständige Nacht im Fenster: kein Wert, auch nicht aus den
    # vorhandenen Signalen (D-26).
    for row in wellness:
        row.pop("respiration")

    days = metrics.daily_days(wellness, [], today - timedelta(days=89), today)
    recovery = metrics.compute_recovery(days, len(days) - 1)

    assert recovery["score"] is None
    assert recovery["label"] == "Keine Daten"
    assert recovery["components"] == []
    assert "Atmung" in recovery["explanation"]


def test_neuer_sensor_wartet_auf_die_fuenf_naechte() -> None:
    """Der erste Wert kommt ab fünf gültigen Nächten (D-89)."""
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
    assert recovery["reference"]["target"] == 60
    assert metrics.REFERENCE_MIN_NIGHTS == 5
    assert "3 von 5" in recovery["explanation"]


def test_neuer_sensor_ignoriert_die_alte_referenz() -> None:
    today = date(2026, 11, 9)
    wellness = _wellness(90, today)
    # Die alte Zeit hat eine ganz andere HRV – sie darf die neue Referenz nicht prägen.
    epoch = today - timedelta(days=metrics.REFERENCE_DAYS)
    for row in wellness:
        if row["date"] < epoch.isoformat():
            row["hrv"] = 90.0

    days = metrics.daily_days(wellness, [], today - timedelta(days=89), today)
    recovery = metrics.compute_recovery(days, len(days) - 1, epoch)

    hrv = next(c for c in recovery["components"] if c["key"] == "hrv")
    assert hrv["baseline"] == 50.0
    assert recovery["reference"]["nights"] >= metrics.REFERENCE_MIN_NIGHTS
    assert recovery["score"] is not None


def test_referenz_ist_immer_das_60_tage_fenster() -> None:
    today = date(2026, 10, 30)
    wellness = _wellness(90, today)
    days = metrics.daily_days(wellness, [], today - timedelta(days=89), today)

    recovery = metrics.compute_recovery(days, len(days) - 1)
    assert recovery["reference"]["nights"] == 60
    assert recovery["reference"]["minimum"] == 5
    assert recovery["reference"]["target"] == 60
    assert recovery["reference"]["days"] == 60
    assert recovery["score"] is not None


def test_teilnacht_heute_ergibt_keinen_wert() -> None:
    """Eine halb synchrone heutige Nacht ist kein Score, auch mit voller Historie."""
    today = date(2026, 11, 10)
    wellness = _wellness(6, today - timedelta(days=1))
    wellness.append({"date": today.isoformat(), "hrv": 99.0})
    days = metrics.daily_days(wellness, [], today - timedelta(days=70), today)

    recovery = metrics.compute_recovery(days, len(days) - 1)

    assert recovery["score"] is None
    assert recovery["date"] is None
    # Die Nacht zählt als vorhandenes Signal in die Referenz, aber nicht als Score.
    assert recovery["reference"]["nights"] == 7


def test_teilnacht_heute_erfuellt_das_minimum_nicht_als_score() -> None:
    """Fünf Nächte mit Signal ergeben keinen Score, wenn heute unvollständig ist."""
    today = date(2026, 11, 10)
    wellness = _wellness(4, today - timedelta(days=1))
    wellness.append({"date": today.isoformat(), "hrv": 99.0})
    days = metrics.daily_days(wellness, [], today - timedelta(days=70), today)

    recovery = metrics.compute_recovery(days, len(days) - 1)

    assert recovery["label"] == "Keine Daten"
    assert recovery["reference"]["nights"] == 5
    assert recovery["score"] is None
    assert "der Ruhepuls" in recovery["explanation"]


def _vorschau_naechte(mit_atmung: bool = True) -> list[dict]:
    """Die sechs echten Nächte 4.–9.11.2026 aus der Vorschau.

    HRV, Ruhepuls und Schlafdauer sind die Werte aus `/api/overview` der
    Vorschau. Atmung und Wachheit waren über die API im Container nicht
    lesbar (kein Garmin-Key); 14,0/min und 20 Minuten wach sind Testwerte,
    die nur die Pflichtschwelle erfüllen. Die echten Werte bestätigt der
    erste Sync mit Key (offener Punkt in D-89).
    """
    hrv = [28, 29, 31, 29, 21, 32]
    rhr = [58, 56, 57, 56, 59, 55]
    schlaf = [7 + 15 / 60, 6 + 50 / 60, 7 + 51 / 60, 7 + 45 / 60, 8 + 2 / 60, 7 + 23 / 60]
    rows = []
    for index in range(6):
        day = date(2026, 11, 4) + timedelta(days=index)
        row = {
            "date": day.isoformat(),
            "hrv": hrv[index],
            "rhr": rhr[index],
            "sleep_s": schlaf[index] * 3600,
            "sleep_awake_s": 20 * 60,
        }
        if mit_atmung:
            row["respiration"] = 14.0
        rows.append(row)
    return rows


def test_sechs_vorschau_naechte_golden_mit_testatmung() -> None:
    end = date(2026, 11, 9)
    days = metrics.daily_days(_vorschau_naechte(), [], date(2026, 9, 1), end)
    recovery = metrics.compute_recovery(days, len(days) - 1)

    assert recovery["score"] == 93
    assert recovery["band"] == "green-top"
    assert recovery["label"] == "Sehr gut erholt"
    assert recovery["date"] == "2026-11-09"
    assert recovery["reference"] == {
        "nights": 6,
        "minimum": 5,
        "target": 60,
        "days": 60,
        "average": None,
    }
    components = {component["key"]: component for component in recovery["components"]}
    assert components["hrv"]["today"] == 32
    assert components["hrv"]["baseline"] == 29.0
    assert components["rhr"]["today"] == 55
    assert components["rhr"]["baseline"] == 56.5
    assert components["sleep"]["today"] == 7.38
    assert components["resp"]["today"] == 14.0
    assert recovery["triggeredRules"] == []
    assert recovery["adjustment"] == 0


def test_vorschau_naechte_ohne_atmung_ergeben_keinen_wert() -> None:
    end = date(2026, 11, 9)
    days = metrics.daily_days(_vorschau_naechte(mit_atmung=False), [], date(2026, 9, 1), end)
    recovery = metrics.compute_recovery(days, len(days) - 1)

    assert recovery["score"] is None
    assert recovery["label"] == "Keine Daten"
    assert recovery["components"] == []
    assert "Atmung" in recovery["explanation"]


def test_fuenf_naechte_ergeben_schon_einen_wert() -> None:
    today = date(2026, 11, 9)
    days = metrics.daily_days(_wellness(5, today), [], today - timedelta(days=10), today)
    recovery = metrics.compute_recovery(days, len(days) - 1)

    assert recovery["reference"]["nights"] == 5
    assert recovery["score"] is not None


def test_vier_naechte_ergeben_noch_keinen_wert() -> None:
    today = date(2026, 11, 9)
    days = metrics.daily_days(_wellness(4, today), [], today - timedelta(days=10), today)
    recovery = metrics.compute_recovery(days, len(days) - 1)

    assert recovery["reference"]["nights"] == 4
    assert recovery["score"] is None
    assert recovery["label"] == "Referenz wird aufgebaut"


def test_mindeststreuung_verhindert_division_durch_null() -> None:
    today = date(2026, 11, 9)
    # Alle Nächte exakt gleich: die MAD ist null, der z-Score bleibt endlich.
    days = metrics.daily_days(_wellness(30, today), [], today - timedelta(days=40), today)
    recovery = metrics.compute_recovery(days, len(days) - 1)

    assert recovery["score"] is not None
    for component in recovery["components"]:
        if component["key"] != "sleep":
            assert component["z"] is not None


def test_mapping_ist_unter_dem_ueblichen_steiler() -> None:
    baseline = [50.0] * 5
    below = metrics._component(
        key="hrv",
        label="HRV",
        unit="ms",
        today=49.0,
        values=[49.0],
        baseline=baseline,
        invert=False,
        weight=35,
    )
    above = metrics._component(
        key="hrv",
        label="HRV",
        unit="ms",
        today=51.0,
        values=[51.0],
        baseline=baseline,
        invert=False,
        weight=35,
    )
    assert below["score"] == 64  # 80 − 16·1
    assert above["score"] == 90  # 80 + 10·1


def test_schlafscore_mit_phasen_60_25_15() -> None:
    day = metrics.Day(
        day=date(2026, 11, 9),
        sleep_h=8.0,
        sleep_awake_h=0.1,
        sleep_deep_h=0.8,
        sleep_rem_h=1.2,
    )
    with_phases = metrics._sleep_component(day, [day])
    without_phases = metrics._sleep_component(
        metrics.Day(day=day.day, sleep_h=8.0, sleep_awake_h=0.1), [day]
    )

    # 60/25/15: Dauer 100, Wachheit 100, Phasen ~62 → 94. Ohne Phasen 100.
    assert with_phases["duration_score"] == 100
    assert with_phases["wake_score"] == 100
    assert with_phases["phase_score"] == 62
    assert with_phases["score"] == 94
    assert without_phases["phase_score"] is None
    assert without_phases["score"] == 100


def test_schlafziel_fallback() -> None:
    assert metrics._sleep_target(metrics.Day(day=date(2026, 11, 9))) == 7.5
    assert (
        metrics._sleep_target(metrics.Day(day=date(2026, 11, 9), sleep_goal_h=7.2)) == 7.2
    )
    assert (
        metrics._sleep_target(
            metrics.Day(day=date(2026, 11, 9), sleep_need_h=8.0, sleep_goal_h=7.2)
        )
        == 8.0
    )
    # Sleep Need unter 7:00 wird auf 7:00 angehoben.
    assert metrics._sleep_target(metrics.Day(day=date(2026, 11, 9), sleep_need_h=6.4)) == 7.0


def test_schlafziel_ist_nicht_der_median_der_tatsaechlichen_dauer() -> None:
    today = date(2026, 11, 9)
    rows = []
    for offset in range(30):
        day = today - timedelta(days=offset)
        rows.append(
            {
                "date": day.isoformat(),
                "hrv": 50.0,
                "rhr": 50.0,
                "sleep_s": 6 * 3600.0,
                "sleep_awake_s": 10 * 60.0,
                "respiration": 13.0,
            }
        )
    days = metrics.daily_days(rows, [], today - timedelta(days=40), today)
    recovery = metrics.compute_recovery(days, len(days) - 1)
    sleep = next(c for c in recovery["components"] if c["key"] == "sleep")

    assert sleep["baseline"] == 7.5
    assert sleep["score"] < 100


def test_garmin_sleep_score_fliesst_nicht_ein() -> None:
    today = date(2026, 11, 9)
    rows = _wellness(30, today)
    rows[0]["sleep_score"] = 10
    days = metrics.daily_days(rows, [], today - timedelta(days=40), today)
    low = metrics.compute_recovery(days, len(days) - 1)

    rows[0]["sleep_score"] = 100
    days = metrics.daily_days(rows, [], today - timedelta(days=40), today)
    high = metrics.compute_recovery(days, len(days) - 1)

    assert low["components"] == high["components"]


def _rule_component(key: str, score: int, today: float, baseline: float) -> dict:
    return {"key": key, "score": score, "today": today, "baseline": baseline}


def test_warnregeln_loesen_mit_den_festen_schwellen_aus() -> None:
    hrv = _rule_component("hrv", 45, 80.0, 100.0)  # −20 %
    rhr = _rule_component("rhr", 45, 60.0, 50.0)  # +10 bpm
    sleep = _rule_component("sleep", 50, 6.0, 7.5)
    rules, total = metrics._warning_rules([hrv, rhr, sleep])
    assert [rule["id"] for rule in rules] == ["hrv_rhr", "hrv_sleep", "rhr_sleep", "triple_low"]
    assert total == -31
    assert metrics._capped_adjustment(total) == -15

    # Genau an der Schwelle: −10 % und +5 bpm lösen aus.
    rules, total = metrics._warning_rules(
        [
            _rule_component("hrv", 60, 90.0, 100.0),
            _rule_component("rhr", 60, 55.0, 50.0),
            _rule_component("sleep", 70, 7.0, 7.5),
        ]
    )
    assert [rule["id"] for rule in rules] == ["hrv_rhr"]
    assert total == -10
    assert metrics._capped_adjustment(total) == -10


def test_warnregeln_bleiben_unter_der_schwelle_stumm() -> None:
    rules, total = metrics._warning_rules(
        [
            _rule_component("hrv", 69, 95.0, 100.0),  # −5 %
            _rule_component("rhr", 70, 54.0, 50.0),  # +4 bpm
            _rule_component("sleep", 61, 7.0, 7.5),
        ]
    )
    assert rules == []
    assert total == 0
    assert metrics._capped_adjustment(total) == 0


def test_warnregeln_im_payload_gedeckelt() -> None:
    today = date(2026, 11, 9)
    rows = _wellness(10, today)
    for row in rows:
        row.update({"hrv": 50.0, "rhr": 50.0, "sleep_s": 8 * 3600.0, "sleep_awake_s": 6 * 60.0})
    rows[0].update(
        {
            "hrv": 40.0,
            "rhr": 56.0,
            "sleep_s": 3 * 3600.0,
            "sleep_awake_s": 6 * 60.0,
        }
    )
    days = metrics.daily_days(rows, [], today - timedelta(days=20), today)
    recovery = metrics.compute_recovery(days, len(days) - 1)

    assert {rule["id"] for rule in recovery["triggeredRules"]} == {
        "hrv_rhr",
        "hrv_sleep",
        "rhr_sleep",
        "triple_low",
    }
    assert recovery["adjustment"] == -15
    assert recovery["score"] == 10
    assert "gedeckelt" in recovery["explanation"]
    for rule in recovery["triggeredRules"]:
        assert set(rule) == {"id", "label", "adjustment"}
        assert rule["adjustment"] < 0


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
