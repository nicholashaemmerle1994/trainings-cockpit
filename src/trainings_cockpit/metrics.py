"""Metriken: Tagesreihen, Readiness, Wochen, Serien."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import mean, median, pstdev
from typing import Any

from . import db, plan
from .planner.summaries import recorded_seconds

TARGET_SLEEP_H = 7.5
#: Garmins Sleep Need ist ein Ziel, keine Mindestdauer — unter sieben Stunden
#: wird es aber nicht als Ziel verwendet (D-89).
MIN_SLEEP_NEED_H = 7.0
#: Referenzfenster: 60 Kalendertage. Der Sommer mit anderem Rhythmus soll einen
#: schlechten Oktober nicht mehr abfedern, aber vier Wochen sind zu wenig, um
#: die eigene Streuung zu kennen.
REFERENCE_DAYS = 60
#: Ab so vielen gültigen Nächten im Fenster entsteht ein Wert (D-89).
REFERENCE_MIN_NIGHTS = 5
#: Median/MAD sind robust; der Faktor macht die MAD zur üblichen Streuung.
MAD_SCALE = 1.4826
#: Unter dieser Streuung wäre jeder z-Score ein Ausreißer. Die Werte sind
#: Mindeststreuungen je Signal, keine Normalisierung (D-89).
MIN_SPREAD = {"hrv": 1.0, "rhr": 1.0, "resp": 0.2}
#: Asymmetrische Abbildung: unter dem Üblichen zählt jeder z-Punkt 16, darüber
#: 10 Score-Punkte. Ein normaler Tag liegt bei 80 (D-89).
SCORE_CENTER = 80.0
SCORE_PER_SD_BELOW = 16.0
SCORE_PER_SD_ABOVE = 10.0
VALID_RANGES = {
    "hrv": (5.0, 200.0),
    "rhr": (30.0, 120.0),
    "sleep_s": (2 * 3600.0, 14 * 3600.0),
    "sleep_score": (0.0, 100.0),
    "sleep_awake_s": (0.0, 6 * 3600.0),
    "sleep_deep_s": (0.0, 8 * 3600.0),
    "sleep_light_s": (0.0, 12 * 3600.0),
    "sleep_rem_s": (0.0, 8 * 3600.0),
    "sleep_need_h": (3.0, 12.0),
    "sleep_goal_h": (3.0, 12.0),
    "respiration": (8.0, 20.0),
    "spo2": (90.0, 100.0),
    "weight_kg": (30.0, 200.0),
}
WEIGHTS = {"hrv": 35.0, "rhr": 25.0, "sleep": 30.0, "resp": 10.0}
#: Ein neuer Sensor misst anders. Nach einem Gerätewechsel beginnt die Referenz
#: neu, sonst mischt sie zwei Sensoren und zeigt eine Erholung, die es nicht gibt.
#: Solange die Referenz entsteht und eine Woche danach, lässt sich der Score der
#: Vergleichs-App (Bevel) eintragen: erst Paare sammeln, dann vergleichen (D-52).
VENDOR_COMPARE_DAYS = 7
#: Ohne diese Signale gibt es keinen Score (D-26). SpO2 ist bewusst nicht dabei:
#: es fließt seit v2 nicht mehr in den Score ein (D-89).
REQUIRED_SIGNALS = {
    "hrv": "die HRV",
    "rhr": "der Ruhepuls",
    "sleep": "der Schlaf",
    "resp": "die Atmung",
}
BANDS = (
    (85, "green-top", "Sehr gut erholt"),
    (70, "green", "Gut erholt"),
    (55, "amber", "Solide"),
    (40, "orange", "Erholungsbedarf"),
    (0, "red", "Ruhetag"),
)
#: Gesamtdeckel der Warnregeln (D-90). Nie positiv, nie tiefer als 15 Punkte.
WARNING_CAP = -15.0

BAND_SENTENCES = {
    "green-top": "Du bist heute sehr gut erholt.",
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
    sleep_awake_h: float | None = None
    sleep_deep_h: float | None = None
    sleep_light_h: float | None = None
    sleep_rem_h: float | None = None
    sleep_need_h: float | None = None
    sleep_goal_h: float | None = None
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
            sleep_awake_h=_seconds_to_hours(
                wellness_row, "sleep_awake_s", VALID_RANGES["sleep_awake_s"]
            ),
            sleep_deep_h=_seconds_to_hours(
                wellness_row, "sleep_deep_s", VALID_RANGES["sleep_deep_s"]
            ),
            sleep_light_h=_seconds_to_hours(
                wellness_row, "sleep_light_s", VALID_RANGES["sleep_light_s"]
            ),
            sleep_rem_h=_seconds_to_hours(
                wellness_row, "sleep_rem_s", VALID_RANGES["sleep_rem_s"]
            ),
            sleep_need_h=_num(wellness_row, "sleep_need_h", VALID_RANGES["sleep_need_h"]),
            sleep_goal_h=_num(wellness_row, "sleep_goal_h", VALID_RANGES["sleep_goal_h"]),
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


def _seconds_to_hours(
    row: dict[str, Any] | None,
    key: str,
    bounds: tuple[float, float] | None = None,
) -> float | None:
    """Wie `_hours`, aber Null ist ein gültiger Wert (null Minuten wach)."""
    value = _num(row, key, bounds)
    if value is None:
        return None
    return round(value / 3600, 2)


# ----------------------------------------------------------------- Readiness


def reference_nights(days: list[Day], index: int, epoch: date | None) -> int:
    """Gültige Nächte im 60-Tage-Fenster, das mit `index` endet (D-89)."""
    return len(_reference_window(days, index, epoch))


def _reference_window(days: list[Day], index: int, epoch: date | None) -> list[Day]:
    start = max(0, index - REFERENCE_DAYS + 1)
    return [
        day
        for day in days[start : index + 1]
        if (epoch is None or day.day >= epoch) and _valid_night(day)
    ]


def _baseline_window(days: list[Day], target: int, epoch: date | None) -> list[Day]:
    """Alle gültigen Nächte im 60-Tage-Fenster, inklusive der Zielnacht (D-89)."""
    return _reference_window(days, target, epoch)


def _valid_night(day: Day) -> bool:
    return any(
        value is not None for value in (day.hrv, day.rhr, day.sleep_h, day.respiration)
    )


def _has_sleep_input(day: Day) -> bool:
    """Der Schlaf-Score braucht Dauer und Wachheit; Phasen sind optional."""
    return day.sleep_h is not None and day.sleep_awake_h is not None


def _complete_night(day: Day) -> bool:
    return (
        day.hrv is not None
        and day.rhr is not None
        and _has_sleep_input(day)
        and day.respiration is not None
    )


def _last_complete_index(days: list[Day], index: int, epoch: date | None) -> int | None:
    """Die heutige oder die unmittelbar vorherige Nacht (D-89).

    Der Rückfall auf die Nacht davor deckt nur den Sync-Verzug am Morgen ab.
    Eine ältere vollständige Nacht ist kein aktueller Erholungswert: fehlen
    heute und gestern die Pflichtwerte, gibt es „Keine Daten“. Einzelne Signale
    werden nicht von gestern geliehen: entweder die ganze Nacht oder keine.
    """
    for position in (index, index - 1):
        if position < 0:
            continue
        day = days[position]
        if epoch is not None and day.day < epoch:
            continue
        if _complete_night(day):
            return position
    return None


def _missing_signals(days: list[Day], index: int, epoch: date | None) -> list[str]:
    """Was der heutigen oder gestrigen Nacht fehlt — nicht einer alten Nacht."""
    for day in reversed(days[max(0, index - 1) : index + 1]):
        if epoch is not None and day.day < epoch:
            continue
        if not _valid_night(day):
            continue
        return [
            name
            for key, name in REQUIRED_SIGNALS.items()
            if (
                getattr(day, {"sleep": "sleep_h", "resp": "respiration"}.get(key, key))
                is None
                or (key == "sleep" and not _has_sleep_input(day))
            )
        ]
    return list(REQUIRED_SIGNALS.values())


def _reference_payload(
    days: list[Day], index: int, epoch: date | None
) -> dict[str, Any]:
    return {
        "nights": reference_nights(days, index, epoch),
        "minimum": REFERENCE_MIN_NIGHTS,
        "target": REFERENCE_DAYS,
        "days": REFERENCE_DAYS,
        "average": None,
    }


def _no_recovery(
    label: str,
    reference: dict[str, Any],
    explanation: str,
    missing: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "score": None,
        "band": "unknown",
        "label": label,
        "confidence": 0.0,
        "components": [],
        "missing": missing or [],
        "reference": reference,
        "explanation": explanation,
        "date": None,
        "triggeredRules": [],
        "adjustment": 0,
    }


def _reference_building(reference: dict[str, Any]) -> dict[str, Any]:
    return _no_recovery(
        "Referenz wird aufgebaut",
        reference,
        (
            f"Für die Referenz fehlen noch Nächte: {reference['nights']} von "
            f"{REFERENCE_MIN_NIGHTS} sind da. Ein Erholungswert entsteht, sobald "
            f"genug Nächte im 60-Tage-Fenster liegen."
        ),
    )


def compute_recovery(
    days: list[Day], index: int, epoch: date | None = None
) -> dict[str, Any]:
    """Erholung nach Nachtsignalen im 60-Tage-Fenster (D-89).

    HRV, Ruhepuls und Atmung werden gegen den persönlichen Median derselben
    Nächte bewertet (Median/MAD, Mindeststreuung), der Schlaf gegen das
    Garmin-Schlafziel. Gewichte: HRV 35, Ruhepuls 25, Schlaf 30, Atmung 10.
    Es gibt keinen Teilwert: fehlt ein Pflichtsignal, entsteht kein Score
    (D-26). Der Score gehört zur letzten vollständigen Nacht; fehlt die heutige
    noch im Sync, wird die Nacht davor genommen und in der Oberfläche benannt.
    """
    target = _last_complete_index(days, index, epoch)
    # Die Referenz gehört zur Score-Nacht. Eine erst halb synchronisierte
    # heutige Nacht zählt nicht mit, wenn der Score von gestern kommt.
    reference = _reference_payload(days, index if target is None else target, epoch)
    if reference["nights"] < REFERENCE_MIN_NIGHTS:
        return _reference_building(reference)

    if target is None:
        missing = _missing_signals(days, index, epoch)
        if len(missing) == 1:
            text = f"Für die letzte Nacht fehlt noch {missing[0]}."
        else:
            text = (
                f"Für die letzte Nacht fehlen noch {', '.join(missing[:-1])} "
                f"und {missing[-1]}."
            )
        return _no_recovery(
            "Keine Daten",
            reference,
            f"{text} Ein Erholungswert entsteht erst, wenn alle Werte da sind.",
            missing=missing,
        )

    current = days[target]
    window = _reference_window(days, target, epoch)
    baseline_days = _baseline_window(days, target, epoch)

    def baseline(field: str) -> list[float]:
        return [
            value
            for day in baseline_days
            if (value := getattr(day, field)) is not None
        ]

    components: list[dict[str, Any]] = []

    hrv = _component(
        key="hrv",
        label="HRV",
        unit="ms",
        today=current.hrv,
        values=[day.hrv for day in window if day.hrv is not None],
        baseline=baseline("hrv"),
        invert=False,
        weight=WEIGHTS["hrv"],
        value_date=current.day.isoformat(),
    )
    if hrv:
        components.append(hrv)

    rhr = _component(
        key="rhr",
        label="Ruhepuls",
        unit="bpm",
        today=current.rhr,
        values=[day.rhr for day in window if day.rhr is not None],
        baseline=baseline("rhr"),
        invert=True,
        weight=WEIGHTS["rhr"],
        value_date=current.day.isoformat(),
    )
    if rhr:
        components.append(rhr)

    sleep = _sleep_component(current, window)
    if sleep:
        components.append(sleep)

    respiration = _component(
        key="resp",
        label="Atmung",
        unit="/min",
        today=current.respiration,
        values=[day.respiration for day in window if day.respiration is not None],
        baseline=baseline("respiration"),
        invert=True,  # niedriger ist besser
        weight=WEIGHTS["resp"],
        value_date=current.day.isoformat(),
    )
    if respiration:
        components.append(respiration)

    fehlend = [
        name for key, name in REQUIRED_SIGNALS.items() if key not in {c["key"] for c in components}
    ]
    if fehlend:
        # Die Zielnacht war vollständig, aber ein Signal hat keine belastbare
        # Referenz (zu wenige Werte). Auch dann gibt es keinen Teilwert.
        if len(fehlend) == 1:
            text = f"Für die letzte Nacht fehlt noch {fehlend[0]}."
        else:
            text = (
                f"Für die letzte Nacht fehlen noch {', '.join(fehlend[:-1])} "
                f"und {fehlend[-1]}."
            )
        return _no_recovery(
            "Keine Daten",
            reference,
            f"{text} Ein Erholungswert entsteht erst, wenn alle Werte da sind.",
            missing=fehlend,
        )

    total_weight = sum(component["weight"] for component in components)
    raw_score = sum(c["score"] * c["weight"] for c in components) / total_weight
    rules, rule_sum = _warning_rules(components)
    adjustment = _capped_adjustment(rule_sum)
    displayed, band, label = _score_band(raw_score + adjustment)

    return {
        "score": displayed,
        "band": band,
        "label": label,
        "confidence": 1.0,
        "components": components,
        "missing": [],
        "reference": reference,
        "explanation": _explanation(band, components, rules, rule_sum, adjustment),
        "date": current.day.isoformat(),
        "triggeredRules": rules,
        "adjustment": round(adjustment),
    }


def _component(
    *,
    key: str,
    label: str,
    unit: str,
    today: float | None,
    values: list[float],
    baseline: list[float],
    invert: bool,
    weight: float,
    value_date: str | None = None,
) -> dict[str, Any] | None:
    """Ein Signal als persönlicher z-Score (Median/MAD), auf 0–100 abgebildet."""
    if today is None or not baseline or len(baseline) < REFERENCE_MIN_NIGHTS:
        return None

    base = median(baseline)
    mad = median([abs(value - base) for value in baseline])
    spread = max(MAD_SCALE * mad, MIN_SPREAD[key])
    z = (today - base) / spread
    if invert:
        z = -z
    mapped = SCORE_CENTER + (
        SCORE_PER_SD_ABOVE if z >= 0 else SCORE_PER_SD_BELOW
    ) * z
    score = max(0.0, min(100.0, mapped))

    recent = values[-7:] if values else [today]
    return {
        "key": key,
        "label": label,
        "score": round(score),
        "today": round(today, 1),
        "average": round(mean(recent), 1),
        "baseline": round(base, 1),
        "unit": unit,
        "weight": weight,
        "date": value_date,
        "z": round(z, 2),
    }


def _sleep_target(day: Day) -> float:
    """Garmin Sleep Need, sonst Garmin-Schlafziel, sonst lokal 7:30 (D-89)."""
    if day.sleep_need_h is not None:
        return max(day.sleep_need_h, MIN_SLEEP_NEED_H)
    if day.sleep_goal_h is not None:
        return day.sleep_goal_h
    return TARGET_SLEEP_H


def _sleep_component(day: Day, window: list[Day]) -> dict[str, Any] | None:
    """Schlaf aus Dauer, Wachheit und — falls vorhanden — Phasen.

    Mit Phasen: 60 % Dauer, 25 % Wachheit, 15 % Phasen. Ohne Phasen: 70/30.
    Der Garmin-Sleep-Score wird nicht verwendet (D-89).
    """
    if day.sleep_h is None or day.sleep_awake_h is None:
        return None

    target = _sleep_target(day)
    duration_score = max(0.0, min(100.0, 100 * day.sleep_h / target))

    in_bed = day.sleep_h + day.sleep_awake_h
    efficiency = day.sleep_h / in_bed if in_bed > 0 else 0.0
    # 95 % Schlafeffizienz und besser = volle Punktzahl, 70 % = 0.
    wake_score = max(0.0, min(100.0, (efficiency - 0.70) / 0.25 * 100))

    deep = day.sleep_deep_h
    rem = day.sleep_rem_h
    has_phases = deep is not None and rem is not None and day.sleep_h > 0
    phase_score: float | None = None
    if has_phases:
        deep_score = 100 * min(1.0, (deep / day.sleep_h) / 0.18)
        rem_score = 100 * min(1.0, (rem / day.sleep_h) / 0.22)
        phase_score = (deep_score + rem_score) / 2
        score = 0.60 * duration_score + 0.25 * wake_score + 0.15 * phase_score
    else:
        score = 0.70 * duration_score + 0.30 * wake_score

    sleep_values = [entry.sleep_h for entry in window if entry.sleep_h is not None]
    return {
        "key": "sleep",
        "label": "Schlaf",
        "score": round(score),
        "today": round(day.sleep_h, 2),
        "average": round(mean(sleep_values[-7:]), 2) if sleep_values else round(day.sleep_h, 2),
        "baseline": round(target, 2),
        "unit": "h",
        "weight": WEIGHTS["sleep"],
        "date": day.day.isoformat(),
        "z": None,
        "target": round(target, 2),
        "awake": round(day.sleep_awake_h, 2),
        "deep": round(deep, 2) if deep is not None else None,
        "rem": round(rem, 2) if rem is not None else None,
        "efficiency": round(efficiency, 3),
        "duration_score": round(duration_score),
        "wake_score": round(wake_score),
        "phase_score": round(phase_score) if phase_score is not None else None,
    }


def _warning_rules(
    components: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], float]:
    """Die vier Warnregeln mit festen Schwellen (D-90).

    Sie prüfen bewusst die Abweichung, nicht den z-Score: die Schwellen sind
    fachlich (10 %, 5 bpm, Schlafscore 60) und bleiben auch dann gleich, wenn
    sich die Streuung der Referenz ändert.
    """
    by_key = {component["key"]: component for component in components}
    if not {"hrv", "rhr", "sleep"} <= by_key.keys():
        return [], 0.0

    hrv = by_key["hrv"]
    rhr = by_key["rhr"]
    sleep = by_key["sleep"]
    hrv_deviation = (
        (hrv["today"] - hrv["baseline"]) / hrv["baseline"] * 100
        if hrv["baseline"]
        else 0.0
    )
    rhr_deviation = rhr["today"] - rhr["baseline"]
    hrv_score = hrv["score"]
    rhr_score = rhr["score"]
    sleep_score = sleep["score"]

    rules: list[dict[str, Any]] = []
    if hrv_deviation <= -10 and rhr_deviation >= 5:
        rules.append(
            {
                "id": "hrv_rhr",
                "label": "HRV mindestens 10 % unter Referenz und Ruhepuls mindestens 5 bpm darüber",
                "adjustment": -10,
            }
        )
    if hrv_deviation <= -10 and sleep_score < 60:
        rules.append(
            {
                "id": "hrv_sleep",
                "label": "HRV mindestens 10 % unter Referenz und Schlafscore unter 60",
                "adjustment": -8,
            }
        )
    if rhr_deviation >= 5 and sleep_score < 60:
        rules.append(
            {
                "id": "rhr_sleep",
                "label": "Ruhepuls mindestens 5 bpm über Referenz und Schlafscore unter 60",
                "adjustment": -8,
            }
        )
    if hrv_score < 50 and rhr_score < 50 and sleep_score < 60:
        rules.append(
            {
                "id": "triple_low",
                "label": "HRV, Ruhepuls und Schlaf liegen alle deutlich unter der Referenz",
                "adjustment": -5,
            }
        )
    return rules, float(sum(rule["adjustment"] for rule in rules))


def _capped_adjustment(rule_sum: float) -> float:
    """Der Gesamtdeckel der Warnregeln: nie positiv, nie tiefer als −15 (D-90)."""
    return max(WARNING_CAP, rule_sum) if rule_sum < 0 else 0.0


def _baseline(
    days: list[Day], index: int, field: str, epoch: date | None = None
) -> list[float] | None:
    values = [
        getattr(d, field)
        for d in days[max(0, index - REFERENCE_DAYS) : index]
        if getattr(d, field) is not None and (epoch is None or d.day >= epoch)
    ]
    return values if len(values) >= REFERENCE_MIN_NIGHTS else None


def _band(score: float) -> tuple[str, str]:
    for threshold, band, label in BANDS:
        if score >= threshold:
            return band, label
    return "red", "Ruhetag"


def _score_band(score: float) -> tuple[int, str, str]:
    """Das Band gehört zu der Zahl, die auf dem Ring steht."""
    displayed = round(score)
    band, label = _band(displayed)
    return displayed, band, label


def _explanation(
    band: str,
    components: list[dict[str, Any]],
    rules: list[dict[str, Any]] | None = None,
    rule_sum: float = 0.0,
    adjustment: float = 0.0,
) -> str:
    by_key = {component["key"]: component for component in components}
    sentences: list[str] = [BAND_SENTENCES.get(band, "")]

    hrv = by_key.get("hrv")
    if hrv:
        direction = "über" if hrv["today"] >= hrv["baseline"] else "unter"
        sentences.append(
            f"Deine HRV liegt mit {_de(hrv['today'])} ms {direction} deinem üblichen "
            f"Wert von {_de(hrv['baseline'])} ms."
        )

    rhr = by_key.get("rhr")
    if rhr:
        direction = "über" if rhr["today"] > rhr["baseline"] else "unter"
        sentences.append(
            f"Der Ruhepuls liegt mit {_de(rhr['today'])} bpm {direction} deinem "
            f"üblichen Wert von {_de(rhr['baseline'])} bpm."
        )

    sleep = by_key.get("sleep")
    if sleep:
        sentences.append(
            f"Du hast {_duration(sleep['today'])} geschlafen; das Ziel lag bei "
            f"{_duration(sleep['baseline'])}."
        )

    # Atmung fließt in den Score, wird aber nicht mehr erzählt: der Athlet
    # will sie nicht in der Oberfläche sehen.

    if rules:
        if rule_sum < WARNING_CAP:
            sentences.append(
                f"Die Warnregeln greifen; der Abzug ist bei {abs(round(adjustment))} "
                f"Punkten gedeckelt."
            )
        else:
            sentences.append(
                f"Die Warnregeln greifen; der Score wurde um {abs(round(adjustment))} "
                f"Punkte reduziert."
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


def recovery_series(days: list[Day], epoch: date | None = None) -> list[dict[str, Any]]:
    """Je Nacht ein Punkt — nicht je Tag, an dem zufällig ein Score gilt.

    Der Score gehört zur letzten vollständigen Nacht. Damit die Serie keine
    Nacht mehrfach zeigt, zählt nur der Tag, an dem diese Nacht liegt.
    """
    out: list[dict[str, Any]] = []
    for index in range(len(days)):
        result = compute_recovery(days, index, epoch)
        if result["score"] is None or result.get("date") != days[index].day.isoformat():
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
        stunden = recorded_seconds(row) / 3600
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
        hours = recorded_seconds(activity) / 3600
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
    moving = recorded_seconds(row)
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

    Zonen, Dauer, Distanz, Last — alles, was ohne einen weiteren Abruf in der
    Zeile steht. Der Verlauf kommt aus `streams.payload` und wird vom Aufrufer
    angehängt (D-53): diese Funktion kennt keine Datenbank.
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
    moving = recorded_seconds(row)
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
    latest = next(
        (
            d
            for d in reversed(series_days)
            if any(
                value is not None
                for value in (d.hrv, d.rhr, d.sleep_h, d.respiration)
            )
        ),
        current,
    )

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
        p
        for p in recovery_series(series_days, epoch)
        if p["date"] >= window_start.isoformat()
    ]

    # 60-Tage-Schnitt der Scores – nach einem Sensorwechsel nur die Nächte
    # seit dem Wechsel, sonst stünde der neue Wert neben einem alten Maßstab.
    if (recovery.get("reference") or {}).get("nights", 0) >= REFERENCE_MIN_NIGHTS:
        since = epoch.isoformat() if epoch else None
        recent = [
            point["score"]
            for point in recovery_points[-REFERENCE_DAYS:]
            if point.get("score") is not None and (since is None or point["date"] >= since)
        ]
        recovery["reference"]["average"] = round(mean(recent)) if recent else None

    # Das Feld für den Vergleichswert erscheint, solange die Referenz entsteht,
    # und eine Woche darüber hinaus (D-52): erst Paare sammeln, dann vergleichen.
    referenz = recovery.get("reference") or {}
    naechte = referenz.get("nights")
    recovery["vendor_prompt"] = bool(
        referenz
        and naechte is not None
        and naechte < (referenz.get("minimum") or 0) + VENDOR_COMPARE_DAYS
    )

    # Die letzten sieben Tage: heute und die sechs davor. Ein rollierendes
    # Fenster, keine Kalenderwoche — sonst springt der Wert am Montag.
    week_from = (today - timedelta(days=6)).isoformat()
    week_acts = [a for a in activities if week_from <= a["date"] <= today.isoformat()]
    week_seconds = sum(recorded_seconds(a) for a in week_acts)
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
    return round(median(baseline), 0) if baseline else None


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
