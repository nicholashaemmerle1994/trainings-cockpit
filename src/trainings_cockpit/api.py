"""FastAPI-Anwendung: API und Auslieferung des gebauten Frontends."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta
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
from .planner.dates import (
    local_today,
    parse_week_parameter,
    planner_week_range,
    rolling_dashboard_range,
    start_of_planner_week,
)
from .planner.details import build_plan_detail
from .planner.drafts import (
    DraftProjectionError,
    build_draft,
    build_draft_projection,
    build_new_draft,
    build_new_draft_projection,
)
from .planner.operations import (
    SqliteOperationStore,
    plan_to_json,
    retention_cutoff,
)
from .planner.save import SaveCoordinator, SaveOutcome, SaveState
from .planner.service import (
    event_delete_service,
    event_read_service,
    event_write_service,
)
from .planner.summaries import recorded_seconds
from .planner.syncmerge import merge_confirmed_event
from .planner.week import (
    SOURCE_COMPLETE,
    SOURCE_EMPTY,
    SOURCE_ERROR,
    SOURCE_PARTIAL,
    SOURCE_UNAVAILABLE,
    account_context,
    build_planner_week,
    coverage_for_period,
)

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
    settings = get_settings()
    today = date.fromisoformat(local_today(settings.time_zone))
    with connection() as conn:
        data = metrics.build_overview(conn, today=today, days=days)
        data["account_id"], data["athlete_id"] = account_context(conn)
        # Die Tageskarte darf „Nichts geplant“ nur sagen, wenn der
        # Planungsanteil tatsächlich gelesen wurde. Der Zustand kommt aus
        # derselben Abdeckungslogik wie die Wochenprojektion.
        plan_rows = db.events_on(conn, today)
        period = planner_week_range(today.isoformat(), settings.time_zone)
        coverage = coverage_for_period(
            period, _sync_range(conn), to_field="events_to"
        )
        state = _source_state(plan_rows, coverage=coverage, error=None)
        data["today"]["plan_source"] = {
            "state": state,
            "complete": state in {SOURCE_COMPLETE, SOURCE_EMPTY},
            "count": len(plan_rows),
            "coverage": coverage,
        }
    data["goals"] = _goals(settings, today)
    data["time_zone"] = settings.time_zone
    return data


def _goals(settings: Settings, today: date | None = None) -> list[dict[str, Any]]:
    today = today or date.today()
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


def _sync_range(conn: sqlite3.Connection) -> dict[str, Any]:
    """Der zuletzt tatsächlich gelesene Bereich, sofern der Sync ihn hinterließ."""
    raw = db.get_setting(conn, "synced_range")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _source_state(
    rows: list[dict[str, Any]],
    *,
    coverage: str,
    error: str | None,
) -> str:
    if error:
        return SOURCE_ERROR
    if rows:
        # Liegt die Woche nur teilweise im nachweislich gelesenen Bereich,
        # sind die vorhandenen Zeilen sichtbar, aber die Summe ist keine
        # vollständige Wochensumme. Das muss die Oberfläche kennzeichnen.
        return SOURCE_PARTIAL if coverage == "uncovered" else SOURCE_COMPLETE
    # Eine Woche außerhalb des nachweislich gelesenen Bereichs ist nicht
    # „bestätigt leer“. Ohne Sync-Marke bleibt der lokale Bestand maßgeblich.
    if coverage == "uncovered":
        return SOURCE_UNAVAILABLE
    return SOURCE_EMPTY


def _week_parameter(
    week: str | None,
    woche: str | None = None,
    von: str | None = None,
    bis: str | None = None,
) -> str | None:
    """Deutsche und englische Parameter auf einen Wochenanker abbilden."""
    if week and woche and week != woche:
        raise HTTPException(status_code=400, detail="week und woche widersprechen sich.")
    if week or woche:
        return week or woche
    # Ein Bereich wird nach Abschnitt 5.7 über sein Enddatum verankert.
    return bis or von


def _planner_week(conn: sqlite3.Connection, parameter: str | None) -> dict[str, Any]:
    settings = get_settings()
    time_zone = settings.time_zone
    today = local_today(time_zone)
    try:
        monday = parse_week_parameter(parameter, time_zone)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Woche als lokales Datum JJJJ-MM-TT angeben.",
        ) from exc
    period = planner_week_range(monday, time_zone)
    account_id, athlete_id = account_context(conn)
    sync_range = _sync_range(conn)

    plans_error: str | None = None
    plans_rows: list[dict[str, Any]] = []
    try:
        plans_rows = db.events_between(
            conn,
            date.fromisoformat(period.start_date),
            date.fromisoformat(period.end_date),
        )
    except Exception as exc:  # noqa: BLE001 - Quellenfehler getrennt melden
        plans_error = str(exc)[:300]

    activities_error: str | None = None
    activity_rows: list[dict[str, Any]] = []
    try:
        activity_rows = db.training_between(
            conn,
            date.fromisoformat(period.start_date),
            date.fromisoformat(period.end_date),
        )
    except Exception as exc:  # noqa: BLE001 - die andere Quelle bleibt nutzbar
        activities_error = str(exc)[:300]

    plans_coverage = coverage_for_period(period, sync_range, to_field="events_to")
    activities_coverage = coverage_for_period(
        period, sync_range, to_field="activities_to", today=today
    )
    plans_state = _source_state(
        plans_rows, coverage=plans_coverage, error=plans_error
    )
    activities_state = _source_state(
        activity_rows, coverage=activities_coverage, error=activities_error
    )

    speeds = plan.speeds(conn, today=date.fromisoformat(today))
    payload = build_planner_week(
        period,
        plans_rows,
        activity_rows,
        today=today,
        time_zone=time_zone,
        account_id=account_id,
        athlete_id=athlete_id,
        plans_state=plans_state,
        activities_state=activities_state,
        plans_error=plans_error,
        activities_error=activities_error,
        plans_coverage=plans_coverage,
        activities_coverage=activities_coverage,
        speeds_kmh=speeds,
    )
    payload["account_id"] = account_id
    payload["athlete_id"] = athlete_id
    payload["generated_at"] = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )
    return payload


@app.get("/api/planner")
def planner(
    week: str | None = Query(None, description="Montag oder Tag der Woche, JJJJ-MM-TT"),
    woche: str | None = Query(None, description="Deutscher Alias für week"),
    von: str | None = Query(None, description="Bereichsbeginn, JJJJ-MM-TT"),
    bis: str | None = Query(None, description="Bereichsende, JJJJ-MM-TT"),
) -> dict[str, Any]:
    """Eine Kalenderwoche mit getrennten Quellenzuständen."""
    with connection() as conn:
        return _planner_week(conn, _week_parameter(week, woche, von, bis))


@app.get("/api/planner/week")
def planner_week(
    week: str | None = Query(None, description="Montag oder Tag der Woche, JJJJ-MM-TT"),
    woche: str | None = Query(None, description="Deutscher Alias für week"),
    von: str | None = Query(None, description="Bereichsbeginn, JJJJ-MM-TT"),
    bis: str | None = Query(None, description="Bereichsende, JJJJ-MM-TT"),
) -> dict[str, Any]:
    """Alias für Verlinkungen, die den Wochenvertrag ausdrücklich nennen."""
    with connection() as conn:
        return _planner_week(conn, _week_parameter(week, woche, von, bis))


@app.post("/api/planner/draft/new")
def plan_new_draft(body: dict[str, Any]) -> dict[str, Any]:
    """Projiziert einen neuen lokalen Entwurf, ohne ein Event anzulegen."""
    settings = get_settings()
    with connection() as conn:
        account_id, athlete_id = account_context(conn)
        try:
            return build_new_draft_projection(
                body,
                time_zone=settings.time_zone,
                account_id=account_id,
                athlete_id=athlete_id,
                zone_profiles=plan.sport_profiles(conn),
            )
        except DraftProjectionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:300]) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:300]) from exc


def _operation_payload(stored: Any) -> dict[str, Any]:
    snapshot = stored.snapshot
    return {
        "operation_id": str(snapshot.operation_id),
        "local_id": str(snapshot.local_id),
        "draft_id": str(snapshot.draft_id),
        "remote_id": str(snapshot.remote_id) if snapshot.remote_id is not None else None,
        "external_id": snapshot.external_id,
        "mode": snapshot.mode,
        "kind": snapshot.kind,
        "state": "unknown"
        if stored.state is SaveState.SAVING
        else stored.state.value,
        "created_at": snapshot.created_at,
        "reconciliation_required": True,
    }


@app.get("/api/planner/operations")
def planner_operations(open_only: bool = Query(True)) -> dict[str, Any]:
    """Offene Vorgänge des aktuellen Accounts, ohne vollständige Payloads."""
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    with connection() as conn:
        account_id, athlete_id = account_context(conn)
        store = SqliteOperationStore(conn)
        store.purge_completed(now=retention_cutoff(now))
        records = store.records(
            account_id=account_id,
            athlete_id=athlete_id,
            open_only=open_only,
        )
        return {
            "account_id": account_id,
            "athlete_id": athlete_id,
            "items": [_operation_payload(item) for item in records],
        }


@app.post("/api/planner/operations/{operation_id}/reconcile")
def planner_reconcile(operation_id: str) -> dict[str, Any]:
    """Setzt einen offenen Vorgang lesend fort; wiederholt keinen Write."""
    settings = get_settings()
    with connection() as conn:
        account_id, athlete_id = account_context(conn)
        store = SqliteOperationStore(conn)
        stored = store.record(operation_id)
        if stored is None or (
            stored.snapshot.account_id != account_id
            or stored.snapshot.athlete_id != athlete_id
        ):
            raise HTTPException(status_code=404, detail="Offener Vorgang nicht gefunden")
        try:
            with event_write_service(settings) as service:
                coordinator = SaveCoordinator(service, recorder=store, shared=True)
                coordinator.restore_open(
                    account_id=account_id, athlete_id=athlete_id
                )
                outcome = coordinator.reconcile(operation_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Vorgang ist nicht offen") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)[:300]) from exc
        # Ein lesend abgeglichener, bestätigter Datensatz gehört wie beim
        # direkten Save in den vorhandenen lokalen Bestand. Sonst würde die
        # Planerwoche den gerade bestätigten Create nicht zeigen.
        _persist_confirmed(conn, outcome)
        confirmed = (
            plan_to_json(outcome.confirmed)
            if outcome.confirmed is not None
            else None
        )
        date_value = (
            outcome.confirmed.date
            if outcome.confirmed is not None
            else (
                outcome.snapshot.intended.date
                if outcome.snapshot is not None
                else None
            )
        )
        return {
            "status": outcome.status.as_dict(),
            "confirmed": confirmed,
            "week": (
                start_of_planner_week(date_value, settings.time_zone)
                if date_value is not None
                else None
            ),
            "time_zone": settings.time_zone,
        }


def _save_response(
    outcome: SaveOutcome,
    *,
    time_zone: str,
    old_week: str | None,
) -> dict[str, Any]:
    snapshot = outcome.snapshot
    confirmed = outcome.confirmed
    date_value = (
        confirmed.date
        if confirmed is not None
        else (snapshot.intended.date if snapshot is not None else None)
    )
    week = (
        start_of_planner_week(date_value, time_zone) if date_value is not None else None
    )
    return {
        "status": outcome.status.as_dict(),
        "confirmed": plan_to_json(confirmed) if confirmed is not None else None,
        "event_id": outcome.status.remote_id,
        "week": week,
        "old_week": old_week,
        "time_zone": time_zone,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def _persist_confirmed(conn: Any, outcome: SaveOutcome) -> None:
    """Nur bestätigte Reads in den vorhandenen Bestand übernehmen."""
    if outcome.status.state is not SaveState.SAVED or outcome.remote_raw is None:
        return
    merge_confirmed_event(conn, outcome.remote_raw)


@app.post("/api/planner/plan/{event_id}/save")
def plan_save(event_id: int, body: dict[str, Any]) -> dict[str, Any]:
    """Speichert einen bestehenden Entwurf über den bestätigten Update-Pfad."""
    settings = get_settings()
    with connection() as conn:
        row = db.event_by_id(conn, event_id)
        if not row:
            raise HTTPException(status_code=404, detail="Planung nicht gefunden")
        account_id, athlete_id = account_context(conn)
        try:
            draft = build_draft(
                row,
                body,
                time_zone=settings.time_zone,
                account_id=account_id,
                athlete_id=athlete_id,
                zone_profiles=plan.sport_profiles(conn),
            )
        except DraftProjectionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:300]) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:300]) from exc
        old_week = (
            start_of_planner_week(draft.base.date, settings.time_zone)
            if draft.base
            else None
        )
        store = SqliteOperationStore(conn)
        try:
            with event_write_service(settings) as service:
                coordinator = SaveCoordinator(service, recorder=store, shared=True)
                outcome = coordinator.activate(
                    draft,
                    account_id=account_id,
                    athlete_id=athlete_id,
                    writable=draft.current.is_metadata_editable,
                    writable_reason=draft.current.editability_reason,
                )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)[:300]) from exc
        _persist_confirmed(conn, outcome)
        return _save_response(outcome, time_zone=settings.time_zone, old_week=old_week)


@app.post("/api/planner/draft/save")
def new_plan_save(body: dict[str, Any]) -> dict[str, Any]:
    """Legt genau eine neue Einheit über den bestätigten Create-Pfad an."""
    settings = get_settings()
    with connection() as conn:
        account_id, athlete_id = account_context(conn)
        try:
            draft = build_new_draft(
                body,
                time_zone=settings.time_zone,
                zone_profiles=plan.sport_profiles(conn),
            )
        except DraftProjectionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:300]) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:300]) from exc
        store = SqliteOperationStore(conn)
        try:
            with event_write_service(settings) as service:
                coordinator = SaveCoordinator(service, recorder=store, shared=True)
                outcome = coordinator.activate(
                    draft,
                    account_id=account_id,
                    athlete_id=athlete_id,
                    writable=True,
                )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)[:300]) from exc
        _persist_confirmed(conn, outcome)
        return _save_response(outcome, time_zone=settings.time_zone, old_week=None)


@app.delete("/api/planner/plan/{event_id}")
def plan_delete(event_id: int) -> dict[str, Any]:
    """Löscht eine geplante Einheit in intervals.icu und im lokalen Bestand.

    Eine bereits extern gelöschte Einheit blockiert das Löschen nicht: der
    404 der Quelle wird als „nicht mehr vorhanden“ gelesen und die lokale
    Zeile trotzdem entfernt. Andere Quellenfehler lassen den Bestand stehen,
    damit kein Löschvorgang unbemerkt nur halb ausgeführt wird.
    """
    settings = get_settings()
    if not settings.intervals_key:
        raise HTTPException(status_code=400, detail="Kein intervals.icu-Key konfiguriert.")
    with connection() as conn:
        row = db.event_by_id(conn, event_id)
        if not row:
            raise HTTPException(status_code=404, detail="Planung nicht gefunden")
        week = start_of_planner_week(str(row["date"])[:10], settings.time_zone)
        try:
            with event_delete_service(settings) as service:
                outcome = service.delete(str(event_id))
        except Exception as exc:  # noqa: BLE001 - Quellenfehler an die UI durchreichen
            raise HTTPException(
                status_code=502,
                detail=f"Löschen in intervals.icu fehlgeschlagen: {str(exc)[:300]}",
            ) from exc
        db.delete_event(conn, event_id)
        return {
            "deleted": True,
            "event_id": event_id,
            "week": week,
            **outcome.as_dict(),
        }


@app.get("/api/planner/plan/{event_id}/remote")
def plan_remote(event_id: int) -> dict[str, Any]:
    """Liest die aktuelle Remoteversion und übernimmt sie als Lese-Datenstand.

    Die Aktion ist rein lesend gegenüber intervals.icu. Der bestätigte
    Remote-Datensatz wird lokal über dieselbe Event-ID eingesortiert; es gibt
    keinen Event-Write.
    """
    settings = get_settings()
    with connection() as conn:
        row = db.event_by_id(conn, event_id)
        if not row:
            raise HTTPException(status_code=404, detail="Planung nicht gefunden")
        try:
            with event_read_service(settings) as client:
                raw = client.event(event_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)[:300]) from exc
        if not isinstance(raw, dict) or str(raw.get("id")) != str(event_id):
            raise HTTPException(
                status_code=409,
                detail="Die Remote-Antwort gehört nicht zu dieser Event-ID.",
            )
        merge_confirmed_event(conn, raw)
        updated = db.event_by_id(conn, event_id)
        account_id, athlete_id = account_context(conn)
        try:
            return build_plan_detail(
                updated or row,
                time_zone=settings.time_zone,
                account_id=account_id,
                athlete_id=athlete_id,
                zone_profiles=plan.sport_profiles(conn),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:300]) from exc


@app.get("/api/planner/plan/{event_id}")
@app.get("/api/plan/{event_id}")
def plan_detail(event_id: int) -> dict[str, Any]:
    """Planungsdetails über die vorhandene Event-Identität, rein lesend."""
    with connection() as conn:
        row = db.event_by_id(conn, event_id)
        if not row:
            raise HTTPException(status_code=404, detail="Planung nicht gefunden")
        settings = get_settings()
        account_id, athlete_id = account_context(conn)
        try:
            return build_plan_detail(
                row,
                time_zone=settings.time_zone,
                account_id=account_id,
                athlete_id=athlete_id,
                zone_profiles=plan.sport_profiles(conn),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:300]) from exc


@app.post("/api/planner/plan/{event_id}/draft")
def plan_draft(
    event_id: int,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Projiziert einen lokalen Entwurf, ohne Remote zu lesen oder zu schreiben."""
    with connection() as conn:
        row = db.event_by_id(conn, event_id)
        if not row:
            raise HTTPException(status_code=404, detail="Planung nicht gefunden")
        settings = get_settings()
        account_id, athlete_id = account_context(conn)
        try:
            return build_draft_projection(
                row,
                body,
                time_zone=settings.time_zone,
                account_id=account_id,
                athlete_id=athlete_id,
                zone_profiles=plan.sport_profiles(conn),
            )
        except DraftProjectionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:300]) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:300]) from exc


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
def week(
    week: str | None = Query(None, description="Wochenanker, JJJJ-MM-TT"),
    from_date: str | None = Query(None, alias="from", description="Beginn, JJJJ-MM-TT"),
    to_date: str | None = Query(None, alias="to", description="Ende, JJJJ-MM-TT"),
) -> dict[str, Any]:
    """Zeitraum der Aufzeichnungen.

    Ohne Parameter bleibt die bisherige rollierende Sieben-Tage-Antwort
    unverändert. Mit ``week`` oder expliziten Grenzen liefert dieselbe route
    einen gezielten Zeitraum; der Planer selbst nutzt ``/api/planner``.
    """
    settings = get_settings()
    today = date.fromisoformat(local_today(settings.time_zone))
    try:
        if week:
            monday = parse_week_parameter(week, settings.time_zone)
            period = planner_week_range(monday, settings.time_zone)
            start = date.fromisoformat(period.start_date)
            end = date.fromisoformat(period.end_date)
        elif from_date or to_date:
            if from_date and to_date:
                start = date.fromisoformat(from_date)
                end = date.fromisoformat(to_date)
            elif from_date:
                start = date.fromisoformat(from_date)
                end = start + timedelta(days=6)
            else:
                end = date.fromisoformat(str(to_date))
                start = end - timedelta(days=6)
        else:
            period = rolling_dashboard_range(today.isoformat(), 7, settings.time_zone)
            start = date.fromisoformat(period.start_date)
            end = date.fromisoformat(period.end_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Zeitraum als lokales Datum JJJJ-MM-TT angeben.",
        ) from exc
    if end < start:
        raise HTTPException(status_code=400, detail="Das Ende liegt vor dem Beginn.")
    with connection() as conn:
        rows = db.training_between(conn, start, end)
    seconds = sum(recorded_seconds(row) for row in rows)
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
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
