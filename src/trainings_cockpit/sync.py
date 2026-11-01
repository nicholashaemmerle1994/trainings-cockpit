"""Sync: intervals.icu → lokale SQLite-Datenbank."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from . import db, dedupe
from .config import Settings
from .sources.garmin import GarminUnavailable, actor_rows, fetch_garmin
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
            activities = dedupe.entdoppeln(client.activities(oldest, today))
            wellness = client.wellness(oldest, today)
            events = client.events(oldest, events_until)

        n_activities = db.upsert_activities(conn, activities)

        # Läufe und Schwimmen kommen direkt von Garmin – mit den Feldern aus der
        # Originalaufzeichnung und einer Last, die an intervals kalibriert ist.
        n_direkt = 0
        garmin_note = ""
        if settings.garmin_key:
            try:
                cache = settings.ensure_data_dir() / "garmin" / "bearer-token.json"
                cache.parent.mkdir(parents=True, exist_ok=True)
                dump = fetch_garmin(settings.garmin_key, oldest, today, token_cache=cache)
                garmin_rows = actor_rows(dump)
                n_direkt = db.upsert_activities(conn, garmin_rows, mapped=True)
                if dump.errors:
                    garmin_note = " garmin=" + ",".join(sorted(dump.errors))[:80]
            except GarminUnavailable as exc:
                garmin_note = f" garmin=aus ({str(exc)[:40]})"

        n_doppelt = dubletten_entfernen(conn)
        n_wellness = db.upsert_wellness(conn, wellness)
        n_events = db.upsert_events(conn, events)

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
            + garmin_note,
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
