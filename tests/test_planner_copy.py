"""P6/P7: Schema-Upgrade und persistente Copy-Grenzen ohne API."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from trainings_cockpit import db


def _columns(conn, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def test_copy_tabellen_werden_auf_bestehender_datenbank_nachgezogen(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "cockpit.db")
    try:
        db.init_db(conn)
        # Ein Bestand aus der Zeit vor TB-23: die beiden Copy-Tabellen fehlen.
        conn.execute("DROP TABLE planner_copy_item")
        conn.execute("DROP TABLE planner_copy_job")
        db.init_db(conn)
        job_columns = _columns(conn, "planner_copy_job")
        item_columns = _columns(conn, "planner_copy_item")
        assert {
            "job_id",
            "client_request_id",
            "source_start",
            "target_start",
            "total",
        } <= job_columns
        assert {
            "item_id",
            "source_event_id",
            "target_date",
            "draft_id",
            "nodes_json",
        } <= item_columns
        # Ein zweiter Lauf bleibt idempotent.
        db.init_db(conn)
    finally:
        conn.close()


def test_provenienz_index_blockiert_nur_aktive_und_bestaetigte_items(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "cockpit.db")
    try:
        db.init_db(conn)
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO planner_copy_job (job_id, account_id, athlete_id, client_request_id, "
            "state, source_start, target_start, weeks, time_zone, message, total, "
            "created_at, updated_at) "
            "VALUES ('j1', 'a', 'b', 'request-1', 'queued', '2026-11-02', '2026-11-09', 1, "
            "'Europe/Vienna', '', 1, ?, ?)",
            (now, now),
        )
        common = (
            "j1",
            "a",
            "b",
            0,
            "9101",
            "2026-11-02",
            "2026-11-09",
            "draft-1",
            "plan:draft-1",
            "Lauf",
            "Run",
            "[]",
            now,
            now,
        )
        conn.execute(
            "INSERT INTO planner_copy_item (item_id, job_id, account_id, athlete_id, ordinal, "
            "source_event_id, source_date, target_date, draft_id, local_id, name, sport, "
            "nodes_json, state, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
            ("i1", *common),
        )
        try:
            conn.execute(
                "INSERT INTO planner_copy_item (item_id, job_id, account_id, athlete_id, ordinal, "
                "source_event_id, source_date, target_date, draft_id, local_id, name, sport, "
                "nodes_json, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unknown', ?, ?)",
                ("i2", *common),
            )
            raise AssertionError("eine aktive Quelle/Ziel-Kombination darf nur einmal existieren")
        except db.sqlite3.IntegrityError:
            pass
        # Ein endgültig gescheitertes Item blockiert eine bewusste neue Kopie nicht.
        conn.execute(
            "INSERT INTO planner_copy_job (job_id, account_id, athlete_id, client_request_id, "
            "state, source_start, target_start, weeks, time_zone, message, total, "
            "created_at, updated_at) "
            "VALUES ('j2', 'a', 'b', 'request-2', 'failed', '2026-11-02', '2026-11-09', 1, "
            "'Europe/Vienna', '', 1, ?, ?)",
            (now, now),
        )
        failed = (
            "j2",
            "a",
            "b",
            0,
            "9101",
            "2026-11-02",
            "2026-11-09",
            "draft-2",
            "plan:draft-2",
            "Lauf",
            "Run",
            "[]",
            now,
            now,
        )
        conn.execute(
            "INSERT INTO planner_copy_item (item_id, job_id, account_id, athlete_id, ordinal, "
            "source_event_id, source_date, target_date, draft_id, local_id, name, sport, "
            "nodes_json, state, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'failed', ?, ?)",
            ("i3", *failed),
        )
    finally:
        conn.close()
