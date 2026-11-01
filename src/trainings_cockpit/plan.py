"""Was eine geplante Einheit verlangt — aus dem Plan von intervals.icu.

Der Plan liegt seit dem Sync als Roh-JSON in `event.raw`. Darin steht, was zu
tun ist: `workout_doc.steps` mit Leistungs-, HF- oder Distanzzielen, dazu
`zoneTimes` und `average_watts`. Was fehlt, ist die andere Hälfte jeder Einheit:
wie lange man unterwegs ist, wenn nur eine Distanz dasteht — oder wie weit man
kommt, wenn nur die Zeit dasteht. Diese Zahl wird **geschätzt**, aus den eigenen
Medianen der letzten 90 Tage, und trägt in der Oberfläche ein ≈.

Kein Coach-Text: was hier entsteht, ist der Plan selbst, die Verpflegung dazu
und bei erledigten Einheiten der Vergleich mit der Aufzeichnung.
"""

from __future__ import annotations

import json
import statistics
from datetime import date, timedelta
from typing import Any

from . import db, fuel

#: Sportarten, die sich dieselbe Geschwindigkeit teilen.
SPORT_FAMILY = {
    "Ride": "bike",
    "VirtualRide": "bike",
    "EBikeRide": "bike",
    "GravelRide": "bike",
    "MountainBikeRide": "bike",
    "Run": "run",
    "VirtualRun": "run",
    "TrailRun": "run",
    "Swim": "swim",
    "OpenWaterSwim": "swim",
}

#: Fallback, wenn die Datenbank zu einer Familie nichts hergibt. Die Werte sind
#: die eigenen Mediane aus August bis Oktober 2026 (Rad 23,7 · Lauf 8,6 ·
#: Schwimmen 2,6 km/h), gerundet.
FALLBACK_KMH = {"bike": 24.0, "run": 8.6, "swim": 2.6}

FAMILY_LABEL = {"bike": "Rad", "run": "Lauf", "swim": "Schwimmen"}

#: Worauf sich ein Prozentziel bezieht.
UNIT_LABEL = {"ftp": "FTP", "hr": "HF", "pace": "Pace", None: ""}

SPORT_LABELS = {
    "Run": "Laufen",
    "VirtualRun": "Laufen (indoor)",
    "Ride": "Rad",
    "VirtualRide": "Rad (indoor)",
    "Swim": "Schwimmen",
    "OpenWaterSwim": "Freiwasser",
    "WeightTraining": "Kraft",
    "Workout": "Workout",
    "Walk": "Gehen",
    "Hike": "Wandern",
    "HighIntensityIntervalTraining": "HIIT",
    "Transition": "Wechsel",
}

#: Zonen als Prozent der Schwelle, wenn der Plan eine Zone statt eines Bandes nennt.
HR_ZONES = {1: (50, 60), 2: (60, 70), 3: (70, 80), 4: (80, 90), 5: (90, 100), 6: (100, 110), 7: (110, 130)}


def sport_family(sport: str | None) -> str | None:
    return SPORT_FAMILY.get(sport or "")


def sport_profiles(conn: Any) -> dict[str, dict[str, Any]]:
    """Max-HF, Zonengrenzen und FTP je Sportart, wie intervals.icu sie führt.

    Die Prozente im Plan sind Prozent der maximalen Herzfrequenz oder der
    Schwelle. Ohne diese Zahlen bliebe nur das Prozentzeichen; mit ihnen steht
    dort, was auf der Uhr steht. Fehlt das Profil (noch kein Sync), bleibt es
    beim Prozentwert.
    """
    raw = db.get_setting(conn, "sport_profile") or db.get_setting(conn, "hr_profile")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _profile_for(profile: dict[str, dict[str, Any]], sport: str | None) -> dict[str, Any] | None:
    if not profile:
        return None
    entry = profile.get(sport or "")
    if isinstance(entry, dict):
        return entry
    family = sport_family(sport)
    for key, value in profile.items():
        if sport_family(key) == family and isinstance(value, dict):
            return value
    return None


def _to_bpm(target: dict[str, Any], entry: dict[str, Any] | None) -> dict[str, Any]:
    """Ein Prozentziel in Schläge übersetzen. Ohne Profil bleibt es Prozent."""
    # Nur Herzfrequenz-Prozente werden zu Schlägen; Prozent der Schwelle (FTP)
    # und Prozent des Tempos bleiben, was sie sind.
    if not entry or target["unit"] != "%" or target.get("basis") != "hr":
        return target
    max_hr = entry.get("max_hr")
    zones = entry.get("zones") or []
    label = target.get("label") or ""
    if label.startswith("Z") and label[1:].isdigit() and zones:
        number = int(label[1:])
        if 1 <= number <= len(zones):
            high = float(zones[number - 1])
            # Die untere Grenze von Zone 1 steht in keiner Liste; intervals rechnet
            # sie ab der halben Maximalfrequenz.
            low = float(zones[number - 2]) if number >= 2 else float(round((max_hr or zones[0]) * 0.5))
            return {**target, "lo": low, "hi": high, "unit": "bpm"}
    if max_hr:
        low = float(round(max_hr * target["lo"] / 100))
        high = float(round(max_hr * target["hi"] / 100))
        return {**target, "lo": low, "hi": high, "unit": "bpm"}
    return target


def _to_watts(target: dict[str, Any], entry: dict[str, Any] | None, sport: str | None) -> dict[str, Any]:
    """Prozent der Schwelle in Watt übersetzen. Ohne FTP bleibt es Prozent."""
    if not entry or target["unit"] != "%" or target.get("basis") != "ftp":
        return target
    # Drinnen gilt die FTP des Ergometers, draußen die Straßen-FTP.
    ftp = entry.get("ftp")
    if str(sport or "").startswith("Virtual") and entry.get("indoor_ftp"):
        ftp = entry["indoor_ftp"]
    if not ftp:
        return target
    low = float(round(ftp * target["lo"] / 100))
    high = float(round(ftp * target["hi"] / 100))
    return {**target, "lo": low, "hi": high, "unit": "W", "label": None}


def speeds(conn: Any, days: int = 180, today: date | None = None) -> dict[str, float]:
    """Median-Geschwindigkeit je Familie aus den eigenen Aktivitäten (km/h)."""
    end = today or date.today()
    start = end - timedelta(days=days)
    rows = conn.execute(
        """
        SELECT sport, moving_s, distance_m FROM activity
        WHERE date BETWEEN ? AND ? AND moving_s > 900 AND distance_m > 0
          AND sport NOT LIKE 'Virtual%' 
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchall()

    buckets: dict[str, list[float]] = {}
    for row in rows:
        family = sport_family(row["sport"])
        if not family:
            continue
        speed = (row["distance_m"] / 1000) / (row["moving_s"] / 3600)
        # Alles außerhalb dieser Spanne ist ein Datenfehler, kein Tempo.
        if 1 <= speed <= 80:
            buckets.setdefault(family, []).append(speed)

    out = dict(FALLBACK_KMH)
    for family, values in buckets.items():
        if len(values) >= 3:
            out[family] = round(statistics.median(values), 1)
    return out


# ------------------------------------------------------------------ Schritte


def _target(step: dict[str, Any]) -> dict[str, Any] | None:
    """Ziel eines Schritts als Band: Wert, Einheit und Spanne."""
    power = step.get("power")
    if isinstance(power, dict):
        units = str(power.get("units") or "w").lower()
        start, end = power.get("start"), power.get("end")
        if str(power.get("units") or "").lower() in {"%ftp", "%"}:
            return _band(start, end, "%", None, "ftp")
        if start is None and end is None:
            return None
        return _band(start, end, "W", None, "ftp")

    hr = step.get("hr")
    if isinstance(hr, dict):
        units = str(hr.get("units") or "").lower()
        if units == "hr_zone":
            zone = int(hr.get("value") or 0)
            low, high = HR_ZONES.get(zone, (60, 70))
            return _band(low, high, "%", f"Z{zone}", "hr")
        return _band(hr.get("start"), hr.get("end"), "%", None, "hr")

    pace = step.get("pace")
    if isinstance(pace, dict):
        units = str(pace.get("units") or "").lower()
        start, end = pace.get("start"), pace.get("end")
        if units in {"%pace", "%"}:
            return _band(start, end, "%", None, "pace")
        return _band(start, end, "min/km", None, "pace")
    return None


def _band(
    start: Any, end: Any, unit: str, label: str | None, basis: str | None = None
) -> dict[str, Any] | None:
    if start is None and end is None:
        return None
    low = float(start if start is not None else end)
    high = float(end if end is not None else start)
    if low > high:
        low, high = high, low
    return {"lo": low, "hi": high, "unit": unit, "label": label, "basis": basis}


def _target_text(target: dict[str, Any] | None, distance_m: float | None) -> str:
    parts: list[str] = []
    if distance_m:
        km = distance_m / 1000
        parts.append(f"{km:.1f} km".replace(".", ","))
    if target:
        if target["unit"] == "bpm":
            parts.append(f"{target['lo']:.0f}–{target['hi']:.0f} bpm")
        elif target["label"]:
            parts.append(target["label"])
        elif target["unit"] == "W":
            parts.append(f"{target['lo']:.0f}–{target['hi']:.0f} W")
        elif target["unit"] == "%":
            parts.append(f"{target['lo']:.0f}–{target['hi']:.0f} % {UNIT_LABEL.get(target['basis'] or '', '')}".strip())
        elif target["unit"] == "min/km":
            parts.append(f"{target['lo']:.2f}–{target['hi']:.2f} min/km")
    return " · ".join(parts)


def _flatten(steps: list[dict[str, Any]], out: list[dict[str, Any]], depth: int = 0) -> None:
    if depth > 4:
        return
    for step in steps:
        if not isinstance(step, dict):
            continue
        if isinstance(step.get("steps"), list) and step["steps"]:
            reps = int(step.get("reps") or 1)
            for _ in range(max(1, min(reps, 30))):
                _flatten(step["steps"], out, depth + 1)
            continue
        duration = step.get("duration") or 0
        distance = step.get("distance") or 0
        if not duration and not distance:
            continue
        target = _target(step)
        out.append(
            {
                "seconds": float(duration or 0),
                "distance_m": float(distance or 0),
                "text": str(step.get("text") or ""),
                "target": target,
                "target_text": _target_text(target, distance or None),
                "warmup": bool(step.get("warmup")),
                "cooldown": bool(step.get("cooldown")),
            }
        )


def _nice_ticks(low: float, high: float, unit: str) -> list[int]:
    """Drei oder vier runde Marken für die Achse."""
    if unit == "W":
        candidates = (10, 20, 25, 50, 100)
    elif unit == "bpm":
        candidates = (5, 10, 15, 20, 25)
    else:
        candidates = (2, 5, 10, 20)
    for step in candidates:
        first = int(-(-low // step) * step)
        ticks = list(range(first, int(high) + 1, step))
        if 3 <= len(ticks) <= 5:
            return ticks
    step = candidates[-1]
    return list(range(int(low // step) * step, int(high) + 1, step))[:5] or [int(low)]


def parse_workout(
    raw: str | None,
    profile: dict[str, Any] | None = None,
    sport: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Schritte und Achse eines Plans.

    Die Achse ist die Skala des Diagramms: absolute Watt, Prozent der Schwelle
    oder Prozent der Herzfrequenz. Gibt der Plan keine Ziele her, bleibt sie leer
    und die Oberfläche zeigt nur die Zahlen.
    """
    if not raw:
        return [], None
    try:
        event = json.loads(raw)
    except (TypeError, ValueError):
        return [], None
    doc = event.get("workout_doc") or {}
    flat: list[dict[str, Any]] = []
    _flatten(doc.get("steps") or [], flat)
    if not flat:
        return [], None

    if profile:
        for step in flat:
            target = step["target"]
            if not target:
                continue
            target = _to_bpm(target, profile)
            target = _to_watts(target, profile, sport)
            step["target"] = target
            step["target_text"] = _target_text(target, step["distance_m"] or None)

    units = [s["target"]["unit"] for s in flat if s["target"]]
    if not units:
        return flat, None
    if "W" in units:
        unit = "W"
    elif "bpm" in units:
        unit = "bpm"
    else:
        unit = "%"
    bands = [s["target"] for s in flat if s["target"] and s["target"]["unit"] == unit]
    if not bands:
        return flat, None

    peak = max(b["hi"] for b in bands)
    for step in flat:
        target = step["target"]
        # Arbeit ist, was nahe an der Spitze liegt. Auf- und Auslaufen bleiben
        # ruhig, auch wenn der Plan sie mit derselben Zone beschreibt.
        step["work"] = bool(
            target
            and target["unit"] == unit
            and target["hi"] >= peak * 0.95
            and not step["warmup"]
            and not step["cooldown"]
        )

    low = min(b["lo"] for b in bands)
    high = max(b["hi"] for b in bands)
    pad = max(3.0, (high - low) * 0.1)
    start = max(0.0, low - pad)
    end = high + pad

    basis = next((b["basis"] for b in bands if b.get("basis")), None)
    if unit == "W":
        label = "W"
    elif unit == "bpm":
        label = "bpm"
    else:
        label = f"% {UNIT_LABEL.get(basis or '', '')}".strip()

    return flat, {
        "from": round(start, 1),
        "to": round(end, 1),
        "ticks": _nice_ticks(start, end, unit),
        "unit": label,
    }


# ------------------------------------------------------------------ Rechnung


def estimate(
    family: str | None,
    minutes: float | None,
    km: float | None,
    speed_kmh: float | None,
) -> tuple[float | None, float | None, str]:
    """Fehlende Hälfte einer Einheit schätzen.

    Zurück kommen Minuten, Kilometer und die Angabe, welche der beiden Zahlen
    geschätzt ist: `dauer`, `distanz` oder `keine`.
    """
    speed = speed_kmh or FALLBACK_KMH.get(family or "", 20.0)
    if minutes and km:
        return minutes, km, "keine"
    if minutes and not km:
        return minutes, round(minutes / 60 * speed, 1), "distanz"
    if km and not minutes:
        return round(km / speed * 60), km, "dauer"
    return None, None, "keine"


def planned(
    event: dict[str, Any],
    speeds_kmh: dict[str, float],
    hr: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Die geplante Einheit als Zahlen: Dauer, Distanz, Schritte, Achse."""
    steps, axis = parse_workout(event.get("raw"), hr, event.get("sport"))
    planned_s = sum(s["seconds"] for s in steps)
    planned_m = sum(s["distance_m"] for s in steps)

    duration_s = planned_s or float(event.get("duration_s") or 0)
    distance_m = planned_m or float(event.get("distance_m") or 0)

    family = sport_family(event.get("sport"))
    minutes, km, estimated = estimate(
        family,
        round(duration_s / 60) if duration_s else None,
        round(distance_m / 1000, 1) if distance_m else None,
        speeds_kmh.get(family or ""),
    )

    # Was im Plan als Ziel steht, ist keine Schätzung: Distanz bei Distanz-Ziel,
    # Dauer bei Dauer-Ziel. Die jeweils andere Zahl kommt aus dem Median.
    primary = "distance" if event.get("distance_m") else ("duration" if duration_s else None)
    if primary == "distance":
        estimated = "dauer" if distance_m else estimated
    elif primary == "duration":
        estimated = "distanz" if duration_s else estimated

    # Ziele je Schritt für die Anzeige (Sekunden sind zum Rechnen, nicht zum Lesen).
    rows = []
    last = len(steps) - 1
    for index, step in enumerate(steps):
        minutes_step = step["seconds"] / 60
        label = step["text"]
        if not label:
            if step["warmup"] or (index == 0 and not step["work"]):
                label = "Aufwärmen"
            elif step["cooldown"] or (index == last and not step["work"]):
                label = "Auslaufen"
            else:
                label = "Hauptteil" if step["work"] else "Ruhig"
        target = step["target"]
        rows.append(
            {
                "label": label,
                "minutes": round(minutes_step, 1),
                "distance_km": round(step["distance_m"] / 1000, 2) if step["distance_m"] else None,
                # Die Distanz steht in der eigenen Spalte, nicht nochmal im Ziel.
                "target": _target_text(target, None),
                "work": step["work"],
                "lo": target["lo"] if target else None,
                "hi": target["hi"] if target else None,
            }
        )

    return {
        "minutes": minutes,
        "km": km,
        "estimated": estimated,
        "primary": primary,
        "axis": axis,
        "steps": rows,
        "total_minutes": round(sum(r["minutes"] for r in rows)) or None,
    }


def fuel_for(minutes: float | None) -> dict[str, Any] | None:
    """Verpflegung für die Einheit — erst ab 60 Minuten."""
    if not minutes or minutes < 60:
        return None
    plan = fuel.plan(minutes, "locker", source="gel")
    return {
        "carbs_g": plan["total"]["carbs"],
        "rate": plan["per_hour"]["carbs"],
        "gels": (plan["gels"] or {}).get("count") or 0,
        "water_ml": plan["total"]["water_ml"],
        "sodium_mg": plan["total"]["sodium_mg"],
    }


def matches(conn: Any, event: dict[str, Any]) -> dict[str, Any] | None:
    """Die Aufzeichnung zu einer geplanten Einheit, wenn es sie gibt.

    Gesucht wird am selben Tag in derselben Sportart-Familie; bei mehreren
    Kandidaten gewinnt die, deren Dauer am nächsten am Plan liegt.
    """
    family = sport_family(event.get("sport"))
    if not family:
        return None
    day = date.fromisoformat(event["date"])
    rows = [
        row
        for row in db.activities_between(conn, day, day)
        if sport_family(row["sport"]) == family
    ]
    if not rows:
        return None
    target = (event.get("duration_s") or 0) / 60
    if target:
        rows.sort(key=lambda row: abs(((row.get("moving_s") or row.get("duration_s") or 0) / 60) - target))
    return rows[0]


def done_payload(row: dict[str, Any]) -> dict[str, Any]:
    moving = row.get("moving_s") or row.get("duration_s") or 0
    return {
        "activity_id": row.get("source_id"),
        "name": row.get("name") or "",
        "minutes": round(moving / 60) if moving else None,
        "km": round((row.get("distance_m") or 0) / 1000, 1) if row.get("distance_m") else None,
        "load": row.get("load"),
        "intensity": round(row["intensity"]) if row.get("intensity") else None,
        "hr": round(row["avg_hr"]) if row.get("avg_hr") else None,
    }


def session(conn: Any, event: dict[str, Any], speeds_kmh: dict[str, float] | None = None) -> dict[str, Any]:
    """Alles, was die Einheit auf dem Bildschirm braucht."""
    speeds_kmh = speeds_kmh or speeds(conn)
    numbers = planned(event, speeds_kmh, _profile_for(sport_profiles(conn), event.get("sport")))
    row = matches(conn, event)
    return {
        "id": event["id"],
        "date": event["date"],
        "sport": event.get("sport"),
        "sport_label": SPORT_LABELS.get(event.get("sport") or "", event.get("sport") or ""),
        "name": event.get("name") or "",
        "load": event.get("load"),
        "intensity": round(event["intensity"]) if event.get("intensity") else None,
        **numbers,
        "fuel": fuel_for(numbers["minutes"]),
        "actual": done_payload(row) if row else None,
    }


def session_row(conn: Any, event: dict[str, Any], speeds_kmh: dict[str, float] | None = None) -> dict[str, Any]:
    """Kurzfassung für die Tageskarte."""
    speeds_kmh = speeds_kmh or speeds(conn)
    numbers = planned(event, speeds_kmh)
    return {
        "id": event["id"],
        "date": event["date"],
        "sport": event.get("sport"),
        "sport_label": SPORT_LABELS.get(event.get("sport") or "", event.get("sport") or ""),
        "name": event.get("name") or "",
        "minutes": numbers["minutes"],
        "km": numbers["km"],
        "estimated": numbers["estimated"],
        "primary": numbers["primary"],
        "load": event.get("load"),
        "done": matches(conn, event) is not None,
    }
