"""Tests für die Verläufe: einlesen, verdichten, ausliefern."""

from __future__ import annotations

from datetime import date, datetime

from trainings_cockpit import db, streams


def _activity(**overrides: object) -> dict:
    row = {
        "id": "i1",
        "start_date_local": "2026-11-03T07:00:00",
        "type": "Ride",
        "name": "Schwelle",
        "moving_time": 3600,
        "elapsed_time": 3600,
        "distance": 30000.0,
    }
    row.update(overrides)
    return row


def _conn(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    db.init_db(conn)
    db.upsert_activities(conn, [_activity()])
    return conn, conn.execute("SELECT id FROM activity").fetchone()[0]


def test_intervals_streams_werden_zu_spuren() -> None:
    series = streams.series_from_intervals(
        [
            {"type": "time", "data": [10, 11, 12, 13]},
            {"type": "watts", "data": [100, None, 300, 200]},
            {"type": "heartrate", "data": [120, 121, 122, 123]},
            {"type": "velocity_smooth", "data": [5.5, 5.5, 5.5, 5.5]},
            {"type": "distance", "data": [0, 5, 11, 16]},
        ]
    )

    assert series["t"] == [0, 1, 2, 3]
    assert series["watts"] == [100, None, 300, 200]
    assert series["hr"] == [120, 121, 122, 123]
    assert series["speed"] == [5.5, 5.5, 5.5, 5.5]
    assert series["dist"] == [0.0, 5.0, 11.0, 16.0]


def test_punkte_ohne_zeit_fallen_weg() -> None:
    series = streams.series_from_intervals(
        [
            {"type": "time", "data": [0, None, 2, 3]},
            {"type": "watts", "data": [100, 999, 300, 200]},
        ]
    )

    assert series["t"] == [0, 2, 3]
    assert series["watts"] == [100, 300, 200]


def test_ein_einziger_punkt_ist_kein_verlauf() -> None:
    nur_ein_punkt = [{"type": "time", "data": [0]}, {"type": "watts", "data": [200]}]

    assert streams.series_from_intervals(nur_ein_punkt) == {}


def test_fit_records_werden_zu_spuren() -> None:
    series = streams.series_from_records(
        [
            {
                "timestamp": datetime(2026, 11, 3, 7, 0, 0),
                "heart_rate": 140,
                "enhanced_speed": 3.2,
                "distance": 0.0,
            },
            {
                "timestamp": datetime(2026, 11, 3, 7, 0, 5),
                "heart_rate": 142,
                "enhanced_speed": 3.4,
                "distance": 16.0,
            },
        ]
    )

    assert series["t"] == [0, 5]
    assert series["hr"] == [140, 142]
    assert series["speed"] == [3.2, 3.4]
    assert series["watts"] == [None, None]


def test_compact_mittelt_je_fuenf_sekunden() -> None:
    series = {
        "t": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        "watts": [100, 100, 100, 100, 100, 200, 200, 200, 200, 200],
        "hr": [None] * 10,
        "speed": [None] * 10,
        "dist": [None] * 10,
    }

    kompakt = streams.compact(series)

    assert kompakt["t"] == [2, 7]
    assert kompakt["watts"] == [100, 200]
    assert kompakt["hr"] == [None, None]


def test_downsample_haelt_die_grenze_ein() -> None:
    series = {
        "t": list(range(400)),
        "watts": [150] * 400,
        "hr": [130] * 400,
        "speed": [None] * 400,
        "dist": [None] * 400,
    }

    klein = streams.downsample(series, 180)

    assert len(klein["t"]) <= 180
    assert len(klein["t"]) > 100
    assert klein["t"][0] < klein["t"][-1]
    assert set(klein["watts"]) == {150}


def test_rad_zeigt_die_leistung(tmp_path) -> None:
    conn, row_id = _conn(tmp_path)
    db.upsert_stream(
        conn,
        row_id,
        streams.compact(
            {
                "t": list(range(600)),
                "watts": [200] * 300 + [100] * 300,
                "hr": [150] * 600,
                "speed": [8.0] * 600,
                "dist": [None] * 600,
            }
        ),
        120,
    )

    serie = streams.payload(conn, db.activity_by_row_id(conn, row_id))

    assert serie is not None
    assert serie["kind"] == "power"
    assert serie["mean"] == 150.0
    assert serie["peak"] == 200
    assert len(serie["points"]) <= streams.MAX_POINTS
    assert serie["reference"] is None


def test_lauf_zeigt_das_tempo_in_minuten_je_kilometer(tmp_path) -> None:
    conn, row_id = _conn(tmp_path)
    db.upsert_activities(conn, [_activity(id="i2", type="Run")])
    row_id = conn.execute("SELECT id FROM activity WHERE sport = 'Run'").fetchone()[0]
    db.upsert_stream(
        conn,
        row_id,
        streams.compact(
            {
                "t": list(range(300)),
                # 12 km/h sind 5:00 min/km.
                "watts": [None] * 300,
                "hr": [150] * 300,
                "speed": [3.333] * 300,
                "dist": [None] * 300,
            }
        ),
        60,
    )

    serie = streams.payload(conn, db.activity_by_row_id(conn, row_id))

    assert serie is not None
    assert serie["kind"] == "pace"
    assert serie["unit"] == "/km"
    assert serie["mean"] == 5.0
    assert serie["pulse"] == 150.0


def test_ohne_verlauf_bleibt_das_blatt_wie_es_war(tmp_path) -> None:
    conn, row_id = _conn(tmp_path)

    assert streams.payload(conn, db.activity_by_row_id(conn, row_id)) is None


def test_eine_leere_reihe_zeichnet_nichts(tmp_path) -> None:
    conn, row_id = _conn(tmp_path)
    db.upsert_stream(conn, row_id, {}, 0)

    assert streams.payload(conn, db.activity_by_row_id(conn, row_id)) is None
    assert db.streams_between(conn, date(2026, 11, 1), date(2026, 11, 5)) == {row_id}


def test_kraft_zeigt_den_puls(tmp_path) -> None:
    conn, _ = _conn(tmp_path)
    db.upsert_activities(conn, [_activity(id="i3", type="WeightTraining")])
    row_id = conn.execute("SELECT id FROM activity WHERE sport = 'WeightTraining'").fetchone()[0]
    db.upsert_stream(
        conn,
        row_id,
        streams.compact(
            {
                "t": list(range(200)),
                "watts": [None] * 200,
                "hr": [110] * 200,
                "speed": [None] * 200,
                "dist": [None] * 200,
            }
        ),
        40,
    )

    serie = streams.payload(conn, db.activity_by_row_id(conn, row_id))

    assert serie is not None
    assert serie["kind"] == "hr"
    assert serie["mean"] == 110.0
