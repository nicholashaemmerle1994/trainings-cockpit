from __future__ import annotations

from trainings_cockpit.sources.garmin import GarminDump, _as_list, _try, wellness_rows


def test_as_list_unwraps_nested_list() -> None:
    assert _as_list([1, 2]) == [1, 2]
    assert _as_list({"sleepSummaries": [{"date": "2026-10-01"}]}) == [{"date": "2026-10-01"}]
    assert _as_list({"value": 3}) == [{"value": 3}]


def test_try_extends_lists_and_records_errors() -> None:
    dump = GarminDump()
    _try(dump, "sleep", lambda: {"sleepSummaries": [{"n": 1}]})
    _try(dump, "sleep", lambda: [{"n": 2}])
    assert dump.sleep == [{"n": 1}, {"n": 2}]

    _try(dump, "profile", lambda: {"displayName": "Nicholas"})
    assert dump.profile == {"displayName": "Nicholas"}

    def boom() -> None:
        raise RuntimeError("endpoint down")

    _try(dump, "hrv", boom)
    assert "endpoint down" in dump.errors["hrv"]


def test_wellness_aus_drei_endpunkten_wird_eine_nacht() -> None:
    """Schlaf, HRV und Tageszusammenfassung gehören zum selben Tag."""
    dump = GarminDump(
        sleep=[
            {
                "calendarDate": "2026-11-04",
                "sleepTimeSeconds": 27_600,
                "sleepScores": {"overall": {"value": 83}},
                "averageRespirationValue": 14.2,
            }
        ],
        hrv=[{"calendarDate": "2026-11-04", "lastNightAvg": 46}],
        summaries=[
            {
                "calendarDate": "2026-11-04",
                "heartRate": {"restingValue": 54},
                "respiration": {"avgValue": 14.9},
            }
        ],
        weight=[{"calendarDate": "2026-11-04", "weight": 79_400}],
    )

    rows = wellness_rows(dump)

    assert rows == [
        {
            "id": "2026-11-04",
            "sleepSecs": 27_600,
            "sleepScore": 83,
            "respiration": 14.2,
            "hrv": 46,
            "restingHR": 54,
            "weight": 79.4,
        }
    ]


def test_wellness_ohne_werte_erzeugt_keine_zeile() -> None:
    """Ein Tag ohne ein einziges Signal ist keine Nacht."""
    dump = GarminDump(
        sleep=[{"calendarDate": None, "sleepTimeSeconds": None}],
        hrv=[{"calendarDate": "2026-11-05", "lastNightAvg": None}],
        summaries=[{"calendarDate": "2026-11-05", "heartRate": {}}],
    )

    assert wellness_rows(dump) == []


def test_wellness_nimmt_die_atmung_aus_der_nacht_vor_der_tagesatmung() -> None:
    dump = GarminDump(
        sleep=[{"calendarDate": "2026-11-04", "averageRespirationValue": 13.4}],
        summaries=[{"calendarDate": "2026-11-04", "respiration": {"avgValue": 16.1}}],
    )

    assert wellness_rows(dump)[0]["respiration"] == 13.4


def test_wellness_liest_phasen_sleep_need_und_schlafziel() -> None:
    dump = GarminDump(
        profile={"sleepGoal": 28_800},
        sleep=[
            {
                "calendarDate": "2026-11-04",
                "sleepTimeSeconds": 27_000,
                "awakeSleepSeconds": 1_200,
                "deepSleepSeconds": 5_400,
                "lightSleepSeconds": 18_000,
                "remSleepSeconds": 3_600,
                "sleepNeed": {"actual": 29_400},
            }
        ],
    )

    row = wellness_rows(dump)[0]
    assert row["awakeSleepSeconds"] == 1_200
    assert row["deepSleepSeconds"] == 5_400
    assert row["lightSleepSeconds"] == 18_000
    assert row["remSleepSeconds"] == 3_600
    assert row["sleepNeedHours"] == 8.17
    assert row["sleepGoalHours"] == 8.0


def test_sleep_need_ohne_dict_und_ohne_ziel() -> None:
    dump = GarminDump(
        sleep=[
            {
                "calendarDate": "2026-11-04",
                "sleepTimeSeconds": 27_000,
                "sleepNeed": 27_900,
            }
        ]
    )

    row = wellness_rows(dump)[0]
    assert row["sleepNeedHours"] == 7.75
    assert "sleepGoalHours" not in row


def test_wachzeit_aus_zeit_im_bett_abgeleitet() -> None:
    dump = GarminDump(
        sleep=[
            {
                "calendarDate": "2026-11-04",
                "sleepTimeSeconds": 27_000,
                "sleepStartTimestampGMT": 1_760_000_000_000,
                "sleepEndTimestampGMT": 1_760_028_200_000,
            }
        ]
    )

    assert wellness_rows(dump)[0]["awakeSleepSeconds"] == 1_200


def test_wachzeit_aus_lokalen_iso_zeiten_abgeleitet() -> None:
    dump = GarminDump(
        sleep=[
            {
                "calendarDate": "2026-11-04",
                "sleepTimeSeconds": 27_000,
                "sleepStartTimestampLocal": "2026-11-04T23:00:00",
                "sleepEndTimestampLocal": "2026-11-05T06:50:00",
            }
        ]
    )

    assert wellness_rows(dump)[0]["awakeSleepSeconds"] == 1_200


def test_explizite_wachzeit_gewinnt() -> None:
    dump = GarminDump(
        sleep=[
            {
                "calendarDate": "2026-11-04",
                "sleepTimeSeconds": 27_000,
                "awakeSleepSeconds": 600,
                "sleepStartTimestampGMT": 1_760_000_000_000,
                "sleepEndTimestampGMT": 1_760_028_200_000,
            }
        ]
    )

    assert wellness_rows(dump)[0]["awakeSleepSeconds"] == 600


def test_schlaf_aus_daily_sleep_dto() -> None:
    dump = GarminDump(
        sleep=[
            {
                "dailySleepDTO": {
                    "calendarDate": "2026-11-04",
                    "sleepTimeSeconds": 27_000,
                    "awakeSleepSeconds": 1_200,
                }
            }
        ]
    )

    row = wellness_rows(dump)[0]
    assert row["sleepSecs"] == 27_000
    assert row["awakeSleepSeconds"] == 1_200
