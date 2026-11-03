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
