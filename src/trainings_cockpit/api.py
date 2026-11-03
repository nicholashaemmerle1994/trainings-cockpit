"""FastAPI-Anwendung: API und Auslieferung des gebauten Frontends."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db, fuel, metrics, plan, streams
from . import sync as sync_mod
from .config import PROJECT_ROOT, Settings

DIST = Path(os.getenv("TC_WEB_DIST") or (PROJECT_ROOT / "web" / "dist"))

app = FastAPI(title="Trainings-Cockpit", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.load()


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    settings = get_settings()
    conn = db.connect(settings.db_path)
    try:
        db.init_db(conn)
        yield conn
    finally:
        conn.close()


@app.get("/api/overview")
def overview(days: int = Query(90, ge=7, le=365)) -> dict[str, Any]:
    with connection() as conn:
        data = metrics.build_overview(conn, days=days)
    data["goals"] = _goals(get_settings())
    return data


def _goals(settings: Settings) -> list[dict[str, Any]]:
    today = date.today()
    items: list[dict[str, Any]] = []
    for goal in settings.goals:
        try:
            target = date.fromisoformat(goal["date"])
        except (KeyError, ValueError):
            continue
        days = (target - today).days
        if days < 0:
            continue
        items.append(
            {
                "name": goal["name"],
                "date": target.isoformat(),
                "days": days,
                "priority": goal.get("priority", "C"),
            }
        )
    return sorted(items, key=lambda item: item["date"])


@app.get("/api/session/{event_id}")
def session(event_id: int) -> dict[str, Any]:
    """Eine geplante Einheit mit Aufbau, Verpflegung und Ist-Abgleich."""
    with connection() as conn:
        event = db.event_by_id(conn, event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Einheit nicht gefunden")
        data = plan.session(conn, event)
        _add_series(conn, data)
        return data


def _add_series(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    """Den Verlauf der zugehörigen Aufzeichnung an das Ist hängen (D-53)."""
    actual = data.get("actual")
    if not isinstance(actual, dict) or actual.get("row_id") is None:
        return
    row = db.activity_by_row_id(conn, int(actual["row_id"]))
    actual["series"] = streams.payload(conn, row) if row else None


@app.get("/api/week")
def week() -> dict[str, Any]:
    """Die Einheiten der letzten sieben Tage — dieselbe Summe wie auf der Karte."""
    with connection() as conn:
        today = date.today()
        start = today - timedelta(days=6)
        rows = db.training_between(conn, start, today)
    seconds = sum((row.get("moving_s") or row.get("duration_s") or 0) for row in rows)
    return {
        "from": start.isoformat(),
        "to": today.isoformat(),
        "seconds": int(seconds),
        "load": round(sum(row.get("load") or 0 for row in rows)),
        "units": [metrics.activity_payload(row) for row in rows],
    }


@app.get("/api/unit/{row_id}")
def unit(row_id: int) -> dict[str, Any]:
    """Eine erledigte Einheit mit Zonen, Puls, Quelle und Verlauf."""
    with connection() as conn:
        row = db.activity_by_row_id(conn, row_id)
        if not row:
            raise HTTPException(status_code=404, detail="Einheit nicht gefunden")
        data = metrics.unit_payload(row)
        data["series"] = streams.payload(conn, row)
        return data


@app.get("/api/activities")
def activities(
    limit: int = Query(50, ge=1, le=500),
    sport: str | None = None,
) -> dict[str, Any]:
    with connection() as conn:
        if sport:
            rows = conn.execute(
                "SELECT * FROM activity WHERE sport = ? ORDER BY start_local DESC LIMIT ?",
                (sport, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM activity ORDER BY start_local DESC LIMIT ?", (limit,)
            ).fetchall()
        items = [metrics.activity_payload(dict(r)) for r in rows]
        sports = conn.execute(
            "SELECT sport, COUNT(*) AS n FROM activity GROUP BY sport ORDER BY n DESC"
        ).fetchall()
        return {
            "items": items,
            "sports": [{"sport": r["sport"], "count": r["n"]} for r in sports],
            "total": conn.execute("SELECT COUNT(*) FROM activity").fetchone()[0],
        }


@app.post("/api/vendor-score")
def save_vendor_score(
    day: str = Query(..., description="JJJJ-MM-TT"),
    score: float = Query(..., ge=0, le=100),
) -> dict[str, Any]:
    try:
        target = date.fromisoformat(day)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Datum als JJJJ-MM-TT angeben.") from exc
    with connection() as conn:
        db.set_vendor_score(conn, target.isoformat(), score)
        saved = db.vendor_scores(conn, 30)
    return {"date": target.isoformat(), "score": score, "saved": saved.get(target.isoformat())}


@app.get("/api/fuel")
def fuel_plan(
    minutes: int = Query(120, ge=20, le=900),
    mode: str = Query("locker"),
    weight: float | None = Query(None, ge=35, le=160),
    temp: int = Query(18, ge=-10, le=45),
    source: str = Query("gel"),
    shot: float = Query(35, ge=10, le=250),
    unit: str = Query("g"),
) -> dict[str, Any]:
    if mode not in fuel.MODES:
        raise HTTPException(status_code=400, detail=f"Unbekannter Modus: {mode}")
    if source not in fuel.SOURCES:
        raise HTTPException(status_code=400, detail=f"Unbekannte Quelle: {source}")
    if unit not in ("g", "ml"):
        raise HTTPException(status_code=400, detail=f"Unbekannte Einheit: {unit}")
    if weight is None:
        weight = _last_weight() or 78.0
    plan = fuel.plan(
        minutes=minutes,
        mode=mode,
        weight_kg=weight,
        temp_c=temp,
        source=source,
        shot_ml=shot / fuel.SYRUP_DENSITY_G_PER_ML if unit == "g" else shot,
        shot_unit=unit,
    )
    plan["modes"] = [
        {"key": key, "label": value["label"], "hint": value["hint"]}
        for key, value in fuel.MODES.items()
    ]
    plan["sources"] = [
        {"key": key, "label": value["label"], "hint": value["hint"]}
        for key, value in fuel.SOURCES.items()
    ]
    return plan


def _last_weight() -> float | None:
    with connection() as conn:
        row = conn.execute(
            "SELECT weight_kg FROM wellness WHERE weight_kg IS NOT NULL "
            "ORDER BY date DESC LIMIT 1"
        ).fetchone()
    return float(row[0]) if row else None


@app.post("/api/sync")
def run_sync(days: int = Query(365, ge=7, le=730)) -> dict[str, Any]:
    settings = get_settings()
    if not settings.intervals_key:
        raise HTTPException(status_code=400, detail="Kein intervals.icu-Key konfiguriert.")
    try:
        return sync_mod.sync(settings, days=days)
    except Exception as exc:  # noqa: BLE001 - Fehler an die UI durchreichen
        raise HTTPException(status_code=502, detail=str(exc)[:300]) from exc


@app.get("/api/health")
def health() -> dict[str, Any]:
    with connection() as conn:
        first, last = db.first_last(conn)
        return {
            "status": "ok",
            "database": str(get_settings().db_path),
            **db.counts(conn),
            "first_activity": first,
            "last_activity": last,
            "last_sync": db.last_sync(conn),
        }


if DIST.exists():
    assets = DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(DIST / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate: Path = DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
