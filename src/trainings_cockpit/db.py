"""SQLite-Speicher: Schema, Upserts und Abfragen."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS activity (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    date          TEXT NOT NULL,
    start_local   TEXT NOT NULL,
    sport         TEXT NOT NULL,
    name          TEXT,
    duration_s    INTEGER,
    moving_s      INTEGER,
    distance_m    REAL,
    elevation_m   REAL,
    avg_hr        REAL,
    max_hr        REAL,
    avg_power     REAL,
    np            REAL,
    calories      REAL,
    load          REAL,
    intensity     REAL,
    raw           TEXT,
    updated_at    TEXT NOT NULL,
    UNIQUE(source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_activity_date ON activity(date);

CREATE TABLE IF NOT EXISTS wellness (
    date             TEXT PRIMARY KEY,
    hrv              REAL,
    rhr              REAL,
    sleep_s          REAL,
    sleep_score      REAL,
    respiration      REAL,
    spo2             REAL,
    stress           REAL,
    weight_kg        REAL,
    readiness_vendor REAL,
    ctl              REAL,
    atl              REAL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS event (
    id          INTEGER PRIMARY KEY,
    date        TEXT NOT NULL,
    sport       TEXT,
    category    TEXT,
    name        TEXT,
    load        REAL,
    duration_s  INTEGER,
    distance_m  REAL,
    intensity   REAL,
    description TEXT,
    raw         TEXT,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_date ON event(date);

CREATE TABLE IF NOT EXISTS sync_run (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT,
    started_at  TEXT,
    finished_at TEXT,
    status      TEXT,
    detail      TEXT
);

CREATE TABLE IF NOT EXISTS setting (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


#: Spalten, die nach dem ersten Anlegen dazugekommen sind.
#: (Tabelle, Spalte, Definition) — SQLite kann nur hinzufügen, nie ändern.
ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("event", "distance_m", "REAL"),
    ("event", "intensity", "REAL"),
    ("event", "raw", "TEXT"),
)


def _ensure_columns(conn: sqlite3.Connection) -> None:
    for table, column, decl in ADDED_COLUMNS:
        known = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in known:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    conn.commit()


# ------------------------------------------------------------------ Mapping


def map_activity(row: dict[str, Any]) -> dict[str, Any]:
    start = str(row.get("start_date_local") or row.get("start_date") or "")
    return {
        "source": "intervals",
        "source_id": str(row.get("id")),
        "date": start[:10],
        "start_local": start,
        "sport": row.get("type") or "Other",
        "name": row.get("name") or "",
        "duration_s": row.get("elapsed_time") or row.get("moving_time"),
        "moving_s": row.get("moving_time"),
        "distance_m": row.get("distance"),
        "elevation_m": row.get("total_elevation_gain"),
        "avg_hr": row.get("average_heartrate"),
        "max_hr": row.get("max_heartrate"),
        "avg_power": row.get("icu_average_watts") or row.get("average_watts"),
        "np": row.get("icu_weighted_avg_watts") or row.get("weighted_average_watts"),
        "calories": row.get("calories"),
        "load": row.get("icu_training_load"),
        "intensity": row.get("icu_intensity"),
        "raw": json.dumps(row, ensure_ascii=False),
    }


def map_wellness(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": str(row.get("id")),
        "hrv": row.get("hrv"),
        "rhr": row.get("restingHR"),
        "sleep_s": row.get("sleepSecs"),
        "sleep_score": row.get("sleepScore"),
        "respiration": row.get("respiration"),
        "spo2": row.get("spO2"),
        "stress": row.get("stress"),
        "weight_kg": row.get("weight"),
        "readiness_vendor": row.get("readiness"),
        "ctl": row.get("ctl"),
        "atl": row.get("atl"),
    }


def map_event(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row.get("id") or 0),
        "date": str(row.get("start_date_local") or "")[:10],
        "sport": row.get("type"),
        "category": row.get("category"),
        "name": row.get("name") or "",
        "load": row.get("icu_training_load"),
        "duration_s": row.get("moving_time"),
        "distance_m": row.get("distance") or None,
        "intensity": row.get("icu_intensity"),
        "description": row.get("description") or "",
        "raw": json.dumps(row, ensure_ascii=False),
    }


# ------------------------------------------------------------------ Upserts


def upsert_activities(
    conn: sqlite3.Connection,
    rows: Iterable[dict[str, Any]],
    mapped: bool = False,
) -> int:
    """Aktivitäten schreiben.

    `mapped=True` überspringt `map_activity` — für Quellen, die schon in der
    Form der Tabelle kommen (Garmin Personal API).
    """
    now = datetime.now().isoformat(timespec="seconds")
    count = 0
    for raw in rows:
        row = raw if mapped else map_activity(raw)
        conn.execute(
            """
            INSERT INTO activity (source, source_id, date, start_local, sport, name,
                duration_s, moving_s, distance_m, elevation_m, avg_hr, max_hr,
                avg_power, np, calories, load, intensity, raw, updated_at)
            VALUES (:source, :source_id, :date, :start_local, :sport, :name,
                :duration_s, :moving_s, :distance_m, :elevation_m, :avg_hr, :max_hr,
                :avg_power, :np, :calories, :load, :intensity, :raw, :updated_at)
            ON CONFLICT(source, source_id) DO UPDATE SET
                date=excluded.date, start_local=excluded.start_local, sport=excluded.sport,
                name=excluded.name, duration_s=excluded.duration_s, moving_s=excluded.moving_s,
                distance_m=excluded.distance_m, elevation_m=excluded.elevation_m,
                avg_hr=excluded.avg_hr, max_hr=excluded.max_hr, avg_power=excluded.avg_power,
                np=excluded.np, calories=excluded.calories, load=excluded.load,
                intensity=excluded.intensity, raw=excluded.raw, updated_at=excluded.updated_at
            """,
            {**row, "updated_at": now},
        )
        count += 1
    conn.commit()
    return count


def upsert_wellness(conn: sqlite3.Connection, rows: Iterable[dict[str, Any]]) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    count = 0
    for raw in rows:
        row = map_wellness(raw)
        conn.execute(
            """
            INSERT INTO wellness (date, hrv, rhr, sleep_s, sleep_score, respiration, spo2,
                stress, weight_kg, readiness_vendor, ctl, atl, updated_at)
            VALUES (:date, :hrv, :rhr, :sleep_s, :sleep_score, :respiration, :spo2,
                :stress, :weight_kg, :readiness_vendor, :ctl, :atl, :updated_at)
            ON CONFLICT(date) DO UPDATE SET
                hrv=excluded.hrv, rhr=excluded.rhr, sleep_s=excluded.sleep_s,
                sleep_score=COALESCE(excluded.sleep_score, wellness.sleep_score),
                respiration=excluded.respiration,
                spo2=excluded.spo2, stress=excluded.stress, weight_kg=excluded.weight_kg,
                readiness_vendor=COALESCE(excluded.readiness_vendor, wellness.readiness_vendor),
                ctl=excluded.ctl,
                atl=excluded.atl, updated_at=excluded.updated_at
            """,
            {**row, "updated_at": now},
        )
        count += 1
    conn.commit()
    return count


def set_vendor_score(conn: sqlite3.Connection, day: str, score: float) -> None:
    """Den Score der Vergleichs-App (Bevel) für einen Tag ablegen.

    Liegt für den Tag noch keine Wellness-Zeile vor, entsteht eine mit leerem
    Rest – der nächste Sync füllt sie auf, ohne den Wert zu überschreiben.
    """
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO wellness (date, readiness_vendor, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            readiness_vendor=excluded.readiness_vendor, updated_at=excluded.updated_at
        """,
        (day, score, now),
    )
    conn.commit()


def vendor_scores(conn: sqlite3.Connection, days: int = 14) -> dict[str, float]:
    rows = conn.execute(
        "SELECT date, readiness_vendor FROM wellness "
        "WHERE readiness_vendor IS NOT NULL ORDER BY date DESC LIMIT ?",
        (days,),
    ).fetchall()
    return {r["date"]: r["readiness_vendor"] for r in rows}


def delete_activities(conn: sqlite3.Connection, source_ids: list[str]) -> int:
    """Löscht Aktivitäten anhand ihrer intervals-ID. Nur für Dubletten gedacht."""
    if not source_ids:
        return 0
    conn.executemany("DELETE FROM activity WHERE source_id = ?", [(i,) for i in source_ids])
    conn.commit()
    return len(source_ids)


def upsert_events(conn: sqlite3.Connection, rows: Iterable[dict[str, Any]]) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    count = 0
    for raw in rows:
        row = map_event(raw)
        if not row["id"]:
            continue
        conn.execute(
            """
            INSERT INTO event (id, date, sport, category, name, load, duration_s,
                distance_m, intensity, description, raw, updated_at)
            VALUES (:id, :date, :sport, :category, :name, :load, :duration_s,
                :distance_m, :intensity, :description, :raw, :updated_at)
            ON CONFLICT(id) DO UPDATE SET
                date=excluded.date, sport=excluded.sport, category=excluded.category,
                name=excluded.name, load=excluded.load, duration_s=excluded.duration_s,
                distance_m=excluded.distance_m, intensity=excluded.intensity,
                description=excluded.description, raw=excluded.raw,
                updated_at=excluded.updated_at
            """,
            {**row, "updated_at": now},
        )
        count += 1
    conn.commit()
    return count


# ------------------------------------------------------------------ Queries


def activities_between(conn: sqlite3.Connection, start: date, end: date) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM activity WHERE date BETWEEN ? AND ? ORDER BY start_local",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [dict(r) for r in rows]


def wellness_between(conn: sqlite3.Connection, start: date, end: date) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM wellness WHERE date BETWEEN ? AND ? ORDER BY date",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [dict(r) for r in rows]


def recent_activities(conn: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM activity ORDER BY start_local DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def events_on(conn: sqlite3.Connection, day: date) -> list[dict[str, Any]]:
    """Geplante Einheiten eines Tages, nach Startzeit und Anlage sortiert."""
    rows = conn.execute(
        "SELECT * FROM event WHERE date = ? AND COALESCE(category, 'WORKOUT') = 'WORKOUT' ORDER BY id",
        (day.isoformat(),),
    ).fetchall()
    return [dict(r) for r in rows]


def event_by_id(conn: sqlite3.Connection, event_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM event WHERE id = ?", (event_id,)).fetchone()
    return dict(row) if row else None


def events_between(conn: sqlite3.Connection, start: date, end: date) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM event WHERE date BETWEEN ? AND ? AND COALESCE(category, 'WORKOUT') = 'WORKOUT' ORDER BY date, id",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [dict(r) for r in rows]


def upcoming_events(conn: sqlite3.Connection, today: date, limit: int = 3) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM event WHERE date >= ? ORDER BY date, id LIMIT ?",
        (today.isoformat(), limit),
    ).fetchall()
    return [dict(r) for r in rows]


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "activities": conn.execute("SELECT COUNT(*) FROM activity").fetchone()[0],
        "wellness": conn.execute("SELECT COUNT(*) FROM wellness").fetchone()[0],
        "events": conn.execute("SELECT COUNT(*) FROM event").fetchone()[0],
    }


def first_last(conn: sqlite3.Connection) -> tuple[str | None, str | None]:
    row = conn.execute("SELECT MIN(date), MAX(date) FROM activity").fetchone()
    return row[0], row[1]


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO setting (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()


def get_setting(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM setting WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def wellness_epoch(conn: sqlite3.Connection) -> date | None:
    """Erste Nacht mit dem aktuellen Sensor – Referenzbeginn (D-31)."""
    raw = get_setting(conn, "wellness_epoch")
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def set_wellness_epoch(conn: sqlite3.Connection, epoch: date | None) -> None:
    if epoch is None:
        conn.execute("DELETE FROM setting WHERE key = 'wellness_epoch'")
    else:
        set_setting(conn, "wellness_epoch", epoch.isoformat())
    conn.commit()


def log_sync(
    conn: sqlite3.Connection,
    source: str,
    started: datetime,
    status: str,
    detail: str,
) -> None:
    conn.execute(
        "INSERT INTO sync_run (source, started_at, finished_at, status, detail) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            source,
            started.isoformat(timespec="seconds"),
            datetime.now().isoformat(timespec="seconds"),
            status,
            detail,
        ),
    )
    conn.commit()


def last_sync(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT finished_at FROM sync_run WHERE status = 'ok' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def date_span(conn: sqlite3.Connection) -> tuple[date | None, date | None]:
    row = conn.execute("SELECT MIN(date), MAX(date) FROM wellness").fetchone()
    if not row or not row[0]:
        return None, None
    return date.fromisoformat(row[0]), date.fromisoformat(row[1])


def days_back(today: date, days: int) -> date:
    return today - timedelta(days=max(days, 1) - 1)
