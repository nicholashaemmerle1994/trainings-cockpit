"""Sekundenwerte einer Aufzeichnung: was anlag, nicht was im Schnitt steht.

Zwei Wege führen zu denselben fünf Spuren — Zeit, Leistung, Puls, Tempo,
Strecke: intervals liefert sie fertig als Streams, Garmin als FIT-Datei der
Originalaufzeichnung. Beide werden hier auf eine Form gebracht und in
5-Sekunden-Mitteln abgelegt (D-53).

Geholt wird nur, was fehlt und nicht älter als zwei Wochen ist. Wer einen
Verlauf braucht, den die Quelle nicht hergibt, bekommt keinen: gezeichnet wird
nur, was gemessen wurde.
"""

from __future__ import annotations

import io
import math
import zipfile
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta
from typing import Any

from . import db, plan

#: Auflösung, in der eine Reihe in der Datenbank liegt.
BUCKET_S = 5
#: So viele Punkte bekommt ein Bildschirm höchstens zu sehen.
MAX_POINTS = 180
#: So weit zurück holt der Sync Verläufe nach.
STREAM_DAYS = 14
#: So viele Fünf-Sekunden-Fenster mittelt das gezeichnete Tempo (20 s).
PACE_SMOOTH = 4

#: Die Spuren, die eine Reihe führt. Reihenfolge ist die der Ausgabe.
CHANNELS = ("t", "watts", "hr", "speed", "dist")

#: Was die Hauptlinie zeigt, nach Sportart-Familie.
KINDS = {"bike": "power", "run": "pace"}

#: Einheit der Hauptlinie für die Achsenbeschriftung.
UNITS = {"power": "W", "pace": "/km", "hr": "bpm"}


# ------------------------------------------------------------------ Einlesen


def series_from_intervals(streams: list[dict[str, Any]] | None) -> dict[str, list[Any]]:
    """intervals' Streams auf die fünf Spuren abbilden."""
    data: dict[str, list[Any]] = {}
    for stream in streams or []:
        if isinstance(stream, dict) and stream.get("type"):
            data[str(stream["type"])] = list(stream.get("data") or [])
    return _series(
        time=data.get("time"),
        watts=data.get("watts"),
        hr=data.get("heartrate"),
        speed=data.get("velocity_smooth"),
        dist=data.get("distance"),
    )


def series_from_records(records: Iterable[dict[str, Any]]) -> dict[str, list[Any]]:
    """Messpunkte, wie `fit_records` sie liefert, auf die fünf Spuren abbilden."""
    rows = list(records)
    return _series(
        time=[row.get("timestamp") for row in rows],
        watts=[row.get("power") for row in rows],
        hr=[row.get("heart_rate") for row in rows],
        # Garmin schreibt das Tempo doppelt: `enhanced_speed` trägt die
        # Nachkommastellen, `speed` nur ganze Zentimeter.
        speed=[row.get("enhanced_speed") or row.get("speed") for row in rows],
        dist=[row.get("distance") for row in rows],
    )


#: Felder, die aus einer FIT-Datei gelesen werden — der Rest der Aufzeichnung
#: (Trittfrequenz, Bodenkontakt, Temperatur) wird nicht gezeichnet.
FIT_FIELDS = frozenset({"timestamp", "heart_rate", "power", "speed", "enhanced_speed", "distance"})


def fit_records(payload: bytes) -> list[dict[str, Any]]:
    """Die FIT-Datei aus dem ZIP von Garmin auspacken und ihre Messpunkte lesen."""
    from fitparse import FitFile  # noqa: PLC0415 - nur für Garmin-Aufzeichnungen nötig

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        name = next((n for n in archive.namelist() if n.lower().endswith(".fit")), "")
        if not name:
            return []
        raw = archive.read(name)

    records: list[dict[str, Any]] = []
    for message in FitFile(io.BytesIO(raw)).get_messages("record"):
        werte = {field.name: field.value for field in message if field.name in FIT_FIELDS}
        if werte.get("timestamp"):
            records.append(werte)
    return records


def _series(
    *,
    time: Sequence[Any] | None,
    watts: Sequence[Any] | None = None,
    hr: Sequence[Any] | None = None,
    speed: Sequence[Any] | None = None,
    dist: Sequence[Any] | None = None,
) -> dict[str, list[Any]]:
    """Die Spuren auf eine Zeitachse legen, beginnend bei null.

    Messpunkte ohne Zeitstempel fallen weg — ohne Zeit gibt es keine Achse.
    Fehlt einer Spur ein Wert, bleibt an dieser Stelle eine Lücke stehen; sie
    wird nicht durch den Nachbarn ersetzt.
    """
    stamps = list(time or [])
    out: dict[str, list[Any]] = {key: [] for key in CHANNELS}
    start: float | None = None
    for index in range(len(stamps)):
        stamp = _seconds(stamps[index])
        if stamp is None:
            continue
        if start is None:
            start = stamp
        out["t"].append(int(round(stamp - start)))
        out["watts"].append(_round(_at(watts, index)))
        out["hr"].append(_round(_at(hr, index)))
        out["speed"].append(_round(_at(speed, index), 2))
        out["dist"].append(_round(_at(dist, index), 1))
    if len(out["t"]) < 2:
        return {}
    return out


# ------------------------------------------------------------------ Verdichten


def compact(series: dict[str, list[Any]], seconds: int = BUCKET_S) -> dict[str, list[Any]]:
    """Auf feste Zeitfenster verdichten: Mittelwert je Spur, Lücken bleiben Lücken.

    Fünf Sekunden sind feiner als jeder Bildschirm und gröber als die
    Aufzeichnung: aus 6 700 Messpunkten eines Laufs werden rund 800 Zeilen.
    """
    stamps = series.get("t") or []
    if not stamps:
        return {}
    return _bucketed(series, [int(stamp) // seconds for stamp in stamps])


def downsample(series: dict[str, list[Any]], limit: int = MAX_POINTS) -> dict[str, list[Any]]:
    """Für den Bildschirm verdichten: höchstens `limit` Punkte."""
    stamps = series.get("t") or []
    if len(stamps) <= limit:
        return series
    size = math.ceil(len(stamps) / limit)
    return _bucketed(series, [index // size for index in range(len(stamps))])


def _bucketed(series: dict[str, list[Any]], slots: Sequence[int]) -> dict[str, list[Any]]:
    groups: dict[int, dict[str, list[float]]] = {}
    for index, slot in enumerate(slots):
        werte = groups.setdefault(int(slot), {})
        for key in CHANNELS:
            value = _at(series.get(key), index)
            if value is not None:
                werte.setdefault(key, []).append(float(value))

    out: dict[str, list[Any]] = {key: [] for key in CHANNELS}
    for slot in sorted(groups):
        werte = groups[slot]
        out["t"].append(_round(_mean(werte.get("t"))))
        out["watts"].append(_round(_mean(werte.get("watts"))))
        out["hr"].append(_round(_mean(werte.get("hr"))))
        out["speed"].append(_round(_mean(werte.get("speed")), 2))
        out["dist"].append(_round(_mean(werte.get("dist")), 1))
    return out


# ------------------------------------------------------------------ Anzeige


def payload(conn: Any, row: dict[str, Any]) -> dict[str, Any] | None:
    """Der Verlauf einer Einheit als das, was das Blatt zeichnet.

    Die Hauptlinie ist die Leistung beim Rad und das Tempo beim Lauf; der Puls
    läuft als zweite, ruhigere Linie mit. Gibt die Quelle keinen Verlauf her,
    kommt `None` zurück — dann bleibt das Blatt, wie es war.
    """
    series = db.stream_for(conn, int(row["id"]))
    if not series:
        return None
    sport = str(row.get("sport") or "")
    kind = _kind(sport, series)
    if kind is None:
        return None

    points = _points(downsample(series, MAX_POINTS), kind)
    if len(points) < 3:
        return None

    return {
        "kind": kind,
        "unit": UNITS[kind],
        "points": points,
        "mean": _mean_of(points, "v"),
        "peak": _peak_of(points, kind),
        "pulse": _mean_of(points, "hr") if kind != "hr" else None,
        "duration_s": int(points[-1]["t"] or 0),
        "reference": _ftp(conn, sport) if kind == "power" else None,
    }


def _kind(sport: str, series: dict[str, list[Any]]) -> str | None:
    family = plan.sport_family(sport)
    if family == "bike" and _filled(series, "watts", minimum=30):
        return "power"
    if family == "run" and _filled(series, "speed"):
        return "pace"
    if _filled(series, "hr"):
        return "hr"
    return None


def _filled(series: dict[str, list[Any]], key: str, minimum: float | None = None) -> bool:
    """Trägt diese Spur genug Werte, um sie zu zeichnen?"""
    values = [float(value) for value in (series.get(key) or []) if value is not None]
    stamps = len(series.get("t") or [])
    if len(values) < 3 or len(values) < stamps * 0.05:
        return False
    return minimum is None or max(values) >= minimum


def _points(series: dict[str, list[Any]], kind: str) -> list[dict[str, Any]]:
    """Die gezeichneten Punkte: Hauptwert und Puls je Zeitstempel."""
    stamps = series.get("t") or []
    channel = {"pace": "speed", "power": "watts"}.get(kind, "hr")
    values = series.get(channel) or []
    if kind == "pace":
        # Das Tempo aus dem GPS ist auf fünf Sekunden unruhig; über 20 s
        # gemittelt bleibt der Verlauf lesbar, ohne die Blöcke zu glätten.
        values = _moving(values, PACE_SMOOTH)
    hr = series.get("hr") or []
    points: list[dict[str, Any]] = []
    for index, stamp in enumerate(stamps):
        value = _at(values, index)
        if kind == "pace":
            # Tempo in Minuten je Kilometer; unter 2 km/h ist Gehen oder Stehen
            # und gehört nicht in die Achse.
            pace = 1000 / float(value) / 60 if value and float(value) > 0.55 else None
            value = _round(pace, 2) if pace is not None else None
        else:
            value = _round(value)
        pulse = _round(_at(hr, index)) if kind != "hr" else None
        if value is None and pulse is None:
            continue
        points.append({"t": int(stamp), "v": value, "hr": pulse})
    return points


def _mean_of(points: list[dict[str, Any]], key: str) -> float | None:
    werte = [float(point[key]) for point in points if point.get(key) is not None]
    return round(sum(werte) / len(werte), 1) if werte else None


def _peak_of(points: list[dict[str, Any]], kind: str) -> float | None:
    """Der höchste Wert der Hauptlinie. Beim Tempo ist das der schnellste."""
    werte = [float(point["v"]) for point in points if point.get("v") is not None]
    if not werte:
        return None
    return round(min(werte) if kind == "pace" else max(werte), 1)


def _ftp(conn: Any, sport: str) -> float | None:
    """Die Schwelle aus den Sport-Einstellungen — die Linie, an der gemessen wird."""
    profile = plan.sport_profiles(conn)
    entry = profile.get(sport)
    if not isinstance(entry, dict):
        family = plan.sport_family(sport)
        entry = next(
            (
                value
                for key, value in profile.items()
                if plan.sport_family(key) == family and isinstance(value, dict)
            ),
            None,
        )
    if not isinstance(entry, dict):
        return None
    order = ("indoor_ftp", "ftp") if sport.startswith("Virtual") else ("ftp", "indoor_ftp")
    for key in order:
        value = entry.get(key)
        if value:
            return float(value)
    return None


# ------------------------------------------------------------------ Nachladen


def fetch_missing(
    conn: Any,
    settings: Any,
    today: date | None = None,
    days: int = STREAM_DAYS,
) -> dict[str, int]:
    """Verläufe der letzten Tage holen, soweit sie fehlen.

    Ein Verlauf wird einmal geholt und liegt dann in der Datenbank. Einheiten
    ohne Sekundenwerte bekommen eine leere Reihe, damit sie nicht bei jedem Sync
    erneut abgefragt werden.
    """
    today = today or date.today()
    since = today - timedelta(days=max(days, 1))
    vorhanden = db.streams_between(conn, since, today)
    offen = [
        row for row in db.training_between(conn, since, today) if int(row["id"]) not in vorhanden
    ]
    counts = {"neu": 0, "leer": 0, "fehler": 0}

    aus_intervals = [row for row in offen if row.get("source") == "intervals"]
    aus_garmin = [row for row in offen if row.get("source") == "garmin"]
    if aus_intervals:
        counts = _from_intervals(conn, settings, aus_intervals, counts)
    if aus_garmin and settings.garmin_key:
        counts = _from_garmin(conn, settings, aus_garmin, counts)
    return counts


def _from_intervals(
    conn: Any, settings: Any, rows: list[dict[str, Any]], counts: dict[str, int]
) -> dict[str, int]:
    from .sources.intervals import IntervalsClient  # noqa: PLC0415 - Zyklus vermeiden

    client = IntervalsClient(
        settings.intervals_key or "", settings.intervals_athlete, settings.base_url
    )
    with client:
        for row in rows:
            try:
                series = series_from_intervals(client.streams(str(row["source_id"])))
            except Exception:  # noqa: BLE001 - eine Einheit ohne Verlauf ist kein Abbruch
                counts["fehler"] += 1
                continue
            counts["neu" if _store(conn, row, series) else "leer"] += 1
    return counts


def _from_garmin(
    conn: Any, settings: Any, rows: list[dict[str, Any]], counts: dict[str, int]
) -> dict[str, int]:
    from .sources.garmin import garmin_client  # noqa: PLC0415 - Paket nur bei Bedarf

    cache = settings.ensure_data_dir() / "garmin" / "bearer-token.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    try:
        with garmin_client(settings.garmin_key or "", token_cache=cache) as api:
            for row in rows:
                try:
                    payload = api.download_activity(int(row["source_id"]))
                    series = series_from_records(fit_records(payload))
                except Exception:  # noqa: BLE001 - eine Einheit ohne Verlauf ist kein Abbruch
                    counts["fehler"] += 1
                    continue
                counts["neu" if _store(conn, row, series) else "leer"] += 1
    except Exception:  # noqa: BLE001 - ohne Anmeldung gibt es nichts zu holen
        counts["fehler"] += len(rows)
    return counts


def _store(conn: Any, row: dict[str, Any], series: dict[str, list[Any]]) -> bool:
    kompakt = compact(series)
    db.upsert_stream(conn, int(row["id"]), kompakt, len(kompakt.get("t") or []))
    return bool(kompakt)


# ------------------------------------------------------------------ Werkzeug


def _at(values: Sequence[Any] | None, index: int) -> Any:
    if not values or index >= len(values):
        return None
    return values[index]


def _seconds(value: Any) -> float | None:
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _mean(values: list[float] | None) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _moving(values: Sequence[Any], window: int) -> list[Any]:
    """Gleitender Mittelwert über `window` Werte; Lücken bleiben Lücken."""
    if window < 2:
        return list(values)
    out: list[Any] = []
    for index in range(len(values)):
        nachbarn = [
            float(value)
            for value in values[max(0, index - window + 1) : index + 1]
            if value is not None
        ]
        out.append(round(sum(nachbarn) / len(nachbarn), 3) if nachbarn else None)
    return out


def _round(value: Any, digits: int = 0) -> float | int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, digits) if digits else int(round(number))
