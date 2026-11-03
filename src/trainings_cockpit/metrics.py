"""Metriken: Tagesreihen, Readiness, Wochen, Serien."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import mean, pstdev
from typing import Any

from . import db, plan

TARGET_SLEEP_H = 7.5
#: Referenzfenster für „üblich“: die letzten drei Wochen, nicht die letzten drei Monate.
#: Ein Sommer mit anderem Schlafrhythmus soll einen schlechten Oktober nicht abfedern.
BASELINE_DAYS = 21
#: Punkte je Standardabweichung. 20 war zu flach: eine Nacht mit 10 ms HRV-Verlust
#: bewegte den Score um 5 Punkte.
SCORE_PER_SD = 25.0
VALID_RANGES = {
    "hrv": (5.0, 200.0),
    "rhr": (30.0, 120.0),
    "sleep_s": (2 * 3600.0, 14 * 3600.0),
    "sleep_score": (0.0, 100.0),
    "respiration": (8.0, 20.0),
    "spo2": (90.0, 100.0),
    "weight_kg": (30.0, 200.0),
}
WEIGHTS = {"hrv": 35.0, "rhr": 20.0, "sleep": 30.0, "resp": 5.0, "spo2": 5.0}
#: Ein neuer Sensor misst anders. Nach einem Gerätewechsel beginnt die Referenz
#: neu, sonst mischt sie zwei Sensoren und zeigt eine Erholung, die es nicht gibt.
#: Der erste Wert kommt erst, wenn die Referenz vollständig ist (D-51): Mit sieben
#: Nächten ist der Maßstab um vier Score-Punkte unsicher, mit 21 um zwei — der
#: Unterschied zwischen "eine Zahl" und "eine belastbare Zahl".
REFERENCE_MIN_NIGHTS = BASELINE_DAYS
#: Ohne diese Signale gibt es keinen Score. SpO2 fehlt hier, weil es nur abzieht.
REQUIRED_SIGNALS = {
    "hrv": "die HRV",
    "rhr": "der Ruhepuls",
    "sleep": "der Schlaf",
    "resp": "die Atmung",
}
BANDS = (
    (70, "green", "Gut erholt"),
    (50, "amber", "Solide"),
    (35, "orange", "Erholungsbedarf"),
    (0, "red", "Ruhetag"),
)

BAND_SENTENCES = {
    "green": "Du bist heute gut erholt.",
    "amber": "Du bist heute solide erholt, aber nicht ganz frisch.",
    "orange": "Dein Körper zeigt Erholungsbedarf.",
    "red": "Du brauchst heute Erholung.",
}


@dataclass
class Day:
    day: date
    load: float = 0.0
    ctl: float | None = None
    atl: float | None = None
    hrv: float | None = None
    rhr: float | None = None
    sleep_h: float | None = None
    sleep_score: float | None = None
    respiration: float | None = None
    spo2: float | None = None
    tsb: float | None = None
    #: Score der Vergleichs-App (Bevel) für diesen Tag, von Hand eingetragen.
    vendor: float | None = None


# ---------------------------------------------------------------------- Tage


def daily_days(
    wellness: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    start: date,
    end: date,
) -> list[Day]:
    by_date = {str(w["date"]): w for w in wellness}
    loads: dict[str, float] = {}
    for activity in activities:
        loads[activity["date"]] = loads.get(activity["date"], 0.0) + (activity.get("load") or 0.0)

    out: list[Day] = []
    ctl = atl = 0.0
    saw_load = False
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        key = day.isoformat()
        wellness_row = by_date.get(key)
        load = loads.get(key, 0.0)
        saw_load = saw_load or load > 0

        ctl += (load - ctl) / 42
        atl += (load - atl) / 7

        # Fitness und Müdigkeit rechnet das Cockpit selbst. intervals' Tageswerte
        # kennen die Läufe nicht mehr, die über die Garmin-Personal-API kommen —
        # sie würden die Form ab dem Sensorwechsel systematisch zu niedrig zeigen.
        point = Day(
            day=day,
            load=round(load, 1),
            ctl=round(ctl, 1) if saw_load else None,
            atl=round(atl, 1) if saw_load else None,
            hrv=_num(wellness_row, "hrv", VALID_RANGES["hrv"]),
            rhr=_num(wellness_row, "rhr", VALID_RANGES["rhr"]),
            sleep_h=_hours(wellness_row, "sleep_s", VALID_RANGES["sleep_s"]),
            sleep_score=_num(wellness_row, "sleep_score", VALID_RANGES["sleep_score"]),
            respiration=_num(wellness_row, "respiration", VALID_RANGES["respiration"]),
            spo2=_num(wellness_row, "spo2", VALID_RANGES["spo2"]),
            vendor=_num(wellness_row, "readiness_vendor", (0.0, 100.0)),
        )
        if point.ctl is not None and point.atl is not None:
            point.tsb = round(point.ctl - point.atl, 1)
        out.append(point)
    return out


def _num(
    row: dict[str, Any] | None,
    key: str,
    bounds: tuple[float, float] | None = None,
) -> float | None:
    if not row:
        return None
    value = row.get(key)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if bounds and not (bounds[0] <= number <= bounds[1]):
        return None
    return number


def _hours(
    row: dict[str, Any] | None,
    key: str,
    bounds: tuple[float, float] | None = None,
) -> float | None:
    value = _num(row, key, bounds)
    if value is None or value <= 0:
        return None
    return round(value / 3600, 2)


# ----------------------------------------------------------------- Readiness


def reference_nights(days: list[Day], index: int, epoch: date | None) -> int | None:
    """Nächte mit mindestens einem Signal seit dem Sensorwechsel."""
    if epoch is None:
        return None
    return sum(
        1
        for d in days[: index + 1]
        if d.day >= epoch
        and (d.hrv is not None or d.rhr is not None or d.sleep_h is not None or d.respiration is not None)
    )


def compute_recovery(
    days: list[Day], index: int, epoch: date | None = None
) -> dict[str, Any]:
    """Erholung nach Nachtsignalen.

    HRV und Ruhepuls gegen die eigene 21-Tage-Referenz, Schlaf aus Dauer und
    Score, Atmung leichtgewichtig, SpO2 nur als Abzug. Training zählt nicht
    direkt. Die Nacht zählt voll – der Vergleich mit dem eigenen Üblichen glättet
    genug, eine zweite Glättung über den Wochenschnitt hat den Score zu träge
    gemacht.
    """
    window = days[max(0, index - 6) : index + 1]
    current = days[index]
    components: list[dict[str, Any]] = []

    nights = reference_nights(days, index, epoch)
    if nights is not None and nights < REFERENCE_MIN_NIGHTS:
        fehlt = REFERENCE_MIN_NIGHTS - nights
        return {
            "score": None,
            "band": "unknown",
            "label": "Referenz wird aufgebaut",
            "confidence": 0.0,
            "components": [],
            "missing": [],
            "reference": {
                "nights": nights,
                "minimum": REFERENCE_MIN_NIGHTS,
                "target": BASELINE_DAYS,
                "average": None,
            },
            "explanation": (
                f"Neuer Sensor: die Referenz beginnt neu. "
                f"{nights} von {REFERENCE_MIN_NIGHTS} Nächten sind da, "
                f"noch {fehlt} bis zum ersten Wert."
            ),
        }


    hrv = _component(
        key="hrv",
        label="HRV",
        unit="ms",
        today=current.hrv,
        window=[d.hrv for d in window],
        baseline=_baseline(days, index, "hrv", epoch),
        invert=False,
        weight=WEIGHTS["hrv"],
    )
    if hrv:
        components.append(hrv)

    rhr = _component(
        key="rhr",
        label="Ruhepuls",
        unit="bpm",
        today=current.rhr,
        window=[d.rhr for d in window],
        baseline=_baseline(days, index, "rhr", epoch),
        invert=True,
        weight=WEIGHTS["rhr"],
    )
    if rhr:
        components.append(rhr)

    sleep_values = [d.sleep_h for d in window if d.sleep_h is not None]
    if current.sleep_h is not None and sleep_values:
        today_sleep = current.sleep_h
        average_sleep = mean(sleep_values)
        blend = today_sleep
        debt = sum(max(0.0, TARGET_SLEEP_H - h) for h in sleep_values)
        duration_score = max(
            0.0, min(100.0, 100 * blend / TARGET_SLEEP_H - min(25.0, debt * 4))
        )
        vendor = current.sleep_score
        score = 0.5 * duration_score + 0.5 * vendor if vendor is not None else duration_score
        components.append(
            {
                "key": "sleep",
                "label": "Schlaf",
                "score": round(score),
                "today": round(today_sleep, 2),
                "average": round(average_sleep, 2),
                "baseline": TARGET_SLEEP_H,
                "unit": "h",
                "weight": WEIGHTS["sleep"],
                "date": current.day.isoformat(),
                "z": None,
                "vendor": vendor,
            }
        )

    respiration = _component(
        key="resp",
        label="Atmung",
        unit="/min",
        today=current.respiration,
        window=[d.respiration for d in window],
        baseline=_baseline(days, index, "respiration", epoch),
        invert=True,
        weight=WEIGHTS["resp"],
    )
    if respiration:
        components.append(respiration)

    spo2 = _spo2_component(days, index, window, epoch)
    if spo2:
        components.append(spo2)

    # Ein Score entsteht nur, wenn alle gewichteten Signale von heute vorliegen.
    # Ein halber Wert wäre eine Zahl, die mehr weiß, als die Daten hergeben.
    fehlend = [
        name for key, name in REQUIRED_SIGNALS.items() if key not in {c["key"] for c in components}
    ]
    if fehlend:
        if len(fehlend) == 1:
            text = f"Für heute fehlt noch {fehlend[0]}."
        else:
            text = f"Für heute fehlen noch {', '.join(fehlend[:-1])} und {fehlend[-1]}."
        return {
            "score": None,
            "band": "unknown",
            "label": "Keine Daten",
            "confidence": 0.0,
            "components": [],
            "missing": fehlend,
            "explanation": f"{text} Ein Erholungswert entsteht erst, wenn alle Werte da sind.",
        }

    total_weight = sum(component["weight"] for component in components)
    score = sum(c["score"] * c["weight"] for c in components) / total_weight
    band, label = _band(score)

    return {
        "score": round(score),
        "band": band,
        "label": label,
        # Alle Pflichtsignale sind da, sonst gäbe es diesen Zweig nicht.
        "confidence": 1.0,
        "components": components,
        "reference": (
            None
            if nights is None
            else {
                "nights": nights,
                "minimum": REFERENCE_MIN_NIGHTS,
                "target": BASELINE_DAYS,
                "average": None,
            }
        ),
        "explanation": _explanation(band, components, current.day),
    }


def _component(
    *,
    key: str,
    label: str,
    unit: str,
    today: float | None,
    window: list[float | None],
    baseline: list[float] | None,
    invert: bool,
    weight: float,
    value_date: str | None = None,
) -> dict[str, Any] | None:
    values = [v for v in window if v is not None]
    if not values or not baseline or len(baseline) < 7:
        return None

    if today is None:
        # Nur die Nacht von heute zählt. Fehlt sie, fehlt das Signal – lieber
        # eine Lücke als ein Wert von gestern, der wie heute aussieht.
        return None
    average = mean(values)
    base = mean(baseline)
    spread = max(pstdev(baseline), 1.0)
    z = (today - base) / spread
    if invert:
        z = -z
    z = max(-2.5, min(2.5, z))
    score = max(0.0, min(100.0, 68 + SCORE_PER_SD * z))

    return {
        "key": key,
        "label": label,
        "score": round(score),
        "today": round(today, 1),
        "average": round(average, 1),
        "baseline": round(base, 1),
        "unit": unit,
        "weight": weight,
        "date": value_date,
        "z": round(z, 2),
    }


def _spo2_component(
    days: list[Day], index: int, window: list[Day], epoch: date | None = None
) -> dict[str, Any] | None:
    """SpO2 zählt nur als Abzug, nie als Bonus."""
    today = days[index].spo2
    baseline = _baseline(days, index, "spo2", epoch)
    if today is None or not baseline:
        return None
    base = mean(baseline)
    if today >= 95 and today > base - 2:
        return None

    values = [d.spo2 for d in window if d.spo2 is not None]
    penalty = 100 - (95 - today) * 8 - max(0.0, base - today) * 4
    return {
        "key": "spo2",
        "label": "SpO₂",
        "score": round(max(0.0, min(100.0, penalty))),
        "today": round(today),
        "average": round(mean(values)) if values else round(today),
        "baseline": round(base),
        "unit": "%",
        "weight": WEIGHTS["spo2"],
        "z": None,
    }


def _baseline(
    days: list[Day], index: int, field: str, epoch: date | None = None
) -> list[float] | None:
    values = [
        getattr(d, field)
        for d in days[max(0, index - BASELINE_DAYS) : index]
        if getattr(d, field) is not None and (epoch is None or d.day >= epoch)
    ]
    return values if len(values) >= 7 else None


def _band(score: float) -> tuple[str, str]:
    for threshold, band, label in BANDS:
        if score >= threshold:
            return band, label
    return "red", "Ruhetag"


def _explanation(
    band: str, components: list[dict[str, Any]], day: date | None = None
) -> str:
    by_key = {component["key"]: component for component in components}
    sentences: list[str] = [BAND_SENTENCES.get(band, "")]

    hrv = by_key.get("hrv")
    if hrv:
        direction = "über" if hrv["today"] >= hrv["average"] else "unter"
        sentences.append(
            f"Deine HRV liegt mit {_de(hrv['today'])} ms {direction} deinem Schnitt "
            f"von {_de(hrv['average'])} ms (üblich {_de(hrv['baseline'])})."
        )

    rhr = by_key.get("rhr")
    if rhr:
        direction = "über" if rhr["today"] > rhr["average"] else "unter"
        sentences.append(
            f"Der Ruhepuls liegt mit {_de(rhr['today'])} bpm {direction} deinem "
            f"Schnitt von {_de(rhr['average'])} bpm."
        )

    sleep = by_key.get("sleep")
    if sleep:
        vendor = sleep.get("vendor")
        score_text = f" (Schlafscore {_de(vendor)})" if vendor is not None else ""
        sentences.append(f"Du hast {_duration(sleep['today'])} geschlafen{score_text}.")

    # Atmung fließt in den Score, wird aber nicht mehr erzählt: der Athlet
    # will sie nicht in der Oberfläche sehen.

    spo2 = by_key.get("spo2")
    if spo2:
        sentences.append(
            f"Die Sauerstoffsättigung lag mit {_de(spo2['today'])} % unter deinem "
            f"üblichen Wert von {_de(spo2['baseline'])} %."
        )

    return " ".join(sentence for sentence in sentences if sentence)


def _de(value: float, digits: int = 0) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _signed(value: float) -> str:
    if value > 0:
        return f"+{value:.0f}"
    if value < 0:
        return f"−{abs(value):.0f}"
    return "0"


def _duration(hours: float) -> str:
    total = round(hours * 60)
    return f"{total // 60}:{total % 60:02d} h"


def recovery_series(days: list[Day]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for index in range(len(days)):
        result = compute_recovery(days, index)
        if result["score"] is None:
            continue
        out.append(
            {
                "date": days[index].day.isoformat(),
                "score": result["score"],
                "vendor": days[index].vendor,
            }
        )
    return out


def build_weeks(conn: Any, weeks: int = 8, today: date | None = None) -> list[dict[str, Any]]:
    """Wochenübersicht direkt aus der Datenbank.

    Ersetzt die Wochen-Notizen im Vault: dieselben Zahlen, nur tagesaktuell und
    ohne dass jemand eine Datei pflegen muss.
    """
    today = today or date.today()
    start = today - timedelta(days=weeks * 7 + 7)
    rows = db.training_between(conn, start, today)
    buckets: dict[date, dict[str, Any]] = {}

    for row in rows:
        try:
            tag = date.fromisoformat(row["date"])
        except (KeyError, ValueError):
            continue
        montag = tag - timedelta(days=tag.weekday())
        bucket = buckets.setdefault(
            montag,
            {
                "montag": montag,
                "lauf_km": 0.0,
                "rad_km": 0.0,
                "sonst_min": 0.0,
                "einheiten": 0,
                "dauer_h": 0.0,
                "langer_lauf_km": 0.0,
                "hoehenmeter_m": 0.0,
            },
        )
        sport = row.get("sport") or ""
        km = (row.get("distance_m") or 0) / 1000
        stunden = (row.get("moving_s") or row.get("duration_s") or 0) / 3600
        bucket["einheiten"] += 1
        bucket["dauer_h"] += stunden
        bucket["hoehenmeter_m"] += row.get("elevation_m") or 0
        if sport in ("Run", "VirtualRun", "TrailRun"):
            bucket["lauf_km"] += km
            bucket["langer_lauf_km"] = max(bucket["langer_lauf_km"], km)
        elif sport in ("Ride", "VirtualRide", "EBikeRide"):
            bucket["rad_km"] += km
        else:
            bucket["sonst_min"] += stunden * 60

    out: list[dict[str, Any]] = []
    for montag in sorted(buckets)[-weeks:]:
        b = buckets[montag]
        out.append(
            {
                "kw": f"KW {montag.isocalendar()[1]:02d}",
                "von": montag.isoformat(),
                "bis": (montag + timedelta(days=6)).isoformat(),
                "lauf_km": round(b["lauf_km"], 1),
                "rad_km": round(b["rad_km"], 1),
                "sonst_min": round(b["sonst_min"]),
                "einheiten": b["einheiten"],
                "dauer_h": round(b["dauer_h"], 1),
                "langer_lauf_km": round(b["langer_lauf_km"], 1),
                "hoehenmeter_m": round(b["hoehenmeter_m"]),
            }
        )
    return out


def week_summaries(
    days: list[Day], activities: list[dict[str, Any]], weeks: int
) -> list[dict[str, Any]]:
    buckets: dict[tuple[int, int], dict[str, Any]] = {}
    for activity in activities:
        try:
            day = date.fromisoformat(activity["date"])
        except (ValueError, KeyError):
            continue
        iso = day.isocalendar()
        key = (iso.year, iso.week)
        bucket = buckets.setdefault(
            key,
            {
                "year": iso.year,
                "week": iso.week,
                "label": f"KW {iso.week:02d}",
                "hours": 0.0,
                "load": 0.0,
                "sessions": 0,
                "by_sport": {},
            },
        )
        hours = (activity.get("moving_s") or activity.get("duration_s") or 0) / 3600
        bucket["hours"] += hours
        bucket["load"] += activity.get("load") or 0
        bucket["sessions"] += 1
        sport = activity.get("sport") or "Other"
        bucket["by_sport"][sport] = bucket["by_sport"].get(sport, 0.0) + hours

    ordered = [buckets[k] for k in sorted(buckets)]
    for bucket in ordered:
        bucket["hours"] = round(bucket["hours"], 1)
        bucket["load"] = round(bucket["load"], 0)
        bucket["by_sport"] = {k: round(v, 1) for k, v in bucket["by_sport"].items()}
    return ordered[-weeks:]


# ---------------------------------------------------------------- Aktivitäten


SPORT_LABELS = plan.SPORT_LABELS


def activity_payload(row: dict[str, Any]) -> dict[str, Any]:
    moving = row.get("moving_s") or row.get("duration_s") or 0
    distance = row.get("distance_m") or 0
    pace_min_km = None
    speed_kmh = None
    if distance > 0 and moving > 0:
        speed_kmh = round(distance / 1000 / (moving / 3600), 1)
        if row.get("sport") in {"Run", "VirtualRun", "Walk", "Hike"}:
            pace_min_km = round((moving / 60) / (distance / 1000), 2)
    return {
        "id": row["source_id"],
        "row_id": row["id"],
        "date": row["date"],
        "start": row["start_local"],
        "sport": row["sport"],
        "sport_label": SPORT_LABELS.get(row["sport"], row["sport"]),
        "name": row.get("name") or "",
        "duration_min": round(moving / 60) if moving else None,
        "total_min": round((row.get("duration_s") or moving) / 60) if moving else None,
        "distance_km": round(distance / 1000, 2) if distance else None,
        "avg_hr": row.get("avg_hr"),
        "max_hr": row.get("max_hr"),
        "load": row.get("load"),
        "intensity": round(row["intensity"]) if row.get("intensity") else None,
        "pace_min_km": pace_min_km,
        "speed_kmh": speed_kmh,
    }


#: Wie eine Aufzeichnung entstanden ist. Der Quellenname in den Rohdaten sagt,
#: über welchen Weg die Einheit in intervals kam.
ORIGINS = {
    "WAHOO": "Wahoo",
    "OAUTH_CLIENT": "Health Sync",
    "GARMIN_CONNECT": "Garmin Connect",
    "ZEPP": "Zepp",
    "STRAVA": "Strava",
}


def zone_seconds(raw: dict[str, Any]) -> list[float]:
    """Zeit je Herzfrequenzzone, so wie die Quelle sie führt.

    intervals liefert `icu_hr_zone_times` (fünf bis sieben Zonen), Garmin
    `hrTimeInZone_1…5`. Beides ist die Verteilung der Aufzeichnung selbst — sie
    liegt schon in der Datenbank, es muss nichts nachgeladen werden.
    """
    intervals = raw.get("icu_hr_zone_times")
    if isinstance(intervals, list) and intervals:
        return [float(value or 0) for value in intervals]
    garmin = [raw.get(f"hrTimeInZone_{index}") for index in range(1, 6)]
    if any(value is not None for value in garmin):
        return [float(value or 0) for value in garmin]
    return []


def unit_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Eine erledigte Einheit mit dem, was die Aufzeichnung weiß.

    Kein Verlaufsprofil: die Datenbank hält keine Sekundenwerte, ein gezeichneter
    Verlauf wäre erfunden. Was sie hält, ist die Zeit je Zone — die einzige
    echte Verteilung, die ohne einen weiteren Abruf auskommt.
    """
    raw: dict[str, Any] = {}
    if row.get("raw"):
        try:
            geladen = json.loads(row["raw"])
        except ValueError:
            geladen = None
        if isinstance(geladen, dict):
            raw = geladen

    base = activity_payload(row)
    zones = zone_seconds(raw)
    total_zones = sum(zones)
    distance = row.get("distance_m") or 0
    moving = row.get("moving_s") or row.get("duration_s") or 0
    family = plan.sport_family(row.get("sport"))
    return {
        **base,
        "elevation_m": round(row["elevation_m"]) if row.get("elevation_m") else None,
        "calories": round(row["calories"]) if row.get("calories") else None,
        "pace_100m": (
            round((moving / 60) / (distance / 100), 1)
            if family == "swim" and distance > 0 and moving > 0
            else None
        ),
        "origin": "Garmin" if row.get("source") == "garmin" else ORIGINS.get(str(raw.get("source")), "intervals.icu"),
        "zones": [
            {"zone": index + 1, "seconds": int(seconds), "share": round(seconds / total_zones, 4)}
            for index, seconds in enumerate(zones)
        ]
        if total_zones
        else [],
        "zone_source": ("Garmin" if not raw.get("icu_hr_zone_times") else "intervals.icu")
        if total_zones
        else None,
    }


# ------------------------------------------------------------------ Overview


def build_overview(conn: Any, today: date | None = None, days: int = 90) -> dict[str, Any]:
    today = today or date.today()
    history_start = today - timedelta(days=days + 90)

    wellness = db.wellness_between(conn, history_start, today)
    activities = db.training_between(conn, history_start, today)
    series_days = daily_days(wellness, activities, history_start, today)

    epoch = db.wellness_epoch(conn)
    recovery = compute_recovery(series_days, len(series_days) - 1, epoch)
    current = series_days[-1] if series_days else None

    # Die Nachtsignale kommen mit dem Sync des Tages. Liegt für heute noch nichts
    # vor, zeigen die Karten den letzten Stand statt "—" – sonst steht jeden
    # Morgen vor dem Sync ein leerer Bildschirm neben einem vollen Ring.
    latest = current

    window_start = today - timedelta(days=days - 1)
    load_series = [
        {
            "date": d.day.isoformat(),
            "load": d.load,
            "ctl": d.ctl,
            "atl": d.atl,
            "tsb": d.tsb,
        }
        for d in series_days
        if d.day >= window_start
    ]

    hrv_start = today - timedelta(days=59)
    hrv_series = []
    for index, d in enumerate(series_days):
        if d.day < hrv_start:
            continue
        baseline = _baseline(series_days, index, "hrv")
        hrv_series.append(
            {
                "date": d.day.isoformat(),
                "hrv": d.hrv,
                "rhr": d.rhr,
                "baseline": round(mean(baseline), 1) if baseline else None,
            }
        )

    sleep_start = today - timedelta(days=29)
    sleep_series = [
        {"date": d.day.isoformat(), "hours": d.sleep_h, "score": d.sleep_score}
        for d in series_days
        if d.day >= sleep_start
    ]

    recovery_points = [
        p for p in recovery_series(series_days) if p["date"] >= window_start.isoformat()
    ]

    # 21-Tage-Schnitt der Scores – nach einem Sensorwechsel nur die Nächte
    # seit dem Wechsel, sonst stünde der neue Wert neben einem alten Maßstab.
    if (recovery.get("reference") or {}).get("nights", 0) >= REFERENCE_MIN_NIGHTS:
        since = epoch.isoformat() if epoch else None
        recent = [
            point["score"]
            for point in recovery_points[-BASELINE_DAYS:]
            if point.get("score") is not None and (since is None or point["date"] >= since)
        ]
        recovery["reference"]["average"] = round(mean(recent)) if recent else None

    # Die letzten sieben Tage: heute und die sechs davor. Ein rollierendes
    # Fenster, keine Kalenderwoche — sonst springt der Wert am Montag.
    week_from = (today - timedelta(days=6)).isoformat()
    week_acts = [a for a in activities if week_from <= a["date"] <= today.isoformat()]
    week_seconds = sum((a.get("moving_s") or a.get("duration_s") or 0) for a in week_acts)
    week_hours = week_seconds / 3600
    week_load = sum(a.get("load") or 0 for a in week_acts)

    load_7 = sum(d.load for d in series_days if d.day > today - timedelta(days=7))
    load_28 = sum(d.load for d in series_days if d.day > today - timedelta(days=28))
    acwr = round(load_7 / (load_28 / 4), 2) if load_28 > 0 else None

    recent = [activity_payload(r) for r in db.recent_activities(conn, 12)]
    upcoming = db.upcoming_events(conn, today, 3)

    # Die Einheiten, um die es heute und morgen geht. Eine Schätzung braucht
    # alle Aktivitäten der letzten Monate — die Mediane werden einmal gerechnet.
    speeds_kmh = plan.speeds(conn, today=today)
    sessions = [
        {"day": day, **plan.session_row(conn, event, speeds_kmh)}
        for day, events in (
            ("today", db.events_on(conn, today)),
            ("tomorrow", db.events_on(conn, today + timedelta(days=1))),
        )
        for event in events
    ]

    # Was heute dazukam, ohne im Plan zu stehen: eine Kraft-Einheit am Morgen
    # gehört auf dieselbe Karte wie der geplante Lauf am Abend — sonst fehlt
    # sie dort, obwohl sie in der Woche zählt.
    unplanned = [plan.done_row(row) for row in plan.unplanned(conn, today)]

    return {
        "athlete": {
            "name": db.get_setting(conn, "athlete_name") or "Athlet",
            "id": db.get_setting(conn, "athlete_id") or "",
        },
        # Mit Zeitzone: die Oberfläche zeigt sonst die Uhr des Containers (UTC),
        # während der Athlet in Wien auf dieselbe Minute schaut.
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "today": {
            "date": today.isoformat(),
            "recovery": recovery,
            "as_of": latest.day.isoformat() if latest else None,
            "vendor": latest.vendor if latest else None,
            "sleep": {
                "hours": latest.sleep_h if latest else None,
                "score": latest.sleep_score if latest else None,
                "debt_7d": _sleep_debt([d for d in series_days if d.sleep_h is not None][-7:]),
                "baseline_hours": TARGET_SLEEP_H,
            },
            "load": {
                "ctl": current.ctl if current else None,
                "atl": current.atl if current else None,
                "tsb": current.tsb if current else None,
                "acwr": acwr,
                "week_seconds": int(week_seconds),
                "week_hours": round(week_hours, 1),
                "week_load": round(week_load),
                "week_sessions": len(week_acts),
            },
            "hrv": {
                "value": latest.hrv if latest else None,
                "average": _recent_average(series_days, "hrv"),
                "baseline": _today_baseline(series_days, "hrv"),
                "status": _hrv_status(series_days),
            },
            "rhr": {
                "value": latest.rhr if latest else None,
                "average": _recent_average(series_days, "rhr"),
                "baseline": _today_baseline(series_days, "rhr"),
            },
        },
        "series": {
            "load": load_series,
            "hrv": hrv_series,
            "sleep": sleep_series,
            "recovery": recovery_points,
        },
        "sessions": sessions,
        "unplanned": unplanned,
        "weeks": week_summaries(series_days, activities, 12),
        "activities": recent,
        "upcoming": [
            {
                "date": e["date"],
                "sport": e["sport"],
                "sport_label": SPORT_LABELS.get(e["sport"] or "", e["sport"] or ""),
                "name": e["name"],
                "load": e["load"],
                "duration_min": round((e["duration_s"] or 0) / 60) or None,
            }
            for e in upcoming
        ],
    }


def _recent_average(days: list[Day], field: str, window: int = 7) -> float | None:
    values = [getattr(d, field) for d in days[-window:] if getattr(d, field) is not None]
    return round(mean(values), 1) if values else None


def _sleep_debt(days: list[Day]) -> float:
    """Fehlende Nächte zählen nicht als null Stunden Schlaf."""
    values = [d.sleep_h for d in days if d.sleep_h is not None]
    return round(sum(max(0.0, TARGET_SLEEP_H - hours) for hours in values), 1)


def _today_baseline(days: list[Day], field: str) -> float | None:
    baseline = _baseline(days, len(days) - 1, field)
    return round(mean(baseline), 0) if baseline else None


def _hrv_status(days: list[Day]) -> str:
    baseline = _baseline(days, len(days) - 1, "hrv")
    recent = [d.hrv for d in days[-7:] if d.hrv is not None]
    if not baseline or not recent:
        return "keine Daten"
    spread = max(pstdev(baseline), 1.0)
    z = (mean(recent) - mean(baseline)) / spread
    if z > 0.5:
        return "über Baseline"
    if z < -0.5:
        return "unter Baseline"
    return "ausgeglichen"
