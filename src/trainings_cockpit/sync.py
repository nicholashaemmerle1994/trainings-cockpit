"""Sync: Plan von intervals, Aktivitäten und Nächte von Garmin.

Die Aufteilung (D-50, D-49 ausgesetzt):

- **intervals.icu** liefert Plan (`event`), Sport-Einstellungen und bis auf
  Weiteres die Aktivitäten für Rad und Kraft.
- **Garmin (Personal API)** liefert die Aktivitäten der Uhr (Läufe, Schwimmen)
  und die Nachtsignale: Schlaf, HRV, Ruhepuls, Atmung.

Fehlt Garmin, fehlen die Nächte — dann steht die Erholung auf „Keine Daten"
(D-26), statt dass eine fremde Quelle einspringt.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from . import db, dedupe
from .config import Settings
from .sources.garmin import GarminDump, GarminUnavailable, actor_rows, fetch_garmin, wellness_rows
from .sources.intervals import IntervalsClient


def sync(settings: Settings, days: int = 365, today: date | None = None) -> dict[str, Any]:
    if not settings.intervals_key:
        raise RuntimeError("Kein INTERVALS_API_KEY gesetzt.")

    today = today or date.today()
    oldest = today - timedelta(days=max(days, 1))
    events_until = today + timedelta(days=365)
    started = datetime.now()

    conn = db.connect(settings.db_path)
    try:
        db.init_db(conn)
        with IntervalsClient(
            settings.intervals_key, settings.intervals_athlete, settings.base_url
        ) as client:
            athlete = client.athlete()
            activities = client.activities(oldest, today)
            events = client.events(oldest, events_until)
            sport_settings = client.sport_settings()

        # Aktivitäten der Uhr und die Nächte kommen direkt von Garmin: die
        # Felder stammen aus der Originalaufzeichnung, die Last rechnet das
        # Cockpit selbst, und die Nachtsignale sind die des neuen Sensors.
        garmin = _garmin_data(settings, oldest, today)
        garmin_rows = garmin.activities
        n_direkt = 0

        # Eine Einheit nur einmal, auch wenn sie über zwei Quellen kommt. Die
        # Entscheidung fällt vor dem Schreiben: sonst legt jeder Sync die
        # Dublette neu an und räumt sie gleich wieder ab. Gespeicherte Zeilen
        # zählen mit, weil intervals eine Aufzeichnung auch zurückziehen kann —
        # die bessere Zeile bleibt dann stehen, statt jeden Morgen neu zu
        # entstehen und wieder zu verschwinden.
        bleibt = dedupe.behalten([*activities, *garmin_rows, *dedupe.aus_datenbank(conn)])
        activities = [a for a in activities if str(a.get("id")) in bleibt]
        garmin_rows = [g for g in garmin_rows if g["source_id"] in bleibt]

        n_activities = db.upsert_activities(conn, activities)
        if garmin_rows:
            n_direkt = db.upsert_activities(conn, garmin_rows, mapped=True)

        n_doppelt = dubletten_entfernen(conn)
        # Seit dem Sensorwechsel zählt nur, was der neue Sensor gemessen hat.
        # Sonst mischten sich beim Jahresimport alte intervals-Werte unter die
        # neuen Nächte, und "üblich" wäre ein Maßstab aus zwei Geräten (D-31).
        n_wellness = db.upsert_wellness(
            conn, _seit_epoche(garmin.wellness, db.wellness_epoch(conn))
        )
        n_events = db.upsert_events(conn, events)

        db.set_setting(conn, "sport_profile", json.dumps(_sport_profile(sport_settings)))
        db.set_setting(conn, "athlete_name", _pretty_name(athlete.get("name")))
        db.set_setting(conn, "athlete_id", str(athlete.get("id") or ""))
        db.set_setting(conn, "last_sync", datetime.now().isoformat(timespec="seconds"))
        db.log_sync(
            conn,
            "intervals",
            started,
            "ok",
            f"activities={n_activities} direkt={n_direkt} wellness={n_wellness} events={n_events}"
            + (f" dubletten={n_doppelt}" if n_doppelt else "")
            + garmin.note,
        )

        return {
            "activities": n_activities + n_direkt,
            "wellness": n_wellness,
            "events": n_events,
            "athlete": _pretty_name(athlete.get("name")),
            "range": [oldest.isoformat(), today.isoformat()],
        }
    except Exception as exc:
        db.log_sync(conn, "intervals", started, "error", str(exc)[:500])
        raise
    finally:
        conn.close()


def dubletten_entfernen(conn: Any) -> int:
    """Wirft gespeicherte Dubletten raus, die vor der Prüfung hereinkamen."""
    rows = dedupe.aus_datenbank(conn)
    weg = [str(verlierer.get("id")) for _, verlierer in dedupe.paare(rows) if verlierer.get("id")]
    return db.delete_activities(conn, weg)


@dataclass(frozen=True)
class GarminDaten:
    """Was Garmin je Sync liefert: Einheiten der Uhr und die Nächte."""

    activities: list[dict[str, Any]]
    wellness: list[dict[str, Any]]
    note: str


def _garmin_data(settings: Settings, oldest: date, today: date) -> GarminDaten:
    """Aktivitäten und Nachtsignale aus der Personal-API."""
    if not settings.garmin_key:
        return GarminDaten([], [], " garmin=aus (kein Key)")
    try:
        cache = settings.ensure_data_dir() / "garmin" / "bearer-token.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        dump = fetch_garmin(settings.garmin_key, oldest, today, token_cache=cache)
    except GarminUnavailable as exc:
        return GarminDaten([], [], f" garmin=aus ({str(exc)[:40]})")
    return GarminDaten(
        activities=actor_rows(dump),
        wellness=wellness_rows(dump),
        note=_garmin_note(dump),
    )


def _seit_epoche(rows: list[dict[str, Any]], epoch: date | None) -> list[dict[str, Any]]:
    """Nur Nächte ab dem Sensorwechsel. Ohne Marke zählt jede Nacht."""
    if epoch is None:
        return rows
    grenze = epoch.isoformat()
    return [row for row in rows if str(row["id"]) >= grenze]


def _garmin_note(dump: GarminDump) -> str:
    """Was Garmin nicht geliefert hat, steht im Sync-Log."""
    return " garmin=" + ",".join(sorted(dump.errors))[:80] if dump.errors else ""


def _sport_profile(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Max-HF, Zonengrenzen und FTP je Sportart aus den Einstellungen von intervals.

    Die Prozente in einem Plan sind Prozent der maximalen Herzfrequenz oder der
    Schwelle; ohne diese Zahlen kann die Oberfläche nur „70–75 %" schreiben
    statt „133–143 bpm" und „% FTP" statt „170–186 W".
    """
    profile: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        entry: dict[str, Any] = {}
        if row.get("max_hr") and row.get("hr_zones"):
            entry["max_hr"] = row["max_hr"]
            entry["zones"] = [int(z) for z in row["hr_zones"]]
        if row.get("ftp"):
            entry["ftp"] = row["ftp"]
        if row.get("indoor_ftp"):
            entry["indoor_ftp"] = row["indoor_ftp"]
        if not entry:
            continue
        for sport in row.get("types") or []:
            profile[str(sport)] = entry
    return profile


def _pretty_name(name: object) -> str:
    text = str(name or "").strip() or "Athlet"
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)


def ensure_db(settings: Settings) -> None:
    conn = db.connect(settings.db_path)
    try:
        db.init_db(conn)
    finally:
        conn.close()


def stats(settings: Settings) -> dict[str, Any]:
    conn = db.connect(settings.db_path)
    try:
        db.init_db(conn)
        first, last = db.first_last(conn)
        return {
            **db.counts(conn),
            "first": first,
            "last": last,
            "last_sync": db.last_sync(conn),
            "athlete": db.get_setting(conn, "athlete_name"),
        }
    finally:
        conn.close()
