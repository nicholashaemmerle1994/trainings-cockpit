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


def test_gleiche_gesamtzeit_schlaegt_verschiedene_strecke() -> None:
    """Die Long Ride vom 1. November: Wahoo und Health Sync rechnen anders.

    Gleicher Start, gleiche Gesamtzeit von 10.007 s, aber 9.796 gegen 7.320 s
    Bewegung und 73,7 gegen 77,0 km. Genau das fiel durch die alte Regel.
    """
    wahoo = _row(
        id="i204257493",
        type="VirtualRide",
        source="WAHOO",
        start_date_local="2026-11-01T08:05:03",
        moving_time=9796,
        elapsed_time=10007,
        distance=73652.51,
        device_name="WAHOO_FITNESS WAHOO APP",
    )
    health = _row(
        id="i204634552",
        type="VirtualRide",
        source="OAUTH_CLIENT",
        start_date_local="2026-11-01T08:05:03",
        moving_time=7320,
        elapsed_time=10007,
        distance=77012.96,
        device_name="Health Sync",
    )

    assert dedupe.ist_dublette(wahoo, health)
    # Der längere Verlauf bleibt.
    assert [row["id"] for row in dedupe.entdoppeln([health, wahoo])] == ["i204257493"]


def test_gleiche_strecke_bei_anderer_bewegungszeit() -> None:
    """Ein Schwimmen von Garmin und von Health Sync: 2.050 m, 3.024 gegen 2.542 s."""
    health = _row(
        id="i200867072",
        type="Swim",
        source="OAUTH_CLIENT",
        start_date_local="2026-10-23T15:12:58",
        moving_time=3024,
        elapsed_time=3086,
        distance=2050,
        device_name="Health Sync",
    )
    garmin = _row(
        id="24825657394",
        type="Swim",
        source="GARMIN_PERSONAL",
        start_date_local="2026-10-23T15:12:58",
        moving_time=2542,
        elapsed_time=2868,
        distance=2050,
        device_name="Garmin (Personal API)",
    )

    assert dedupe.ist_dublette(health, garmin)
    # Garmin bleibt, wie in D-32 festgelegt.
    assert [row["id"] for row in dedupe.entdoppeln([health, garmin])] == ["24825657394"]


def test_behalten_vergleicht_rohdaten_aus_beiden_quellen() -> None:
    """Vor dem Schreiben liegen intervals-Rohdaten und Datenbank-Zeilen nebeneinander."""
    import json

    intervals = _row(
        id="i200867072",
        type="Swim",
        source="OAUTH_CLIENT",
        moving_time=2600,
        elapsed_time=3200,
        distance=2050,
    )
    garmin_zeile = {
        "source": "garmin",
        "source_id": "24825657394",
        "sport": "Swim",
        "raw": json.dumps(
            {
                "id": "24825657394",
                "type": "Swim",
                "source": "GARMIN_PERSONAL",
                "start_date_local": "2026-10-30T07:35:00",
                "moving_time": 2542,
                "elapsed_time": 2700,
                "distance": 2050,
            }
        ),
    }

    # Gleiche Strecke und ähnliche Bewegungszeit, andere Gesamtzeit: die
    # Rohdaten der Garmin-Zeile zählen, nicht die Spalten der Tabelle.
    assert dedupe.behalten([intervals, garmin_zeile]) == {"24825657394"}


def test_gleiche_bewegungszeit_schlaegt_verschiedene_distanz() -> None:
    """15. April: ROUVY und Health Sync zählen für dieselbe Fahrt andere Kilometer.

    Start 84 s auseinander, 2.390 gegen 2.415 s Bewegung, aber 17,4 gegen 23,4 km
    und 2.568 gegen 3.170 s Gesamtzeit.
    """
    rouvy = _row(
        id="i139934969",
        type="VirtualRide",
        start_date_local="2026-04-15T16:20:00",
        moving_time=2390,
        elapsed_time=2568,
        distance=17384,
    )
    health = _row(
        id="i139936348",
        type="VirtualRide",
        start_date_local="2026-04-15T16:21:24",
        moving_time=2415,
        elapsed_time=3170,
        distance=23441,
    )

    assert dedupe.ist_dublette(rouvy, health)


def test_zwei_einheiten_derselben_art_mit_abstand_bleiben() -> None:
    """19 Minuten Abstand im Schwimmbad sind zwei Einheiten, keine Dublette."""
    frueh = _row(id="a", type="Swim", start_date_local="2026-10-30T15:15:40", moving_time=540,
                 elapsed_time=540, distance=400)
    spaet = _row(id="b", type="Swim", start_date_local="2026-10-30T15:34:07", moving_time=1614,
                 elapsed_time=1661, distance=1250)

    assert not dedupe.ist_dublette(frueh, spaet)


def test_gleiche_strecke_bei_doppelter_dauer_bleibt() -> None:
    """Gleiche Strecke, aber dreimal so lang: zwei Blöcke, keine Dublette."""
    kurz = _row(id="a", moving_time=1800, elapsed_time=1800)
    lang = _row(id="b", moving_time=5400, elapsed_time=5400)

    assert not dedupe.ist_dublette(kurz, lang)
