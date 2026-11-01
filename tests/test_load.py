from __future__ import annotations

from datetime import date, timedelta

from trainings_cockpit import load, metrics


def test_last_trifft_die_historische_skala() -> None:
    # 52 min bei 151 bpm ergaben in intervals 67 Punkte.
    assert 50 <= load.compute_load("Run", 51.7 * 60, 151) <= 70


def test_last_ohne_puls_oder_dauer_ist_leer() -> None:
    assert load.compute_load("Run", 3600, None) is None
    assert load.compute_load("Run", None, 150) is None
    assert load.compute_load("Run", 3600, 300) is None


def test_schwimmen_hat_einen_eigenen_faktor() -> None:
    swim = load.compute_load("Swim", 58 * 60, 145)
    run = load.compute_load("Run", 58 * 60, 145)
    assert swim is not None and run is not None
    assert swim < run


def test_last_waechst_mit_quadrat_des_pulses() -> None:
    leise = load.compute_load("Run", 3600, 120)
    laut = load.compute_load("Run", 3600, 160)
    assert leise is not None and laut is not None
    assert laut > leise * 1.7


def test_garmin_aktivitaeten_werden_gemappt() -> None:
    from trainings_cockpit.sources.garmin import GarminDump, actor_rows

    dump = GarminDump(
        activities=[
            {
                "activityId": 4711,
                "activityName": "Wien - Long Run",
                "activityType": {"typeKey": "running"},
                "startTimeLocal": "2026-10-31T07:10:46.0",
                "duration": 6707.0,
                "movingDuration": 6100.0,
                "distance": 17000.0,
                "elevationGain": 80.0,
                "averageHR": 151.0,
                "maxHR": 167.0,
                "calories": 1200.0,
            },
            {
                "activityId": 4712,
                "activityName": "Kraft",
                "activityType": {"typeKey": "strength_training"},
                "startTimeLocal": "2026-10-30T18:00:00.0",
                "duration": 3000.0,
            },
        ]
    )
    rows = actor_rows(dump)

    # Nur Läufe und Schwimmen kommen direkt – Kraft bleibt bei intervals.
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "garmin"
    assert row["source_id"] == "4711"
    assert row["sport"] == "Run"
    assert row["duration_s"] == 6707
    assert row["load"] is not None and row["load"] > 40
    assert '"GARMIN_PERSONAL"' in row["raw"]


def test_garmin_last_passt_zur_bisherigen_last() -> None:
    """Die Formel muss die alte intervals-Last treffen, sonst springt die Fitness."""
    from trainings_cockpit.sources.garmin import GarminDump, actor_rows

    # Drei echte Paare aus den Rohdaten: (Start, Dauer in s, Puls, intervals-Last)
    pairs = [
        ("2026-10-17T10:34:00.0", 51.7 * 60, 151.0, 67.0),
        ("2026-10-13T18:00:00.0", 33.6 * 60, 145.0, 39.0),
        ("2026-10-19T07:30:00.0", 69.7 * 60, 149.0, 78.0),
    ]
    dump = GarminDump(
        activities=[
            {
                "activityId": index,
                "activityType": {"typeKey": "running"},
                "startTimeLocal": start,
                "duration": duration,
                "averageHR": hr,
            }
            for index, (start, duration, hr, _) in enumerate(pairs, start=1)
        ]
    )
    rows = actor_rows(dump)
    assert len(rows) == 3
    for row, (_, _, _, expected) in zip(rows, pairs):
        assert abs(row["load"] - expected) <= expected * 0.2
