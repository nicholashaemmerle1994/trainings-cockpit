"""Sichere Wochen- und Blockkopie über den bestehenden Speicherweg.

Die Vorschau liest ausschließlich. Der Job persistiert Quelle, Ziel und
Knoten-Snapshot, bevor ein Item über den vorhandenen ``SaveCoordinator``
angelegt wird. Jeder ``advance`` verarbeitet genau ein Item; ein Claim
verhindert parallele Bulk-Creates. Unklare Vorgänge werden nur lesend
abgeglichen und nie automatisch wiederholt.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any

from .. import db, plan
from .clone import CloneError, clone_for_new_plan
from .dates import local_today, planner_week_range
from .details import plan_nodes_payload, read_plan_row
from .drafts import DraftProjectionError, build_new_draft
from .links import resolve_relationships
from .operations import SqliteOperationStore
from .save import SaveCoordinator, SaveState
from .syncmerge import merge_confirmed_event
from .validation import calculate_known_totals
from .week import (
    SOURCE_COMPLETE,
    SOURCE_EMPTY,
    SOURCE_PARTIAL,
    SOURCE_UNAVAILABLE,
    build_planner_week,
    coverage_for_period,
)

MAX_WEEKS = 4
LEASE_SECONDS = 30
PROVENANCE_STATES = ("pending", "created", "saved_unverified", "unknown", "conflict")
TERMINAL_JOB_STATES = ("completed", "partial", "failed")


class CopyCode(StrEnum):
    INVALID_SOURCE = "invalid_source"
    INVALID_TARGET = "invalid_target"
    INVALID_WEEKS = "invalid_weeks"
    OVERLAP = "overlap"
    SOURCE_COVERAGE = "source_coverage"
    TARGET_COVERAGE = "target_coverage"
    SOURCE_NOT_CLONEABLE = "source_not_cloneable"
    NO_ITEMS = "no_items"
    COPY_RUNNING = "copy_running"
    COPY_BUSY = "copy_busy"
    PREVIEW_CHANGED = "preview_changed"
    NOT_FOUND = "not_found"
    INVALID_REQUEST = "invalid_request"


class CopyError(ValueError):
    def __init__(
        self,
        code: CopyCode,
        message: str,
        *,
        status: int = 422,
        blockers: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.blockers = blockers or []


@dataclass(frozen=True, slots=True)
class _SourceItem:
    source_event_id: str
    source_date: str
    target_date: str
    name: str
    sport: str
    seconds: int | None
    metres: int | None
    nodes: tuple[Any, ...]
    clone_error: str | None = None


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sync_range(conn: sqlite3.Connection) -> dict[str, Any]:
    raw = db.get_setting(conn, "synced_range")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _source_state(rows: list[dict[str, Any]], *, coverage: str) -> str:
    if rows:
        return SOURCE_PARTIAL if coverage == "uncovered" else SOURCE_COMPLETE
    if coverage == "uncovered":
        return SOURCE_UNAVAILABLE
    return SOURCE_EMPTY


def _parse_week_start(value: object, code: CopyCode) -> date:
    if not isinstance(value, str) or not value.strip():
        raise CopyError(code, "Ein lokales Startdatum ist erforderlich.")
    try:
        parsed = date.fromisoformat(value.strip()[:10])
    except ValueError as exc:
        raise CopyError(code, "Das lokale Startdatum ist ungültig.") from exc
    return parsed - timedelta(days=parsed.weekday())


def _week_payload(
    conn: sqlite3.Connection,
    week_start: date,
    *,
    time_zone: str,
    account_id: str,
    athlete_id: str,
) -> dict[str, Any]:
    period = planner_week_range(week_start.isoformat(), time_zone)
    plan_rows = db.events_between(conn, week_start, week_start + timedelta(days=6))
    activity_rows = db.training_between(conn, week_start, week_start + timedelta(days=6))
    coverage = coverage_for_period(period, _sync_range(conn), to_field="events_to")
    relationships, _ = resolve_relationships(
        plan_rows,
        activity_rows,
        db.plan_links(conn, account_id=account_id, athlete_id=athlete_id),
        account_id=account_id,
        athlete_id=athlete_id,
    )
    payload = build_planner_week(
        period,
        plan_rows,
        activity_rows,
        today=local_today(time_zone),
        time_zone=time_zone,
        account_id=account_id,
        athlete_id=athlete_id,
        plans_state=_source_state(plan_rows, coverage=coverage),
        activities_state=_source_state(activity_rows, coverage=coverage),
        plans_coverage=coverage,
        activities_coverage=coverage,
        relationships=relationships,
        speeds_kmh=plan.speeds(conn, today=date.fromisoformat(local_today(time_zone))),
    )
    return {
        "coverage": coverage,
        "entries": [
            entry
            for day in payload["days"]
            for entry in day["entries"]
            if entry.get("kind") == "planned"
        ],
    }


def _provenance(
    conn: sqlite3.Connection, *, account_id: str, athlete_id: str
) -> set[tuple[str, str]]:
    markers = ", ".join("?" for _ in PROVENANCE_STATES)
    rows = conn.execute(
        f"SELECT source_event_id, target_date FROM planner_copy_item "  # noqa: S608
        f"WHERE account_id = ? AND athlete_id = ? AND state IN ({markers})",
        (account_id, athlete_id, *PROVENANCE_STATES),
    ).fetchall()
    return {(str(row["source_event_id"]), str(row["target_date"])) for row in rows}


def _active_job(
    conn: sqlite3.Connection, *, account_id: str, athlete_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM planner_copy_job j WHERE account_id = ? AND athlete_id = ? "
        "AND (state IN ('queued', 'running') OR (state IN ('partial', 'failed') "
        "AND EXISTS (SELECT 1 FROM planner_copy_item i WHERE i.job_id = j.job_id "
        "AND i.state IN ('unknown', 'saved_unverified')))) "
        "ORDER BY created_at DESC LIMIT 1",
        (account_id, athlete_id),
    ).fetchone()
    return dict(row) if row else None


def _existing_target_count(conn: sqlite3.Connection, start: date, end: date) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM event WHERE date BETWEEN ? AND ? "
        "AND COALESCE(category, 'WORKOUT') = 'WORKOUT'",
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    return int(row[0]) if row else 0


def _read_item(
    conn: sqlite3.Connection,
    entry: Mapping[str, Any],
    *,
    target_date: date,
    time_zone: str,
    account_id: str,
    athlete_id: str,
    draft_id: str | None = None,
) -> _SourceItem:
    event_id = entry.get("plan_id")
    if event_id is None:
        raise CopyError(
            CopyCode.SOURCE_NOT_CLONEABLE,
            "Eine Planung ohne Event-ID ist nicht kopierbar.",
        )
    row = db.event_by_id(conn, int(event_id))
    if row is None:
        raise CopyError(
            CopyCode.SOURCE_NOT_CLONEABLE,
            "Die Quellplanung ist lokal nicht mehr vorhanden.",
        )
    try:
        remote = read_plan_row(
            row,
            time_zone=time_zone,
            account_id=account_id,
            athlete_id=athlete_id,
        )
    except ValueError as exc:
        raise CopyError(
            CopyCode.SOURCE_NOT_CLONEABLE,
            "Die Quellplanung ist nicht lesbar.",
        ) from exc
    totals = calculate_known_totals(remote.plan)
    try:
        cloned, _ = clone_for_new_plan(
            remote.plan,
            target_date=target_date.isoformat(),
            time_zone=time_zone,
            account_id=account_id,
            athlete_id=athlete_id,
            keep_time=True,
            draft_id=draft_id,
        )
    except CloneError as exc:
        raise CopyError(CopyCode.SOURCE_NOT_CLONEABLE, exc.reason) from exc
    return _SourceItem(
        source_event_id=str(event_id),
        source_date=str(entry.get("date") or row["date"]),
        target_date=target_date.isoformat(),
        name=cloned.name,
        sport=cloned.sport,
        seconds=totals.duration_seconds,
        metres=totals.distance_metres,
        nodes=tuple(plan_nodes_payload(cloned.nodes)),
    )


def _validate_range(
    source_start: object,
    target_start: object,
    weeks: object,
    *,
    time_zone: str,
) -> tuple[date, date, int]:
    try:
        week_count = int(weeks)
    except (TypeError, ValueError) as exc:
        raise CopyError(CopyCode.INVALID_WEEKS, "Die Anzahl Wochen muss eine Zahl sein.") from exc
    if not 1 <= week_count <= MAX_WEEKS:
        raise CopyError(CopyCode.INVALID_WEEKS, "Es lassen sich 1 bis 4 Wochen kopieren.")
    source = _parse_week_start(source_start, CopyCode.INVALID_SOURCE)
    if target_start is None:
        target = source + timedelta(days=7 * week_count)
    else:
        target = _parse_week_start(target_start, CopyCode.INVALID_TARGET)
    return source, target, week_count


def preview_copy(
    conn: sqlite3.Connection,
    *,
    source_start: object,
    weeks: object,
    target_start: object,
    time_zone: str,
    account_id: str,
    athlete_id: str,
) -> dict[str, Any]:
    source, target, week_count = _validate_range(
        source_start, target_start, weeks, time_zone=time_zone
    )
    source_end = source + timedelta(days=7 * week_count - 1)
    target_end = target + timedelta(days=7 * week_count - 1)
    if not (target_end < source or target > source_end):
        return {
            "source_start": source.isoformat(),
            "source_end": source_end.isoformat(),
            "target_start": target.isoformat(),
            "target_end": target_end.isoformat(),
            "weeks": week_count,
            "time_zone": time_zone,
            "coverage": {"source": "unknown", "target": "unknown"},
            "blockers": [
                {
                    "code": CopyCode.OVERLAP.value,
                    "message": "Quell- und Zielblock dürfen sich nicht überschneiden.",
                    "date": target.isoformat(),
                }
            ],
            "warnings": [],
            "existing_target_count": 0,
            "items": [],
            "totals": {
                "items": 0,
                "seconds": 0,
                "metres": 0,
                "already_copied": 0,
                "blocked": 0,
            },
        }
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    provenance = _provenance(conn, account_id=account_id, athlete_id=athlete_id)
    active = _active_job(conn, account_id=account_id, athlete_id=athlete_id)
    if active is not None:
        blockers.append(
            {
                "code": CopyCode.COPY_RUNNING.value,
                "message": "Für diesen Account läuft bereits eine Kopie.",
                "date": None,
            }
        )

    source_items: list[_SourceItem] = []
    source_covered = True
    for index in range(week_count):
        week = source + timedelta(days=7 * index)
        payload = _week_payload(
            conn,
            week,
            time_zone=time_zone,
            account_id=account_id,
            athlete_id=athlete_id,
        )
        if payload["coverage"] != "covered":
            source_covered = False
            blockers.append(
                {
                    "code": CopyCode.SOURCE_COVERAGE.value,
                    "message": (
                        "Die Quellwoche ist nicht nachweislich vollständig geladen. "
                        "Es wird nichts kopiert."
                    ),
                    "date": week.isoformat(),
                }
            )
        for entry in payload["entries"]:
            target_date = target + (date.fromisoformat(str(entry["date"])) - source)
            try:
                item = _read_item(
                    conn,
                    entry,
                    target_date=target_date,
                    time_zone=time_zone,
                    account_id=account_id,
                    athlete_id=athlete_id,
                )
            except CopyError as exc:
                blockers.append(
                    {
                        "code": CopyCode.SOURCE_NOT_CLONEABLE.value,
                        "message": exc.message,
                        "date": str(entry.get("date") or ""),
                    }
                )
                continue
            source_items.append(item)

    target_covered = True
    tests: list[dict[str, Any]] = []
    for index in range(week_count):
        week = target + timedelta(days=7 * index)
        payload = _week_payload(
            conn,
            week,
            time_zone=time_zone,
            account_id=account_id,
            athlete_id=athlete_id,
        )
        if payload["coverage"] != "covered":
            target_covered = False
            blockers.append(
                {
                    "code": CopyCode.TARGET_COVERAGE.value,
                    "message": (
                        "Die Zielwoche ist nicht nachweislich vollständig geladen. "
                        "Es wird nichts kopiert."
                    ),
                    "date": week.isoformat(),
                }
            )
        tests.append(payload)

    existing_count = _existing_target_count(
        conn, target, target + timedelta(days=7 * week_count - 1)
    )
    if existing_count:
        warnings.append(
            {
                "code": "existing_target",
                "message": (
                    "Am Ziel liegen bereits Planungen. Sie bleiben unverändert; "
                    "es werden nur neue Einheiten ergänzt."
                ),
                "date": target.isoformat(),
            }
        )

    items: list[dict[str, Any]] = []
    ready_seconds = 0
    ready_metres = 0
    already = 0
    for item in sorted(source_items, key=lambda entry: (entry.target_date, entry.source_event_id)):
        copied = (item.source_event_id, item.target_date) in provenance
        status = "already_copied" if copied else "ready"
        if copied:
            already += 1
        else:
            ready_seconds += int(item.seconds or 0)
            ready_metres += int(item.metres or 0)
        items.append(
            {
                "source_event_id": item.source_event_id,
                "source_date": item.source_date,
                "target_date": item.target_date,
                "name": item.name,
                "sport": item.sport,
                "sport_label": plan.SPORT_LABELS.get(item.sport, item.sport),
                "seconds": item.seconds,
                "metres": item.metres,
                "status": status,
                "reason": None if copied else None,
            }
        )
    if not items:
        blockers.append(
            {
                "code": CopyCode.NO_ITEMS.value,
                "message": "In den Quellwochen liegen keine offenen Planungen.",
                "date": None,
            }
        )
    if not source_covered or not target_covered:
        # Die Coverage-Blöcke stehen bereits einzeln in der Liste.
        pass
    blockers = _unique_blockers(blockers)
    return {
        "source_start": source.isoformat(),
        "source_end": (source + timedelta(days=7 * week_count - 1)).isoformat(),
        "target_start": target.isoformat(),
        "target_end": (target + timedelta(days=7 * week_count - 1)).isoformat(),
        "weeks": week_count,
        "time_zone": time_zone,
        "coverage": {
            "source": "covered" if source_covered else "uncovered",
            "target": "covered" if target_covered else "uncovered",
        },
        "blockers": blockers,
        "warnings": warnings,
        "existing_target_count": existing_count,
        "items": items,
        "totals": {
            "items": len(items),
            "seconds": ready_seconds,
            "metres": ready_metres,
            "already_copied": already,
            "blocked": 0,
        },
    }


def _unique_blockers(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for blocker in blockers:
        key = (str(blocker.get("code")), str(blocker.get("date") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(blocker)
    return result


def _job_payload(conn: sqlite3.Connection, job_id: str) -> dict[str, Any]:
    job = conn.execute(
        "SELECT * FROM planner_copy_job WHERE job_id = ?", (job_id,)
    ).fetchone()
    if job is None:
        raise CopyError(CopyCode.NOT_FOUND, "Kopievorgang nicht gefunden.", status=404)
    items = [
        _item_public(dict(row))
        for row in conn.execute(
            "SELECT * FROM planner_copy_item WHERE job_id = ? ORDER BY ordinal, target_date",
            (job_id,),
        ).fetchall()
    ]
    counts = _counts(items)
    total = int(job["total"])
    state = str(job["state"])
    terminal = state in TERMINAL_JOB_STATES
    unresolved = any(
        item["state"] in ("unknown", "saved_unverified") for item in items
    )
    next_item = next((item for item in items if item["state"] == "pending"), None)
    return {
        "job": {
            "job_id": str(job["job_id"]),
            "client_request_id": str(job["client_request_id"]),
            "state": state,
            "source_start": str(job["source_start"]),
            "target_start": str(job["target_start"]),
            "weeks": int(job["weeks"]),
            "total": total,
            "created": counts["created"],
            "failed": counts["failed"],
            "pending": counts["pending"],
            "unknown": counts["unknown"],
            "message": str(job["message"]),
            "created_at": str(job["created_at"]),
            "updated_at": str(job["updated_at"]),
            "can_advance": bool(
                (not terminal and counts["pending"] > 0) or unresolved
            ),
            "next_target_date": next_item["target_date"] if next_item else None,
        },
        "items": items,
    }


def _counts(items: list[dict[str, Any]]) -> dict[str, int]:
    created = sum(1 for item in items if item["state"] == "created")
    failed = sum(1 for item in items if item["state"] in ("failed", "conflict"))
    unknown = sum(
        1 for item in items if item["state"] in ("unknown", "saved_unverified")
    )
    pending = sum(1 for item in items if item["state"] == "pending")
    return {
        "created": created,
        "failed": failed,
        "unknown": unknown,
        "pending": pending,
    }


def _item_public(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "item_id": str(item["item_id"]),
        "job_id": str(item["job_id"]),
        "source_event_id": str(item["source_event_id"]),
        "source_date": str(item["source_date"]),
        "target_date": str(item["target_date"]),
        "draft_id": str(item["draft_id"]),
        "local_id": str(item["local_id"]),
        "name": str(item["name"]),
        "sport": str(item["sport"]),
        "state": str(item["state"]),
        "operation_id": item["operation_id"],
        "remote_id": item["remote_id"],
        "message": item["message"],
    }


def _job_state(items: list[dict[str, Any]]) -> tuple[str, str]:
    counts = _counts(items)
    if counts["pending"] > 0:
        return "running", "Die Kopie läuft; jede Einheit wird einzeln angelegt."
    if counts["unknown"] > 0:
        return (
            ("partial" if counts["created"] > 0 else "failed"),
            "Mindestens ein Vorgang ist unklar. Er wird nur lesend geprüft, "
            "nicht automatisch wiederholt.",
        )
    if counts["failed"] > 0:
        return (
            ("partial" if counts["created"] > 0 else "failed"),
            "Mindestens eine Einheit konnte nicht angelegt werden. "
            "Bereits angelegte Einheiten bleiben erhalten.",
        )
    return "completed", "Alle Einheiten wurden angelegt."


def _install_items(
    conn: sqlite3.Connection,
    preview: dict[str, Any],
    *,
    job_id: str,
    account_id: str,
    athlete_id: str,
    time_zone: str,
) -> list[dict[str, Any]]:
    ready = [item for item in preview["items"] if item["status"] == "ready"]
    items: list[dict[str, Any]] = []
    now = _now()
    for ordinal, item in enumerate(ready):
        source_row = db.event_by_id(conn, int(item["source_event_id"]))
        if source_row is None:
            raise CopyError(
                CopyCode.PREVIEW_CHANGED,
                "Eine Quellplanung hat sich zwischen Vorschau und Start geändert.",
                status=409,
            )
        try:
            remote = read_plan_row(
                source_row,
                time_zone=time_zone,
                account_id=account_id,
                athlete_id=athlete_id,
            )
            draft_id = f"copy:{job_id}:{item['source_event_id']}:{item['target_date']}"
            local_id = f"plan:{draft_id}"
            cloned, _ = clone_for_new_plan(
                remote.plan,
                target_date=item["target_date"],
                time_zone=time_zone,
                account_id=account_id,
                athlete_id=athlete_id,
                keep_time=True,
                draft_id=draft_id,
                local_id=local_id,
            )
        except (ValueError, CloneError) as exc:
            raise CopyError(
                CopyCode.PREVIEW_CHANGED,
                "Eine Quellplanung ist nicht mehr kopierbar. Es wurde nichts angelegt.",
                status=409,
            ) from exc
        nodes_json = json.dumps(plan_nodes_payload(cloned.nodes), ensure_ascii=False)
        item_id = f"copy-item:{uuid.uuid4().hex}"
        conn.execute(
            """
            INSERT INTO planner_copy_item (
                item_id, job_id, account_id, athlete_id, ordinal, source_event_id,
                source_date, target_date, draft_id, local_id, name, sport,
                nodes_json, state, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                item_id,
                job_id,
                account_id,
                athlete_id,
                ordinal,
                item["source_event_id"],
                item["source_date"],
                item["target_date"],
                draft_id,
                local_id,
                cloned.name,
                cloned.sport,
                nodes_json,
                now,
                now,
            ),
        )
        items.append(
            {
                "item_id": item_id,
                "job_id": job_id,
                "source_event_id": item["source_event_id"],
                "source_date": item["source_date"],
                "target_date": item["target_date"],
                "draft_id": draft_id,
                "local_id": local_id,
                "name": cloned.name,
                "sport": cloned.sport,
                "state": "pending",
                "operation_id": None,
                "remote_id": None,
                "message": None,
            }
        )
    return items


def start_copy_job(
    conn: sqlite3.Connection,
    *,
    source_start: object,
    weeks: object,
    target_start: object,
    client_request_id: object,
    time_zone: str,
    account_id: str,
    athlete_id: str,
) -> tuple[dict[str, Any], bool]:
    request_id = str(client_request_id or "").strip()
    if not 8 <= len(request_id) <= 200:
        raise CopyError(
            CopyCode.INVALID_REQUEST,
            "Die Anfrage braucht eine stabile client_request_id.",
        )
    existing = conn.execute(
        "SELECT job_id FROM planner_copy_job WHERE account_id = ? AND athlete_id = ? "
        "AND client_request_id = ?",
        (account_id, athlete_id, request_id),
    ).fetchone()
    if existing is not None:
        return _job_payload(conn, str(existing["job_id"])), False

    preview = preview_copy(
        conn,
        source_start=source_start,
        weeks=weeks,
        target_start=target_start,
        time_zone=time_zone,
        account_id=account_id,
        athlete_id=athlete_id,
    )
    if preview["blockers"]:
        raise CopyError(
            CopyCode.COPY_RUNNING
            if any(b["code"] == CopyCode.COPY_RUNNING.value for b in preview["blockers"])
            else CopyCode.PREVIEW_CHANGED,
            "Die Kopie ist blockiert. Es wurde nichts angelegt.",
            status=409,
            blockers=preview["blockers"],
        )
    ready = [item for item in preview["items"] if item["status"] == "ready"]
    if not ready:
        raise CopyError(
            CopyCode.NO_ITEMS,
            "Es gibt keine neue Einheit zu kopieren.",
            status=409,
        )

    now = _now()
    job_id = f"copy-job:{uuid.uuid4().hex}"
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO planner_copy_job (
                job_id, account_id, athlete_id, client_request_id, state,
                source_start, target_start, weeks, time_zone, message,
                total, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                account_id,
                athlete_id,
                request_id,
                preview["source_start"],
                preview["target_start"],
                preview["weeks"],
                time_zone,
                "Kopie vorbereitet. Noch wurde nichts an intervals.icu gesendet.",
                len(ready),
                now,
                now,
            ),
        )
        _install_items(
            conn,
            preview,
            job_id=job_id,
            account_id=account_id,
            athlete_id=athlete_id,
            time_zone=time_zone,
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        # Ein paralleler Start mit derselben ID oder ein aktiver Job hat gewonnen.
        existing = conn.execute(
            "SELECT job_id FROM planner_copy_job WHERE account_id = ? AND athlete_id = ? "
            "AND client_request_id = ?",
            (account_id, athlete_id, request_id),
        ).fetchone()
        if existing is not None:
            return _job_payload(conn, str(existing["job_id"])), False
        raise CopyError(
            CopyCode.COPY_RUNNING,
            "Für diesen Account läuft bereits eine Kopie.",
            status=409,
        ) from exc
    except Exception:
        conn.rollback()
        raise
    return _job_payload(conn, job_id), True


def _claim(conn: sqlite3.Connection, job_id: str) -> str | None:
    token = uuid.uuid4().hex
    now = datetime.now().astimezone()
    expires = (now + timedelta(seconds=LEASE_SECONDS)).isoformat(timespec="seconds")
    cursor = conn.execute(
        "UPDATE planner_copy_job SET lease_owner = ?, lease_expires_at = ?, updated_at = ? "
        "WHERE job_id = ? AND (lease_owner IS NULL OR lease_expires_at IS NULL "
        "OR lease_expires_at < ?) AND state IN ('queued', 'running', 'partial', 'failed')",
        (
            token,
            expires,
            now.isoformat(timespec="seconds"),
            job_id,
            now.isoformat(timespec="seconds"),
        ),
    )
    if cursor.rowcount == 0:
        return None
    return token


def _release(conn: sqlite3.Connection, job_id: str, token: str) -> None:
    conn.execute(
        "UPDATE planner_copy_job SET lease_owner = NULL, lease_expires_at = NULL, updated_at = ? "
        "WHERE job_id = ? AND lease_owner = ?",
        (_now(), job_id, token),
    )


def _map_outcome(state: SaveState, message: str) -> tuple[str, str]:
    if state in (SaveState.SAVED, SaveState.CLEAN):
        return "created", message
    if state is SaveState.SAVED_UNVERIFIED:
        return "saved_unverified", message
    if state is SaveState.UNKNOWN:
        return "unknown", message
    if state is SaveState.CONFLICT:
        return "conflict", message
    return "failed", message


def _reconcile_item(
    conn: sqlite3.Connection,
    item: Mapping[str, Any],
    *,
    coordinator: SaveCoordinator,
    store: SqliteOperationStore,
) -> bool:
    operation_id = item["operation_id"]
    if operation_id is None:
        # Nach einem Abbruch zwischen Remote-Create und Item-Update kann der
        # Vorgang nur über seinen stabilen lokalen Schlüssel gefunden werden.
        for stored in store.open_operations(
            account_id=str(item["account_id"]), athlete_id=str(item["athlete_id"])
        ):
            snapshot = stored.snapshot
            if str(snapshot.local_id) == str(item["local_id"]):
                operation_id = str(snapshot.operation_id)
                conn.execute(
                    "UPDATE planner_copy_item SET operation_id = ?, updated_at = ? "
                    "WHERE item_id = ?",
                    (operation_id, _now(), item["item_id"]),
                )
                conn.commit()
                break
    if operation_id is None:
        return False
    try:
        outcome = coordinator.reconcile(operation_id)
    except KeyError:
        return False
    state, message = _map_outcome(outcome.status.state, outcome.status.message)
    if state == "created" and outcome.remote_raw is not None:
        merge_confirmed_event(conn, outcome.remote_raw)
    conn.execute(
        "UPDATE planner_copy_item SET state = ?, remote_id = ?, message = ?, updated_at = ? "
        "WHERE item_id = ?",
        (
            state,
            outcome.status.remote_id,
            message,
            _now(),
            item["item_id"],
        ),
    )
    conn.commit()
    return True


def advance_copy_job(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    account_id: str,
    athlete_id: str,
    settings: Any,
    service_factory: Any,
) -> dict[str, Any]:
    job = conn.execute(
        "SELECT * FROM planner_copy_job WHERE job_id = ? AND account_id = ? AND athlete_id = ?",
        (job_id, account_id, athlete_id),
    ).fetchone()
    if job is None:
        raise CopyError(CopyCode.NOT_FOUND, "Kopievorgang nicht gefunden.", status=404)
    if str(job["state"]) in TERMINAL_JOB_STATES:
        current = _job_payload(conn, job_id)
        if not any(
            item["state"] in ("unknown", "saved_unverified")
            for item in current["items"]
        ):
            return current

    lock = _JOB_LOCKS.setdefault(job_id, threading.Lock())
    if not lock.acquire(blocking=False):
        raise CopyError(CopyCode.COPY_BUSY, "Dieser Kopievorgang läuft bereits.", status=409)
    try:
        conn.execute("BEGIN IMMEDIATE")
        token = _claim(conn, job_id)
        if token is None:
            conn.rollback()
            raise CopyError(
                CopyCode.COPY_BUSY,
                "Dieser Kopievorgang wird bereits von einem anderen Prozess bearbeitet.",
                status=409,
            )
        conn.commit()

        try:
            store = SqliteOperationStore(conn)
            with service_factory(settings) as service:
                coordinator = SaveCoordinator(service, recorder=store, shared=True)
                if store.open_operations(
                    account_id=account_id, athlete_id=athlete_id
                ):
                    # Nach einem Neustart den persistierten Vorgang wieder in den
                    # lesenden Abgleich nehmen; es wird dabei nichts gesendet.
                    coordinator.restore_open(
                        account_id=account_id, athlete_id=athlete_id
                    )
                unresolved = conn.execute(
                    "SELECT * FROM planner_copy_item WHERE job_id = ? "
                    "AND state IN ('unknown', 'saved_unverified') "
                    "ORDER BY ordinal LIMIT 1",
                    (job_id,),
                ).fetchone()
                if unresolved is not None:
                    _reconcile_item(
                        conn,
                        dict(unresolved),
                        coordinator=coordinator,
                        store=store,
                    )
                else:
                    pending = conn.execute(
                        "SELECT * FROM planner_copy_item WHERE job_id = ? "
                        "AND state = 'pending' ORDER BY ordinal LIMIT 1",
                        (job_id,),
                    ).fetchone()
                    if pending is not None:
                        _process_item(
                            conn,
                            dict(pending),
                            coordinator=coordinator,
                            store=store,
                            time_zone=str(job["time_zone"]),
                            account_id=account_id,
                            athlete_id=athlete_id,
                        )
            _finish_job(conn, job_id)
        finally:
            _release(conn, job_id, token)
            conn.commit()
    finally:
        lock.release()
    return _job_payload(conn, job_id)


def _process_item(
    conn: sqlite3.Connection,
    item: Mapping[str, Any],
    *,
    coordinator: SaveCoordinator,
    store: SqliteOperationStore,
    time_zone: str,
    account_id: str,
    athlete_id: str,
) -> None:
    # Ein vorhandener offener Vorgang wird zuerst lesend geprüft; niemals ein
    # zweiter Create auf unklarem Zustand.
    for stored in store.open_operations(account_id=account_id, athlete_id=athlete_id):
        if str(stored.snapshot.local_id) == str(item["local_id"]):
            _reconcile_item(
                conn,
                {**dict(item), "operation_id": str(stored.snapshot.operation_id)},
                coordinator=coordinator,
                store=store,
            )
            return
    try:
        nodes = json.loads(str(item["nodes_json"]))
        draft = build_new_draft(
            {
                "draft_id": str(item["draft_id"]),
                "sport": str(item["sport"]),
                "date": str(item["target_date"]),
                "name": str(item["name"]),
                "nodes": nodes,
            },
            time_zone=time_zone,
            zone_profiles=plan.sport_profiles(conn),
        )
        outcome = coordinator.activate(
            draft,
            account_id=account_id,
            athlete_id=athlete_id,
            writable=True,
        )
        state, message = _map_outcome(outcome.status.state, outcome.status.message)
        if state == "created" and outcome.remote_raw is not None:
            merge_confirmed_event(conn, outcome.remote_raw)
        conn.execute(
            "UPDATE planner_copy_item SET state = ?, operation_id = ?, remote_id = ?, "
            "message = ?, updated_at = ? WHERE item_id = ?",
            (
                state,
                str(outcome.status.operation_id) if outcome.status.operation_id else None,
                outcome.status.remote_id,
                message,
                _now(),
                item["item_id"],
            ),
        )
        conn.commit()
    except (DraftProjectionError, ValueError, TypeError) as exc:
        conn.rollback()
        conn.execute(
            "UPDATE planner_copy_item SET state = 'failed', message = ?, updated_at = ? "
            "WHERE item_id = ?",
            (str(exc)[:300], _now(), item["item_id"]),
        )
        conn.commit()


def _finish_job(conn: sqlite3.Connection, job_id: str) -> None:
    items = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM planner_copy_item WHERE job_id = ?", (job_id,)
        ).fetchall()
    ]
    state, message = _job_state(items)
    conn.execute(
        "UPDATE planner_copy_job SET state = ?, message = ?, updated_at = ? WHERE job_id = ?",
        (state, message, _now(), job_id),
    )
    conn.commit()


def open_copy_jobs(
    conn: sqlite3.Connection, *, account_id: str, athlete_id: str
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT job_id FROM planner_copy_job j WHERE account_id = ? AND athlete_id = ? "
        "AND (state IN ('queued', 'running') OR (state IN ('partial', 'failed') "
        "AND EXISTS (SELECT 1 FROM planner_copy_item i WHERE i.job_id = j.job_id "
        "AND i.state IN ('unknown', 'saved_unverified')))) ORDER BY created_at",
        (account_id, athlete_id),
    ).fetchall()
    return [_job_payload(conn, str(row["job_id"]))["job"] for row in rows]


def get_copy_job(
    conn: sqlite3.Connection, job_id: str, *, account_id: str, athlete_id: str
) -> dict[str, Any]:
    row = conn.execute(
        "SELECT job_id FROM planner_copy_job WHERE job_id = ? "
        "AND account_id = ? AND athlete_id = ?",
        (job_id, account_id, athlete_id),
    ).fetchone()
    if row is None:
        raise CopyError(CopyCode.NOT_FOUND, "Kopievorgang nicht gefunden.", status=404)
    return _job_payload(conn, str(row["job_id"]))


_JOB_LOCKS: dict[str, threading.Lock] = {}


__all__ = [
    "CopyCode",
    "CopyError",
    "advance_copy_job",
    "get_copy_job",
    "open_copy_jobs",
    "preview_copy",
    "start_copy_job",
]
