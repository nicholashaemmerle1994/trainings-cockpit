"""Dubletten: dieselbe Einheit, zweimal aufgezeichnet.

Seit Health Sync die Garmin-Daten über Apple Health nach intervals.icu schickt,
kommt eine Einheit oft doppelt an: einmal von Garmin Connect, einmal von Health
Sync, gelegentlich zusätzlich von Wahoo oder Zepp. Unterschiedliche IDs, gleiche
Einheit.

Erkannt wird nicht über die ID, sondern über den Verlauf: gleiche Sportart und
**fast gleicher Startzeitpunkt** — und dazu mindestens eine übereinstimmende
Spur: dieselbe Gesamtzeit, dieselbe Bewegungszeit oder dieselbe Strecke. Der
Startzeitpunkt ist der scharfe Filter — zwei Atemübungen am selben Tag um 05:47
und 22:32 sind zwei Einheiten, auch wenn sie gleich lang sind.

Die Gesamtzeit ist der verlässlichste Zeuge: sie steht in der Aufzeichnung selbst
und wird beim Wiederveröffentlichen nicht neu gerechnet. Bewegungszeit und
Strecke rechnet jede Plattform anders — Wahoo und Health Sync kamen für dieselbe
Fahrt auf 9.796 und 7.320 Sekunden Bewegung, aber beide auf 10.007 Sekunden
Gesamtzeit.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

#: Zwei Aufzeichnungen beginnen innerhalb von fünf Minuten.
START_TOLERANCE_S = 300
#: … und dauern insgesamt ungefähr gleich lang — dieselbe Uhr.
ELAPSED_TOLERANCE_S = 300
#: … oder dauern in Bewegung ungefähr gleich lang.
DURATION_TOLERANCE_S = 120
#: Bei langen Einheiten zählt auch ein Anteil statt fester Minuten: zwei
#: Aufzeichnungen derselben Fahrt können sich beim Abziehen von Pausen um mehr
#: als zwei Minuten unterscheiden, ohne verschiedene Fahrten zu sein.
DURATION_SHARE = 0.2
#: … und sind ungefähr gleich weit.
DISTANCE_TOLERANCE_M = 400


def _start(row: dict[str, Any]) -> datetime | None:
    roh = row.get("start_date_local") or row.get("start_date") or ""
    try:
        return datetime.fromisoformat(str(roh)[:19])
    except ValueError:
        return None


def _elapsed(row: dict[str, Any]) -> float:
    return float(row.get("elapsed_time") or row.get("moving_time") or 0)


def _duration(row: dict[str, Any]) -> float:
    return float(row.get("moving_time") or row.get("elapsed_time") or 0)


def _distance(row: dict[str, Any]) -> float:
    return float(row.get("distance") or 0)


def _score(row: dict[str, Any]) -> tuple[int, int, float]:
    """Welche Aufzeichnung bleibt.

    Die Garmin-Aufzeichnung schlägt Apple Health, weil die Uhr Puls und Strecke
    selbst misst. Innerhalb der Garmin-Zeilen steht die Personal API vor der
    Zeile, die über Garmin Connect kam: dieselbe Aufzeichnung, aber die Personal
    API gibt die Bewegungszeit des Geräts weiter, intervals hat sie im April
    einmal als Gesamtzeit übernommen (250 m in 43 Minuten). Bei Gleichstand
    gewinnt die vollständigere, dann die längere Aufzeichnung.
    """
    quelle = str(row.get("source") or "")
    geraet = str(row.get("device_name") or "").lower()
    garmin = 3 if quelle == "GARMIN_PERSONAL" else (2 if quelle == "GARMIN_CONNECT" else 0)
    if not garmin and "garmin" in geraet:
        garmin = 1
    felder = sum(
        1
        for key in ("average_heartrate", "max_heartrate", "total_elevation_gain", "distance")
        if row.get(key)
    )
    return (garmin, felder, _duration(row))


def _nahe_dauer(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Gleiche Bewegungszeit, mit Spielraum für lange Einheiten."""
    dauer_a, dauer_b = _duration(a), _duration(b)
    spielraum = max(DURATION_TOLERANCE_S, DURATION_SHARE * max(dauer_a, dauer_b))
    return abs(dauer_a - dauer_b) <= spielraum


def ist_dublette(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("type") != b.get("type"):
        return False
    start_a, start_b = _start(a), _start(b)
    if not start_a or not start_b:
        return False
    if abs((start_a - start_b).total_seconds()) > START_TOLERANCE_S:
        return False
    # Dieselbe Uhr: die Gesamtzeit überlebt das Wiederveröffentlichen.
    if abs(_elapsed(a) - _elapsed(b)) <= ELAPSED_TOLERANCE_S:
        return True
    # Dieselbe Bewegungszeit: eine Fahrt, zwei Wege — auch wenn ROUVY 17,4 und
    # Health Sync 23,4 km daraus machen.
    if abs(_duration(a) - _duration(b)) <= DURATION_TOLERANCE_S:
        return True
    # Sonst zählt der Verlauf: gleiche Strecke bei ähnlicher Dauer.
    if not _nahe_dauer(a, b):
        return False
    return abs(_distance(a) - _distance(b)) <= DISTANCE_TOLERANCE_M


def paare(rows: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Alle Dubletten als (Gewinner, Verlierer)."""
    sortiert = sorted([r for r in rows if _start(r)], key=_start)  # type: ignore[arg-type]
    vergeben: set[int] = set()
    treffer: list[tuple[dict[str, Any], dict[str, Any]]] = []

    for i, a in enumerate(sortiert):
        if i in vergeben:
            continue
        for j in range(i + 1, len(sortiert)):
            if j in vergeben:
                continue
            b = sortiert[j]
            abstand = (_start(b) - _start(a)).total_seconds()  # type: ignore[operator]
            if abstand > START_TOLERANCE_S:
                break
            if ist_dublette(a, b):
                gewinner, verlierer = (a, b) if _score(a) >= _score(b) else (b, a)
                treffer.append((gewinner, verlierer))
                vergeben.add(j)
    return treffer


def entdoppeln(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die Liste ohne die Verlierer der Dublettenpaare."""
    weg = {id(verlierer) for _, verlierer in paare(rows)}
    return [row for row in rows if id(row) not in weg]


def _roh(row: dict[str, Any]) -> dict[str, Any]:
    """Die Aufzeichnung selbst, egal ob Rohdaten oder Datenbank-Zeile."""
    raw = row.get("raw")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            geladen = json.loads(raw)
        except ValueError:
            return row
        return geladen if isinstance(geladen, dict) else row
    return row


def behalten(rows: list[dict[str, Any]]) -> set[str]:
    """IDs der Aufzeichnungen, die bleiben — über alle Quellen hinweg.

    Nimmt intervals-Rohdaten und Datenbank-Zeilen (mit `raw`) gemischt: die
    Prüfung liest in beiden Fällen die Aufzeichnung selbst. Damit fällt die
    Entscheidung **vor** dem Schreiben, statt eine Zeile anzulegen und im
    nächsten Sync wieder zu löschen.
    """
    return {str(r.get("id")) for r in entdoppeln([_roh(row) for row in rows]) if r.get("id")}


def aus_datenbank(conn: Any, table: str = "activity") -> list[dict[str, Any]]:
    """Gespeicherte Aktivitäten inklusive Rohdaten als Liste."""
    rows: list[dict[str, Any]] = []
    for eintrag in conn.execute(f"SELECT raw FROM {table}"):  # noqa: S608 - fester Tabellenname
        roh = eintrag["raw"]
        if not roh:
            continue
        try:
            rows.append(json.loads(roh))
        except ValueError:
            continue
    return rows
