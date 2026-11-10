"""Garmin Connect Personal API (read-only).

Nutzt das offizielle Paket `garmin-connect-personal-api-python`.
Key anlegen: Garmin Connect → Settings → Personal API.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from ..load import compute_load


class GarminUnavailable(RuntimeError):
    pass


#: Garmins `typeKey` auf die Sportnamen, die das Cockpit führt.
SPORTS = {
    "running": "Run",
    "treadmill_running": "VirtualRun",
    "trail_running": "Run",
    "lap_swimming": "Swim",
    "open_water_swimming": "OpenWaterSwim",
    "swimming": "Swim",
}
#: Diese Sportarten kommen direkt von Garmin, alles andere über intervals.
DIRECT_SPORTS = {"Run", "VirtualRun", "Swim", "OpenWaterSwim"}


@dataclass
class GarminDump:
    profile: dict[str, Any] | None = None
    activities: list[dict[str, Any]] = field(default_factory=list)
    sleep: list[dict[str, Any]] = field(default_factory=list)
    hrv: list[dict[str, Any]] = field(default_factory=list)
    summaries: list[dict[str, Any]] = field(default_factory=list)
    weight: list[dict[str, Any]] = field(default_factory=list)
    fit_zip_bytes: int = 0
    fit_activity_id: int | None = None
    errors: dict[str, str] = field(default_factory=dict)


@contextmanager
def garmin_client(api_key: str, token_cache: Path | None = None) -> Iterator[Any]:
    """Ein angemeldeter Garmin-Client als `with`-Block.

    Der Bearer-Token liegt im Zwischenspeicher auf der Platte, nicht in der
    Datenbank: er wechselt und ist kein Messwert.
    """
    try:
        from garmin_personal_api import (  # noqa: PLC0415
            GarminPersonalApiClient,
            PersonalApiAuthenticator,
        )
    except ImportError as exc:  # pragma: no cover - Umgebungsfehler
        raise GarminUnavailable(
            "Paket 'garmin-connect-personal-api-python' fehlt. Installiere es mit `uv sync`."
        ) from exc

    with PersonalApiAuthenticator(bearer_token_cache_file=token_cache) as authenticator:
        token = authenticator.obtain_token(api_key)
    with GarminPersonalApiClient(token.access_token) as client:
        yield client


def fetch_garmin(
    api_key: str,
    oldest: date,
    newest: date,
    *,
    download_fit: bool = False,
    only_activities: bool = False,
    activity_limit: int = 1000,
    token_cache: Path | None = None,
) -> GarminDump:
    dump = GarminDump()

    with garmin_client(api_key, token_cache=token_cache) as client:
        if not only_activities:
            _try(dump, "profile", lambda: client.get_user_profile_settings())
            _windowed(dump, "sleep", client.get_daily_sleep_summaries, oldest, newest)
            _windowed(dump, "hrv", client.get_daily_hrv_summaries, oldest, newest)
            _windowed(dump, "summaries", client.get_daily_summaries, oldest, newest)
            _windowed(dump, "weight", client.get_weight_measurements, oldest, newest)
        _try(
            dump,
            "activities",
            lambda: _all_activities(client, oldest, newest, activity_limit),
        )
        if download_fit and dump.activities:
            newest_id = _activity_id(dump.activities[0])
            if newest_id is not None:
                try:
                    payload = client.download_activity(newest_id)
                    dump.fit_zip_bytes = len(payload)
                    dump.fit_activity_id = newest_id
                except Exception as exc:  # noqa: BLE001 - Befund statt Abbruch
                    dump.errors["fit_download"] = _short(exc)
    return dump


def activity_type(activity: dict[str, Any]) -> str | None:
    raw = activity.get("activityType")
    key = raw.get("typeKey") if isinstance(raw, dict) else raw
    return str(key) if key else None


def actor_rows(dump: GarminDump) -> list[dict[str, Any]]:
    """Garmin-Aktivitäten als Datensätze für die Datenbank.

    Läufe und Schwimmen: alles, was das Gerät aufgezeichnet hat, plus die Last
    aus `load.compute_load`, weil intervals sie für diese Einheiten nicht mehr
    liefert.
    """
    rows: list[dict[str, Any]] = []
    for activity in dump.activities:
        key = activity_type(activity)
        sport = SPORTS.get(str(key))
        if sport is None or sport not in DIRECT_SPORTS:
            continue

        start = str(
            activity.get("startTimeLocal") or activity.get("startTimeGMT") or ""
        ).replace(" ", "T")
        if not start[:10]:
            continue

        duration = activity.get("duration")
        moving = activity.get("movingDuration")
        rows.append(
            {
                "source": "garmin",
                "source_id": str(activity.get("activityId")),
                "date": start[:10],
                "start_local": start[:19],
                "sport": sport,
                "name": str(activity.get("activityName") or sport),
                "duration_s": int(duration) if duration else None,
                "moving_s": int(moving) if moving else None,
                "distance_m": activity.get("distance"),
                "elevation_m": activity.get("elevationGain"),
                "avg_hr": activity.get("averageHR"),
                "max_hr": activity.get("maxHR"),
                "avg_power": activity.get("averagePower"),
                "np": None,
                "calories": activity.get("calories"),
                "load": compute_load(sport, moving or duration, activity.get("averageHR")),
                "intensity": None,
                # Die Dublettenprüfung liest die Rohdaten: sie braucht die
                # Felder, die auch eine intervals-Aufzeichnung mitbringt.
                "raw": json.dumps(
                    {
                        **activity,
                        "id": str(activity.get("activityId")),
                        "source": "GARMIN_PERSONAL",
                        "device_name": "Garmin (Personal API)",
                        "type": sport,
                        "start_date_local": start[:19],
                        "elapsed_time": duration,
                        "moving_time": moving or duration,
                        "distance": activity.get("distance"),
                        "average_heartrate": activity.get("averageHR"),
                        "max_heartrate": activity.get("maxHR"),
                    },
                    ensure_ascii=False,
                ),
            }
        )
    return rows


def wellness_rows(dump: GarminDump) -> list[dict[str, Any]]:
    """Die Nachtsignale aus Garmin — Schlaf, HRV, Ruhepuls, Atmung, Gewicht.

    Drei Endpunkte liefern je Tag ein Stück: `sleep` die Dauer mit Score und
    Atmung, `hrv` den rMSSD der letzten Nacht, `summaries` den Ruhepuls und die
    Tagesatmung. Hier wird daraus **eine** Zeile je Tag in der Form, die
    `db.map_wellness` versteht — so bleibt der Weg in die Datenbank derselbe.

    Fehlt ein Wert, bleibt das Feld leer. Ein Tag mit halben Daten ist besser
    als kein Tag: ob die Erholung damit rechnet, entscheidet `metrics` (D-26),
    nicht der Import.
    """
    tage: dict[str, dict[str, Any]] = {}

    def tag(day: str) -> dict[str, Any]:
        return tage.setdefault(day, {"id": day})

    for roh in dump.sleep:
        # Je nach Endpunkt liegt die Nacht direkt oder unter `dailySleepDTO`.
        eintrag = (
            {**roh["dailySleepDTO"], **roh}
            if isinstance(roh, dict) and isinstance(roh.get("dailySleepDTO"), dict)
            else roh
        )
        day = _day(eintrag)
        if not day:
            continue
        zeile = tag(day)
        if eintrag.get("sleepTimeSeconds") is not None:
            zeile["sleepSecs"] = eintrag["sleepTimeSeconds"]
        for quelle, ziel in (
            ("awakeSleepSeconds", "awakeSleepSeconds"),
            ("deepSleepSeconds", "deepSleepSeconds"),
            ("lightSleepSeconds", "lightSleepSeconds"),
            ("remSleepSeconds", "remSleepSeconds"),
        ):
            if eintrag.get(quelle) is not None:
                zeile[ziel] = eintrag[quelle]
        # Fehlt `awakeSleepSeconds`, lässt es sich aus Zeit im Bett minus
        # Schlafdauer ableiten — dieselbe Nacht, kein erfundener Wert.
        awake = _awake_seconds(eintrag)
        if awake is not None:
            zeile["awakeSleepSeconds"] = awake
        need = _sleep_hours(eintrag.get("sleepNeed"))
        if need is not None:
            zeile["sleepNeedHours"] = need
        score = (eintrag.get("sleepScores") or {}).get("overall") or {}
        if score.get("value") is not None:
            zeile["sleepScore"] = score["value"]
        if eintrag.get("averageRespirationValue") is not None:
            zeile["respiration"] = eintrag["averageRespirationValue"]

    # Das Schlafziel steht im Profil, nicht in der Nacht. Es gilt für alle
    # Nächte des Laufs; fehlt es, bleibt die Spalte leer und `metrics` nimmt
    # den lokalen Fallback (7:30).
    goal = _profile_sleep_goal(dump.profile)
    if goal is not None:
        for zeile in tage.values():
            zeile["sleepGoalHours"] = goal

    for eintrag in dump.hrv:
        day = _day(eintrag)
        if day and eintrag.get("lastNightAvg") is not None:
            tag(day)["hrv"] = eintrag["lastNightAvg"]

    for eintrag in dump.summaries:
        day = _day(eintrag)
        if not day:
            continue
        zeile = tag(day)
        rhr = (eintrag.get("heartRate") or {}).get("restingValue")
        if rhr:
            zeile["restingHR"] = rhr
        atmung = (eintrag.get("respiration") or {}).get("avgValue")
        if atmung and zeile.get("respiration") is None:
            zeile["respiration"] = atmung

    for eintrag in dump.weight:
        day = _day(eintrag)
        gramm = eintrag.get("weight")
        if day and gramm:
            tag(day)["weight"] = round(float(gramm) / 1000, 1)

    return [zeile for zeile in tage.values() if len(zeile) > 1]


def _day(eintrag: dict[str, Any]) -> str | None:
    """Der Tag, dem ein Messwert gehört — Garmin nennt ihn `calendarDate`."""
    tag = eintrag.get("calendarDate") or eintrag.get("date")
    return str(tag)[:10] if tag else None


def _awake_seconds(eintrag: dict[str, Any]) -> int | None:
    """Wachzeit der Nacht — explizit, sonst Zeit im Bett minus Schlafdauer."""
    explicit = eintrag.get("awakeSleepSeconds")
    if explicit is not None:
        try:
            return max(0, int(round(float(explicit))))
        except (TypeError, ValueError):
            return None
    total = eintrag.get("sleepTimeSeconds")
    if total is None:
        return None
    seconds = _timestamp_seconds(
        eintrag.get("sleepStartTimestampGMT"), eintrag.get("sleepEndTimestampGMT")
    )
    if seconds is None:
        seconds = _timestamp_seconds(
            eintrag.get("sleepStartTimestampLocal"),
            eintrag.get("sleepEndTimestampLocal"),
        )
    if seconds is None:
        return None
    try:
        return max(0, int(round(seconds - float(total))))
    except (TypeError, ValueError):
        return None


def _timestamp_seconds(start: Any, end: Any) -> float | None:
    """Abstand zweier Garmin-Zeitstempel; Millisekunden und ISO sind erlaubt."""
    if start is None or end is None:
        return None
    if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        factor = 1000 if max(start, end) > 1e11 else 1
        return (float(end) - float(start)) / factor
    try:
        beginn = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        ende = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
        return (ende - beginn).total_seconds()
    except (TypeError, ValueError):
        try:
            start_number = float(start)
            end_number = float(end)
        except (TypeError, ValueError):
            return None
        factor = 1000 if max(start_number, end_number) > 1e11 else 1
        return (end_number - start_number) / factor


def _sleep_hours(value: Any) -> float | None:
    """Schlafziel in Stunden, egal ob die Quelle Sekunden oder Stunden liefert.

    Garmin führt Dauern in Sekunden; ein bereits normalisiertes Feld in Stunden
    bleibt Stunden. Ein Dict trägt den Wert unter `actual`, `need` oder
    `baseline` — die genaue Form bestätigt der erste Sync mit Key.
    """
    if isinstance(value, dict):
        for key in ("actual", "need", "recommendedSleepNeed", "baseline", "value"):
            if value.get(key) is not None:
                return _sleep_hours(value[key])
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return round(number / 3600, 2) if number > 24 else round(number, 2)


def _profile_sleep_goal(profile: dict[str, Any] | None) -> float | None:
    """Das Schlafziel aus dem Profil, tolerant gegenüber der Verschachtelung."""
    if not isinstance(profile, dict):
        return None
    for key in ("sleepGoal", "sleepGoalHours", "sleepNeedGoal"):
        if key in profile:
            goal = _sleep_hours(profile[key])
            if goal is not None:
                return goal
    for value in profile.values():
        if isinstance(value, dict):
            goal = _profile_sleep_goal(value)
            if goal is not None:
                return goal
    return None



def _all_activities(
    client: Any, oldest: date, newest: date, limit: int
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    page = 100
    start = 0
    while start < limit:
        batch = client.search_activities(
            start=start,
            limit=min(page, limit - start),
            start_date=oldest.isoformat(),
            end_date=newest.isoformat(),
        )
        if not batch:
            break
        collected.extend(batch)
        if len(batch) < page:
            break
        start += len(batch)
    return collected


WINDOW_DAYS = 28


def _windows(oldest: date, newest: date, days: int = WINDOW_DAYS):
    cursor = oldest
    while cursor <= newest:
        end = min(cursor + timedelta(days=days - 1), newest)
        yield cursor, end
        cursor = end + timedelta(days=1)


def _windowed(dump: GarminDump, name: str, fetch: Any, oldest: date, newest: date) -> None:
    """Garmin begrenzt die Zeiträume pro Endpunkt — in Fenstern abrufen."""
    for start, end in _windows(oldest, newest):
        _try(dump, name, lambda s=start, e=end: fetch(s, e))


def _try(dump: GarminDump, name: str, call: Any) -> None:
    try:
        value = call()
    except Exception as exc:  # noqa: BLE001 - einzelne Endpunkte dürfen scheitern
        dump.errors[name] = _short(exc)
        return
    if value is None:
        return
    current = getattr(dump, name)
    if isinstance(current, list):
        current.extend(_as_list(value))
    else:
        setattr(dump, name, value)


def _as_list(value: Any) -> list[Any]:
    """Garmin liefert je Endpunkt mal Liste, mal {"...": [...]}."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for nested in value.values():
            if isinstance(nested, list):
                return nested
        return [value]
    return [value]


def _activity_id(activity: dict[str, Any]) -> int | None:
    raw = activity.get("activityId") or activity.get("activity_id")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _short(exc: Exception) -> str:
    text = str(exc).strip().replace("\n", " ")
    return text[:300] if text else exc.__class__.__name__
