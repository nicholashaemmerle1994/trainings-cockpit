"""Dubletten: dieselbe Einheit, zweimal aufgezeichnet.

Seit Health Sync die Garmin-Daten über Apple Health nach intervals.icu schickt,
kommt eine Einheit oft doppelt an: einmal von Garmin Connect, einmal von Health
Sync, gelegentlich zusätzlich von Wahoo oder Zepp. Unterschiedliche IDs, gleiche
Einheit.

Erkannt wird nicht über die ID, sondern über den Verlauf: gleicher Tag, gleiche
Sportart, **fast gleicher Startzeitpunkt**, gleiche Dauer und Strecke. Der
Startzeitpunkt ist der scharfe Filter — zwei Atemübungen am selben Tag um 05:47
und 22:32 sind zwei Einheiten, auch wenn sie gleich lang sind.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

#: Zwei Aufzeichnungen beginnen innerhalb von fünf Minuten.
START_TOLERANCE_S = 300
#: … und dauern ungefähr gleich lang.
DURATION_TOLERANCE_S = 120
#: … und sind ungefähr gleich weit.
DISTANCE_TOLERANCE_M = 400


def _start(row: dict[str, Any]) -> datetime | None:
    roh = row.get("start_date_local") or row.get("start_date") or ""
    try:
        return datetime.fromisoformat(str(roh)[:19])
    except ValueError:
        return None


def _duration(row: dict[str, Any]) -> float:
    return float(row.get("moving_time") or row.get("elapsed_time") or 0)


def _distance(row: dict[str, Any]) -> float:
    return float(row.get("distance") or 0)


def _score(row: dict[str, Any]) -> tuple[int, int, float]:
    """Welche Aufzeichnung bleibt.

    Garmin Connect schlägt Apple Health, weil die Uhr Höhenmeter und Puls selbst
    misst. Bei Gleichstand gewinnt die vollständigere, dann die längere Aufzeichnung.
    """
    quelle = str(row.get("source") or "")
    geraet = str(row.get("device_name") or "").lower()
    garmin = 2 if quelle == "GARMIN_CONNECT" else (1 if "garmin" in geraet else 0)
    felder = sum(
        1
        for key in ("average_heartrate", "max_heartrate", "total_elevation_gain", "distance")
        if row.get(key)
    )
    return (garmin, felder, _duration(row))


def ist_dublette(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("type") != b.get("type"):
        return False
    start_a, start_b = _start(a), _start(b)
    if not start_a or not start_b:
        return False
    if abs((start_a - start_b).total_seconds()) > START_TOLERANCE_S:
        return False
    if abs(_duration(a) - _duration(b)) > DURATION_TOLERANCE_S:
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
