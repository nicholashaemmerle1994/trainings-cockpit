"""Garmin Connect Personal API (read-only).

Nutzt das offizielle Paket `garmin-connect-personal-api-python`.
Key anlegen: Garmin Connect → Settings → Personal API.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
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
    weight: list[dict[str, Any]] = field(default_factory=list)
    fit_zip_bytes: int = 0
    fit_activity_id: int | None = None
    errors: dict[str, str] = field(default_factory=dict)


def fetch_garmin(
    api_key: str,
    oldest: date,
    newest: date,
    *,
    download_fit: bool = False,
    activity_limit: int = 500,
    token_cache: Path | None = None,
) -> GarminDump:
    try:
        from garmin_personal_api import (  # noqa: PLC0415
            GarminPersonalApiClient,
            PersonalApiAuthenticator,
        )
    except ImportError as exc:  # pragma: no cover - Umgebungsfehler
        raise GarminUnavailable(
            "Paket 'garmin-connect-personal-api-python' fehlt. "
            "Installiere es mit `uv sync`."
        ) from exc

    dump = GarminDump()

    with PersonalApiAuthenticator(bearer_token_cache_file=token_cache) as authenticator:
        token = authenticator.obtain_token(api_key)

    with GarminPersonalApiClient(token.access_token) as client:
        _try(dump, "profile", lambda: client.get_user_profile_settings())
        _windowed(dump, "sleep", client.get_daily_sleep_summaries, oldest, newest)
        _windowed(dump, "hrv", client.get_daily_hrv_summaries, oldest, newest)
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
