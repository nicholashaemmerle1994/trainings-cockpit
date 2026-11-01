from __future__ import annotations

from datetime import date

from trainings_cockpit import db


def _activity(**overrides: object) -> dict:
    row = {
        "id": "i1",
        "start_date_local": "2026-10-01T07:00:00",
        "type": "Run",
        "name": "Testlauf",
        "moving_time": 1800,
        "elapsed_time": 1900,
        "distance": 5000.0,
        "icu_training_load": 40.0,
    }
    row.update(overrides)
    return row


def test_upsert_activities_is_idempotent(tmp_path) -> None:
    conn = db.connect(tmp_path / "test.db")
    db.init_db(conn)

    assert db.upsert_activities(conn, [_activity()]) == 1
    assert db.upsert_activities(conn, [_activity(name="Geändert")]) == 1
    assert db.counts(conn)["activities"] == 1

    rows = db.activities_between(conn, date(2026, 10, 1), date(2026, 10, 2))
    assert rows[0]["name"] == "Geändert"
    assert rows[0]["load"] == 40.0


def test_upsert_wellness_updates_by_date(tmp_path) -> None:
    conn = db.connect(tmp_path / "test.db")
    db.init_db(conn)

    db.upsert_wellness(conn, [{"id": "2026-10-01", "hrv": 50, "restingHR": 48}])
    db.upsert_wellness(conn, [{"id": "2026-10-01", "hrv": 55, "restingHR": 47}])

    rows = db.wellness_between(conn, date(2026, 10, 1), date(2026, 10, 1))
    assert len(rows) == 1
    assert rows[0]["hrv"] == 55.0
    assert rows[0]["rhr"] == 47.0


def test_events_and_settings(tmp_path) -> None:
    conn = db.connect(tmp_path / "test.db")
    db.init_db(conn)

    db.upsert_events(
        conn,
        [
            {
                "id": 7,
                "start_date_local": "2026-11-01T00:00:00",
                "type": "Ride",
                "category": "WORKOUT",
                "name": "Long Ride",
                "icu_training_load": 120,
                "moving_time": 7200,
            }
        ],
    )
    upcoming = db.upcoming_events(conn, date(2026, 10, 30))
    assert upcoming[0]["name"] == "Long Ride"

    db.set_setting(conn, "athlete_name", "Nicholas Pahr")
    assert db.get_setting(conn, "athlete_name") == "Nicholas Pahr"
    assert db.counts(conn)["events"] == 1
