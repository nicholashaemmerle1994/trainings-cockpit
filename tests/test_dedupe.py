from __future__ import annotations

from trainings_cockpit import dedupe


def _row(**kwargs):
    base = {
        "id": "i1",
        "type": "Run",
        "start_date_local": "2026-10-30T07:35:00",
        "moving_time": 2700,
        "distance": 20600,
        "source": "GARMIN_CONNECT",
        "device_name": "Garmin fenix 7 Pro",
        "average_heartrate": 140,
    }
    base.update(kwargs)
    return base


def test_same_ride_from_two_sources_is_a_duplicate() -> None:
    garmin = _row(id="i1", source="GARMIN_CONNECT")
    health = _row(id="i2", source="OAUTH_CLIENT", device_name="Health Sync")

    assert dedupe.ist_dublette(garmin, health)
    assert dedupe.entdoppeln([garmin, health]) == [garmin]


def test_two_breathing_sessions_are_not_duplicates() -> None:
    morgen = _row(
        id="i1",
        type="Workout",
        start_date_local="2026-09-22T05:47:00",
        moving_time=333,
        distance=0,
    )
    abend = _row(
        id="i2",
        type="Workout",
        start_date_local="2026-09-22T22:32:00",
        moving_time=333,
        distance=0,
    )

    assert not dedupe.ist_dublette(morgen, abend)
    assert len(dedupe.entdoppeln([morgen, abend])) == 2


def test_different_sport_is_not_a_duplicate() -> None:
    lauf = _row(type="Run")
    rad = _row(id="i2", type="Ride")

    assert not dedupe.ist_dublette(lauf, rad)


def test_different_length_is_not_a_duplicate() -> None:
    kurz = _row(moving_time=1800)
    lang = _row(id="i2", moving_time=5400)

    assert not dedupe.ist_dublette(kurz, lang)


def test_garmin_wins_over_health_sync() -> None:
    garmin = _row(id="g", source="GARMIN_CONNECT")
    health = _row(id="h", source="OAUTH_CLIENT", device_name="Health Sync")

    gewinner, verlierer = dedupe.paare([health, garmin])[0]
    assert gewinner["id"] == "g"
    assert verlierer["id"] == "h"


def test_paare_findet_nur_ein_paar_je_einheit() -> None:
    a = _row(id="a", source="GARMIN_CONNECT")
    b = _row(id="b", source="OAUTH_CLIENT")
    c = _row(id="c", source="ZEPP", start_date_local="2026-10-30T07:36:00")

    paare = dedupe.paare([a, b, c])
    # Eine Aufzeichnung kann zwei Dubletten schlagen: beide Paare zeigen auf a.
    assert len(paare) == 2
    assert {gewinner["id"] for gewinner, _ in paare} == {"a"}
    assert len(dedupe.entdoppeln([a, b, c])) == 1
