"""Verpflegungsrechner: Kohlenhydrate, Flüssigkeit, Salz und was man herrichtet.

Zwei Modi, mehr braucht es vorerst nicht:

- ``locker`` – lange ruhige Einheit (Long Run, Zone 2). Weniger Kohlenhydrate,
  weil der Körper dort mehr Fett verbrennt und der Magen weniger arbeiten muss.
- ``race`` – Wettkampf. Mehr Kohlenhydrate pro Stunde, weil das Tempo höher und
  der Glykogenverbrauch größer ist.

Die Zahlen stehen auf zwei Beinen:

1. **Bänder nach Dauer.** Die veröffentlichte Empfehlung (ACSM/IOC-Konsens,
   Arbeiten von Asker Jeukendrup) gibt Gramm pro Stunde, nicht Gramm pro Kilo —
   die Grenze sitzt in der Darmwand, nicht in der Muskelmasse. Übernommen wird
   die *Mitte* des Bandes, nicht das obere Ende: 90 g/h sind bei einem
   Vier-Stunden-Rennen zwölf Gels, und das macht niemand.
2. **Zwei Türen.** SGLT1 nimmt Glukose bis etwa 60 g/h auf, GLUT5 zusätzlich
   Fruktose bis etwa 30 g/h. Deshalb ist 60 g/h die Grenze für einen einzigen
   Zucker und 90 g/h die Grenze für eine Mischung. Alles darüber kommt nicht an.

Bewusst *nicht* enthalten: Sportart, Höhenmeter, Leistungsmessung. Für die
Frage "wie viel nehme ich mit" ändern sie das Ergebnis kaum, für die Frage
"welche Einheit plane ich" gehören sie in die Trainingsplanung und nicht hierher.
"""

from __future__ import annotations

import math
from typing import Any

MODES: dict[str, dict[str, Any]] = {
    "locker": {
        "label": "Locker",
        "hint": "Long Run, Zone 2, ruhige Ausfahrt",
        # 0,9 statt der 0,75 aus der Literatur: der erste Praxistest
        # (17 km in 1:51 mit 73 g Kohlenhydraten, also 40 g/h) lag genau hier.
        "factor": 0.90,
        "water_base": 400,
        "sodium": 400,
    },
    "race": {
        "label": "Wettkampf",
        "hint": "Renntempo, Marathon, Ironman",
        "factor": 1.10,
        "water_base": 500,
        "sodium": 600,
    },
}

#: (Obergrenze in Minuten, Gramm je Stunde). Die letzte Zeile gilt für alles darüber.
CARB_BANDS: list[tuple[int | None, float]] = [
    (45, 0.0),
    (75, 22.0),
    (120, 45.0),
    (180, 60.0),
    (240, 75.0),
    (None, 82.0),
]

#: Mehr als das kommt auch als Mischung nicht an.
CARB_CAP = 90.0
#: Ab hier reicht ein Zucker nicht mehr, Fruktose muss dazu.
SINGLE_TRANSPORT = 60.0
#: Unter dieser Rate lohnt kein Fueling — Wasser reicht.
MIN_USEFUL_RATE = 20.0

#: Ein Gel hat rund 22 g Kohlenhydrate. Rechengröße, keine Produktempfehlung.
GEL_CARBS = 22.0

#: Ahornsirup: 65,3 g Kohlenhydrate je 100 g, Dichte rund 1,33 g/ml.
#: 100 ml sind damit etwa 87 g Kohlenhydrate – vier Gels in einer Flasche.
SYRUP_CARBS_PER_GRAM = 0.653
SYRUP_DENSITY_G_PER_ML = 1.33
#: 1 g Natrium entspricht rund 2,54 g Kochsalz (NaCl).
SALT_PER_SODIUM = 2.54
#: Ungesalzener Ahornsirup, mit dem gerechnet wird.
SHOT_ML_DEFAULT = 50.0
#: Größen, zwischen denen die Seite einen passenderen Shot vorschlägt.
SHOT_SIZES = (20, 25, 30, 40, 50, 60, 80, 100)

#: Woraus die Kohlenhydrate kommen.
SOURCES: dict[str, dict[str, Any]] = {
    "gel": {"label": "Gels & Pulver", "hint": "Getränk plus Gels"},
    "syrup": {"label": "Ahornsirup", "hint": "Sirup-Shots plus Wasser"},
}
#: Höhere Konzentration zieht Wasser in den Darm und drückt.
MAX_CONCENTRATION = 0.08


def _round_to(value: float, step: float) -> float:
    """Kaufmännisch runden – Pythons round() rundet 0,5 zur geraden Zahl."""
    return math.floor(value / step + 0.5) * step


def _clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _de(value: float, digits: int = 2) -> str:
    """Zahl mit Komma – die Texte gehen so in die Oberfläche."""
    return f"{value:.{digits}f}".replace(".", ",")


def band_for(minutes: float) -> tuple[int | None, float]:
    """Das Dauerband, in das diese Einheit fällt."""
    for bis, grams in CARB_BANDS:
        if bis is None or minutes < bis:
            return bis, grams
    return CARB_BANDS[-1]


def carb_rate(minutes: float, mode: str) -> int:
    """Kohlenhydrate je Stunde, gerundet auf 5 g."""
    _, base = band_for(minutes)
    rate = base * MODES[mode]["factor"]
    return int(min(CARB_CAP, _round_to(rate, 5)))


def _drink(rate: int, hours: float, source: str = "gel") -> dict[str, Any]:
    """Wie viel von der Stundenmenge über das Getränk kommt.

    Bei Ahornsirup kommt alles aus den Shots, das Getränk bleibt Wasser.
    """
    if source == "syrup":
        # Alles kommt aus den Shots. Wasser steht nicht im Zeitplan – es läuft
        # nebenher nach Durst, der Sirup ist das Gel.
        return {
            "carbs_per_hour": 0,
            "carbs_per_bottle": 0,
            "bottle_ml": 500,
            "concentration_pct": 0.0,
            "bottles": 0,
        }

    if rate < MIN_USEFUL_RATE:
        return {
            "carbs_per_hour": 0,
            "carbs_per_bottle": 0,
            "bottle_ml": 0,
            "concentration_pct": 0.0,
            "bottles": 0,
        }

    per_hour = int(_round_to(rate * 0.5, 5))
    per_bottle = per_hour
    # Konzentration über 8 % nur über mehr Wasser, nicht über mehr Pulver.
    bottle_ml = max(500, math.ceil(per_bottle / MAX_CONCENTRATION / 50) * 50)
    concentration = round(per_bottle / bottle_ml * 100, 1)
    return {
        "carbs_per_hour": per_hour,
        "carbs_per_bottle": per_bottle,
        "bottle_ml": bottle_ml,
        "concentration_pct": concentration,
        "bottles": max(1, math.ceil(hours)),
    }


def _gels(rate: int, drink_carbs: int, hours: float) -> dict[str, Any]:
    if rate < MIN_USEFUL_RATE:
        return {"per_hour": 0.0, "count": 0, "carbs_each": int(GEL_CARBS), "carbs_total": 0,
                "caffeine": 0}

    rest = max(0.0, rate - drink_carbs)
    per_hour = rest / GEL_CARBS
    total = round(per_hour * hours)
    # Eine angebrochene Portion lohnt erst, wenn sie mehr als ein halbes Gel trägt.
    if per_hour * hours > 0.6 and total == 0:
        total = 1
    return {
        "per_hour": round(per_hour, 1),
        "count": total,
        "carbs_each": int(GEL_CARBS),
        "carbs_total": int(total * GEL_CARBS),
        "caffeine": max(0, total // 3) if total >= 4 else 0,
    }


def _syrup(
    rate: int,
    hours: float,
    sodium_per_hour: int,
    shot_ml: float,
    unit: str = "ml",
) -> dict[str, Any]:
    """Wie viel Sirup je Stunde, je Shot – und wie viel Salz hinein gehört.

    ``unit`` sagt nur, in welcher Einheit die Portion angezeigt wird. Gerechnet
    wird immer in Millilitern, weil die Dichte die Brücke zwischen Waage und
    Flasche ist.
    """
    shot_ml = _clamp(shot_ml, 10, 250)
    shot_g = shot_ml * SYRUP_DENSITY_G_PER_ML
    amount = round(shot_g) if unit == "g" else round(shot_ml)
    if rate < MIN_USEFUL_RATE:
        return {
            "shot_ml": round(shot_ml),
            "shot_g": round(shot_g),
            "unit": unit,
            "amount": amount,
            "grams_per_shot": 0,
            "carbs_per_shot": 0,
            "carbs_total": 0,
            "shots_per_hour": 0.0,
            "minutes_between": None,
            "shots": 0,
            "ml_per_hour": 0,
            "ml_total": 0,
            "grams_total": 0,
            "salt_g_per_hour": 0.0,
            "salt_g_total": 0.0,
            "salt_g_per_shot": 0.0,
            "sodium_mg_per_shot": 0,
        }

    grams_per_hour = rate / SYRUP_CARBS_PER_GRAM
    ml_per_hour = grams_per_hour / SYRUP_DENSITY_G_PER_ML
    shots_per_hour = ml_per_hour / shot_ml
    shots = max(1, round(shots_per_hour * hours))
    salt_per_hour = sodium_per_hour * SALT_PER_SODIUM / 1000
    per_shot = salt_per_hour / shots_per_hour if shots_per_hour else 0.0

    return {
        "shot_ml": round(shot_ml),
        "shot_g": round(shot_g),
        "unit": unit,
        "amount": amount,
        "grams_per_shot": round(shot_g),
        "carbs_per_shot": round(shot_ml * SYRUP_DENSITY_G_PER_ML * SYRUP_CARBS_PER_GRAM),
        "carbs_total": round(shots * shot_ml * SYRUP_DENSITY_G_PER_ML * SYRUP_CARBS_PER_GRAM),
        "shots_per_hour": round(shots_per_hour, 1),
        "minutes_between": round(60 / shots_per_hour) if shots_per_hour else None,
        "shots": shots,
        "ml_per_hour": round(ml_per_hour),
        "ml_total": round(ml_per_hour * hours),
        "grams_total": round(grams_per_hour * hours),
        "salt_g_per_hour": round(salt_per_hour, 2),
        "salt_g_total": round(salt_per_hour * hours, 1),
        "salt_g_per_shot": round(per_shot, 2),
        "sodium_mg_per_shot": round(per_shot * 1000 / SALT_PER_SODIUM),
    }


def _shot_mismatch(rate: int, hours: float, shot_ml: float) -> tuple[int, float]:
    """Wie viele Shots und wie weit weg von der Zielmenge."""
    carbs_per_shot = shot_ml * SYRUP_DENSITY_G_PER_ML * SYRUP_CARBS_PER_GRAM
    ml_per_hour = rate / SYRUP_CARBS_PER_GRAM / SYRUP_DENSITY_G_PER_ML
    shots = max(1, round(ml_per_hour * hours / shot_ml))
    target = rate * hours
    return shots, abs(shots * carbs_per_shot - target) / target


def _shot_suggestion(rate: int, hours: float, shot_ml: float) -> dict[str, Any] | None:
    """Ein Shot, der die Stundenmenge glatter trifft als der gewählte.

    Bei 1:51 und 50-ml-Shots bleibt genau ein Shot übrig – 43 von 65 Gramm.
    Mit 25 ml passen drei hinein und die Menge stimmt. Das soll dastehen,
    statt dass man es an der Zahl merkt.
    """
    if rate < MIN_USEFUL_RATE:
        return None
    current_shots, current_off = _shot_mismatch(rate, hours, shot_ml)
    if current_off <= 0.12:
        return None

    best: tuple[float, float, int] | None = None
    for size in SHOT_SIZES:
        shots, off = _shot_mismatch(rate, hours, size)
        # Ein einzelner Shot für eine lange Einheit ist kein Rhythmus.
        penaltiy = 0.25 if shots < 2 and hours >= 1.5 else 0.0
        score = off + penaltiy
        if best is None or score < best[0]:
            best = (score, size, shots)

    if best is None:
        return None
    _, size, shots = best
    _, off = _shot_mismatch(rate, hours, size)
    if size == shot_ml or off >= current_off - 0.1:
        return None

    carbs = round(size * SYRUP_DENSITY_G_PER_ML * SYRUP_CARBS_PER_GRAM)
    current_carbs = round(shot_ml * SYRUP_DENSITY_G_PER_ML * SYRUP_CARBS_PER_GRAM)
    return {
        "shot_ml": size,
        "shots": shots,
        "carbs_per_shot": carbs,
        "text": (
            f"Mit {int(size)}-ml-Shots passt es besser: {shots} Shots à {carbs} g "
            f"statt {current_shots} à {current_carbs} g."
        ),
    }


def _water(minutes: float, mode: str, temp_c: float) -> dict[str, Any]:
    base = MODES[mode]["water_base"] + 25 * (temp_c - 15)
    per_hour = int(_round_to(_clamp(base, 350, 1000), 50))
    hours = minutes / 60
    return {
        "ml_per_hour": per_hour,
        "ml_total": int(_round_to(per_hour * hours, 100)),
        "note": "Nach Durst trinken — mehr als ein Liter je Stunde bringt nichts.",
    }


def _sodium(minutes: float, mode: str, temp_c: float) -> dict[str, Any]:
    if minutes < 90:
        return {
            "mg_per_hour": 0,
            "mg_total": 0,
            "salt_g_per_hour": 0.0,
            "salt_g_total": 0.0,
            "note": "Unter 90 Minuten deckt das jede normale Mahlzeit ab.",
        }
    per_hour = MODES[mode]["sodium"] + (100 if temp_c >= 26 else 0)
    total = per_hour * minutes / 60
    return {
        "mg_per_hour": int(per_hour),
        "mg_total": int(_round_to(total, 50)),
        "salt_g_per_hour": round(per_hour * SALT_PER_SODIUM / 1000, 1),
        "salt_g_total": round(total * SALT_PER_SODIUM / 1000, 1),
        "note": "Salztabletten oder Elektrolytpulver; Sportgetränke bringen schon einen Teil mit.",
    }


def _verteilen(first: float, last: float, count: int) -> list[float]:
    """Gleichmäßig über das Fenster verteilen."""
    if count <= 0:
        return []
    if count == 1:
        return [(first + last) / 2]
    step = (last - first) / (count - 1)
    return [first + index * step for index in range(count)]


def _schedule(
    minutes: float,
    drink: dict[str, Any],
    gels: dict[str, Any],
    syrup: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Was man wann in die Hand nimmt."""
    entries: list[dict[str, Any]] = []

    if drink["bottles"]:
        for index in range(drink["bottles"]):
            minute = index * 60
            if minute >= minutes:
                break
            entries.append(
                {
                    "minute": minute,
                    "kind": "trinken",
                    "label": f"Flasche {index + 1}",
                    "detail": (
                        f"{drink['bottle_ml']} ml mit {drink['carbs_per_bottle']} g"
                        if drink["carbs_per_bottle"]
                        else f"{drink['bottle_ml']} ml Wasser"
                    ),
                    "carbs": drink["carbs_per_bottle"],
                }
            )

    if syrup and syrup["shots"]:
        first = min(25, round(minutes * 0.2))
        last = max(first, minutes - 10)
        detail = (
            f"{syrup['carbs_per_shot']} g KH"
            if syrup["unit"] == "g"
            else f"{syrup['grams_per_shot']} g · {syrup['carbs_per_shot']} g KH"
        )
        if syrup["salt_g_per_shot"]:
            detail += f" · {_de(syrup['salt_g_per_shot'])} g Salz"
        for minute in _verteilen(first, last, syrup["shots"]):
            entries.append(
                {
                    "minute": round(minute),
                    "kind": "essen",
                    "label": f"1 Shot à {syrup['amount']} {syrup['unit']}",
                    "detail": detail,
                    "carbs": syrup["carbs_per_shot"],
                }
            )

    elif gels["count"]:
        interval = 60 / gels["per_hour"] if gels["per_hour"] else 60
        first = min(interval, 25)
        for index in range(gels["count"]):
            minute = round(first + index * interval)
            if minute > minutes - 10:
                break
            entries.append(
                {
                    "minute": minute,
                    "kind": "essen",
                    "label": "1 Gel",
                    "detail": f"{int(GEL_CARBS)} g",
                    "carbs": int(GEL_CARBS),
                }
            )

    return sorted(entries, key=lambda entry: (entry["minute"], entry["kind"]))


def _surrounding(minutes: float, mode: str, weight: float) -> list[dict[str, Any]]:
    """Drumherum: Vortag, Frühstück, danach. Nur was der Dauer entspricht."""
    items: list[dict[str, Any]] = []

    if mode == "race" and minutes >= 150:
        items.append(
            {
                "key": "vortag",
                "label": "Am Vortag",
                "carbs": int(_round_to(9 * weight, 10)),
                "text": "8–10 g/kg über den Tag verteilt, abends die letzte große Mahlzeit.",
            }
        )
    if minutes >= 90:
        items.append(
            {
                "key": "fruehstueck",
                "label": "Frühstück, 3 h vorher",
                "carbs": int(_round_to(1.3 * weight, 10)),
                "text": "Bekanntes, fettarmes Frühstück — nichts Neues am Renntag.",
            }
        )
        items.append(
            {
                "key": "danach",
                "label": "Danach, bis 2 h",
                "carbs": int(_round_to(1.0 * weight, 10)),
                "text": "1 g/kg Kohlenhydrate plus 20–30 g Eiweiß.",
            }
        )
    return items


def _notes(
    minutes: float,
    mode: str,
    rate: int,
    temp_c: float,
    drink: dict[str, Any],
    gels: dict[str, Any],
    syrup: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    notes: list[dict[str, str]] = []

    if rate == 0:
        notes.append(
            {
                "tone": "info",
                "text": "Unter 45 Minuten braucht es kein Fueling. Wasser reicht.",
            }
        )
        return notes

    if rate < MIN_USEFUL_RATE:
        notes.append(
            {
                "tone": "info",
                "text": "Kurz und locker: Wasser genügt, ein Gel schadet aber nicht.",
            }
        )

    if syrup and syrup["shots"]:
        if syrup.get("suggestion"):
            notes.append({"tone": "info", "text": syrup["suggestion"]["text"]})
        notes.append(
            {
                "tone": "info",
                "text": (
                    "Ahornsirup ist fast reiner Haushaltszucker – also Glukose und Fruktose "
                    "zu gleichen Teilen. Damit sind auch 90 g/h über beide Darmtüren abgedeckt."
                ),
            }
        )
        notes.append(
            {
                "tone": "info",
                "text": (
                    "Sirup ist dickflüssig und zieht Wasser: zu jedem Shot ein paar Schluck "
                    "Wasser, sonst drückt es."
                ),
            }
        )
        if syrup["suggestion"]:
            notes.append({"tone": "info", "text": syrup["suggestion"]["text"]})
        if syrup["salt_g_per_shot"]:
            notes.append(
                {
                    "tone": "info",
                    "text": (
                        f"Salz direkt in den Shot rühren ({_de(syrup['salt_g_per_shot'])} g) – "
                        "oder in die Wasserflasche, wenn es zu salzig schmeckt."
                    ),
                }
            )

    if rate > SINGLE_TRANSPORT and not syrup:
        notes.append(
            {
                "tone": "warn",
                "text": (
                    f"Über {int(SINGLE_TRANSPORT)} g/h geht nur mit Glukose und Fruktose. "
                    "Ein reiner Glukose-Gel oder Traubenzucker bleibt sonst im Darm liegen."
                ),
            }
        )
    if rate >= 85:
        notes.append(
            {
                "tone": "warn",
                "text": (
                    "Das ist am oberen Rand. Im Training testen, "
                    "nicht zum ersten Mal im Rennen."
                ),
            }
        )
    if temp_c >= 26:
        notes.append(
            {
                "tone": "info",
                "text": "Hitze: mehr trinken ja, aber die Konzentration im Magen niedrig halten.",
            }
        )
    if minutes >= 180 and mode == "locker":
        notes.append(
            {
                "tone": "info",
                "text": (
                    "Ab drei Stunden lohnt auch im Training feste Nahrung — "
                    "der Magen will üben."
                ),
            }
        )
    if not syrup and gels["count"] and drink["carbs_per_hour"]:
        notes.append(
            {
                "tone": "info",
                "text": (
                    "Ein Gel mit ein paar Schlucken Wasser nehmen, dann drückt es nicht."
                ),
            }
        )
    return notes


def plan(
    minutes: float,
    mode: str = "locker",
    weight_kg: float = 78.0,
    temp_c: float = 18.0,
    source: str = "gel",
    shot_ml: float = SHOT_ML_DEFAULT,
    shot_unit: str = "g",
) -> dict[str, Any]:
    """Der ganze Verpflegungsplan für eine Einheit."""
    if mode not in MODES:
        raise ValueError(f"Unbekannter Modus: {mode}")
    if source not in SOURCES:
        raise ValueError(f"Unbekannte Quelle: {source}")
    if shot_unit not in ("g", "ml"):
        raise ValueError(f"Unbekannte Einheit: {shot_unit}")

    minutes = _clamp(float(minutes), 20, 900)
    weight = _clamp(float(weight_kg), 35, 160)
    temp = _clamp(float(temp_c), -10, 45)
    hours = minutes / 60

    rate = carb_rate(minutes, mode)
    water = _water(minutes, mode, temp)
    sodium = _sodium(minutes, mode, temp)
    drink = _drink(rate, hours, source)
    gels = (
        _gels(rate, drink["carbs_per_hour"], hours)
        if source == "gel"
        else _gels(0, 0, hours)
    )
    syrup = None
    if source == "syrup":
        syrup = _syrup(rate, hours, sodium["mg_per_hour"], shot_ml, shot_unit)
        syrup["suggestion"] = _shot_suggestion(rate, hours, syrup["shot_ml"])

    low = int(_round_to(rate * 0.85, 5))
    high = int(min(CARB_CAP, _round_to(rate * 1.15, 5)))

    return {
        "input": {
            "minutes": int(minutes),
            "hours": round(hours, 2),
            "mode": mode,
            "mode_label": MODES[mode]["label"],
            "source": source,
            "source_label": SOURCES[source]["label"],
            "shot_unit": shot_unit,
            "weight_kg": round(weight, 1),
            "temp_c": round(temp),
        },
        "per_hour": {
            "carbs": rate,
            "from": low,
            "to": high,
            "water_ml": water["ml_per_hour"],
        },
        "total": {
            "carbs": int(_round_to(rate * hours, 5)),
            "from": int(_round_to(low * hours, 5)),
            "to": int(_round_to(high * hours, 5)),
            "water_ml": water["ml_total"],
            "sodium_mg": sodium["mg_total"],
        },
        "drink": drink,
        "gels": gels,
        "syrup": syrup,
        "water": water,
        "sodium": sodium,
        "schedule": _schedule(minutes, drink, gels, syrup),
        "surrounding": _surrounding(minutes, mode, weight),
        "notes": _notes(minutes, mode, rate, temp, drink, gels, syrup),
    }
