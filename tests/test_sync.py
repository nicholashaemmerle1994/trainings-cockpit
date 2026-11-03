from __future__ import annotations

from datetime import date

import pytest

from trainings_cockpit import db
from trainings_cockpit import sync as sync_mod
from trainings_cockpit.config import Settings
from trainings_cockpit.sources.garmin import GarminDump


class FakeIntervals:
    """intervals liefert Plan und Aktivitäten — die Nächte nicht mehr (D-50)."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self) -> FakeIntervals:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def athlete(self) -> dict:
        return {"id": "i123", "name": "NicholasPahr"}

    def activities(self, oldest: date, newest: date) -> list[dict]:
        return []

    def events(self, oldest: date, newest: date) -> list[dict]:
        return []

    def sport_settings(self) -> list[dict]:
        return []

    def wellness(self, oldest: date, newest: date) -> list[dict]:
        raise AssertionError("Nächte kommen aus Garmin, nicht aus intervals (D-50)")


def _dump() -> GarminDump:
    return GarminDump(
        sleep=[
            {
                "calendarDate": "2026-11-04",
                "sleepTimeSeconds": 27_600,
                "sleepScores": {"overall": {"value": 83}},
                "averageRespirationValue": 14.2,
            }
        ],
        hrv=[{"calendarDate": "2026-11-04", "lastNightAvg": 46}],
        summaries=[{"calendarDate": "2026-11-04", "heartRate": {"restingValue": 54}}],
    )


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Settings:
    monkeypatch.setattr(sync_mod, "IntervalsClient", FakeIntervals)
    monkeypatch.setattr(sync_mod, "fetch_garmin", lambda *a, **k: _dump())
    return Settings(
        intervals_key="test",
        intervals_athlete="0",
        garmin_key="garmin",
        data_dir=tmp_path,
        base_url="https://example.invalid/api/v1",
    )


def test_sync_schreibt_die_naechte_aus_garmin(settings: Settings) -> None:
    ergebnis = sync_mod.sync(settings, days=30, today=date(2026, 11, 4))

    conn = db.connect(settings.db_path)
    row = db.wellness_between(conn, date(2026, 11, 4), date(2026, 11, 4))[0]
    conn.close()

    assert ergebnis["wellness"] == 1
    assert row["hrv"] == 46.0
    assert row["rhr"] == 54.0
    assert row["sleep_s"] == 27_600
    assert row["sleep_score"] == 83
    assert row["respiration"] == pytest.approx(14.2)


def test_ohne_garmin_bleiben_die_naechte_leer(settings: Settings) -> None:
    """Kein stiller Rückfall auf intervals (D-26, D-50)."""
    ohne_garmin = Settings(
        intervals_key=settings.intervals_key,
        intervals_athlete="0",
        garmin_key=None,
        data_dir=settings.data_dir,
        base_url=settings.base_url,
    )

    ergebnis = sync_mod.sync(ohne_garmin, days=30, today=date(2026, 11, 4))

    assert ergebnis["wellness"] == 0


def test_nur_naechte_seit_dem_sensorwechsel(settings: Settings, monkeypatch) -> None:
    """Vor dem Wechsel bleibt der alte Bestand stehen (D-31, D-50)."""
    conn = db.connect(settings.db_path)
    db.init_db(conn)
    db.set_wellness_epoch(conn, date(2026, 11, 4))
    conn.close()

    alt = GarminDump(
        summaries=[
            {"calendarDate": "2026-10-20", "heartRate": {"restingValue": 61}},
            {"calendarDate": "2026-11-04", "heartRate": {"restingValue": 54}},
        ]
    )
    monkeypatch.setattr(sync_mod, "fetch_garmin", lambda *a, **k: alt)

    sync_mod.sync(settings, days=30, today=date(2026, 11, 4))

    conn = db.connect(settings.db_path)
    alt_row = db.wellness_between(conn, date(2026, 10, 20), date(2026, 10, 20))
    neu_row = db.wellness_between(conn, date(2026, 11, 4), date(2026, 11, 4))
    conn.close()

    assert alt_row == []
    assert neu_row[0]["rhr"] == 54.0
