#!/usr/bin/python3
"""Pull a verified, consistent production SQLite snapshot from the homeserver.

Only the Python standard library and key-based SSH access are required.
The source is read-only; the last backup is replaced only after validation.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shlex
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

REMOTE_DB = "~/docker/compose/cockpit/data/cockpit.db"
REQUIRED_TABLES = {"activity", "wellness", "event", "setting", "sync_run"}

# Back up the live database through SQLite, including committed WAL contents.
# The temporary server-side snapshot is private and removed after transmission.
REMOTE_SCRIPT = r'''
import pathlib, shutil, sqlite3, sys, tempfile, time
source_path = pathlib.Path(sys.argv[1]).expanduser().resolve(strict=True)
with tempfile.TemporaryDirectory(prefix="cockpit-backup-") as folder:
    snapshot = pathlib.Path(folder) / "snapshot.db"
    source = sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True)
    target = sqlite3.connect(snapshot)
    started = time.monotonic()
    def progress(status, remaining, total):
        if time.monotonic() - started > 90:
            raise TimeoutError("SQLite snapshot exceeded 90 seconds")
    try:
        source.backup(target, pages=256, progress=progress, sleep=0.05)
        target.execute("PRAGMA journal_mode=DELETE")
    finally:
        target.close()
        source.close()
    with snapshot.open("rb") as stream:
        shutil.copyfileobj(stream, sys.stdout.buffer)
    sys.stdout.buffer.flush()
'''


def inspect_snapshot(path: Path) -> dict:
    """Check all database pages and identify the expected cockpit tables."""
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        checks = [row[0] for row in conn.execute("PRAGMA integrity_check")]
        if checks != ["ok"]:
            raise RuntimeError("SQLite integrity_check failed: " + "; ".join(checks))
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        missing = REQUIRED_TABLES - tables
        if missing:
            raise RuntimeError("Missing cockpit tables: " + ", ".join(sorted(missing)))
        return {
            "activities": conn.execute("SELECT count(*) FROM activity").fetchone()[0],
            "wellness_days": conn.execute("SELECT count(*) FROM wellness").fetchone()[0],
            "events": conn.execute("SELECT count(*) FROM event").fetchone()[0],
            "last_sync": conn.execute(
                "SELECT finished_at FROM sync_run WHERE status='ok' ORDER BY id DESC LIMIT 1"
            ).fetchone(),
        }
    finally:
        conn.close()


def is_due(destination: Path, now: datetime) -> bool:
    """A successful snapshot covers daily boundaries through its creation time."""
    boundary = now.replace(hour=19, minute=0, second=0, microsecond=0)
    if now < boundary:
        boundary -= timedelta(days=1)
    try:
        manifest = json.loads((destination / "latest.json").read_text(encoding="utf-8"))
        created = datetime.fromisoformat(manifest["created_at"])
        name = manifest["file"]
        if Path(name).name != name or created < boundary:
            return True
        snapshot = destination / name
        return hashlib.sha256(snapshot.read_bytes()).hexdigest() != manifest["sha256"]
    except (OSError, ValueError, KeyError, TypeError):
        return True


def backup(
    host: str, remote_db: str, destination: Path,
    *, if_due: bool = False, now: datetime | None = None, ssh_config: Path | None = None,
) -> dict:
    if host.startswith("-"):
        raise ValueError("SSH host must not start with '-'")
    destination = destination.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.chmod(0o700)
    lock_fd = os.open(destination / ".backup.lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(lock_fd, "w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        # A forced shutdown can bypass finally; discard only our own leftovers.
        for pattern in (".snapshot-*.part", ".latest-*.part"):
            for leftover in destination.glob(pattern):
                leftover.unlink()
        now = now or datetime.now(ZoneInfo("Europe/Vienna"))
        if if_due and not is_due(destination, now):
            return {"status": "already_backed_up", "checked_at": now.isoformat()}
        name = "cockpit-main.db"
        snapshot = destination / name
        temporary = None
        manifest_tmp = None
        try:
            fd, raw_path = tempfile.mkstemp(prefix=".snapshot-", suffix=".part", dir=destination)
            temporary = Path(raw_path)
            command = "python3 -c " + shlex.quote(REMOTE_SCRIPT) + " " + shlex.quote(remote_db)
            ssh_args = ["/usr/bin/ssh"]
            if ssh_config is not None:
                ssh_args.extend(["-F", str(ssh_config)])
            with os.fdopen(fd, "wb") as stream:
                subprocess.run(
                    ssh_args + [
                        "-T", "-o", "BatchMode=yes",
                        "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=15",
                        "-o", "ServerAliveCountMax=3", host, command,
                    ],
                    stdout=stream, stderr=subprocess.PIPE, timeout=180, check=True,
                )
                stream.flush()
                os.fsync(stream.fileno())
            details = inspect_snapshot(temporary)
            sync_row = details["last_sync"]
            details["last_sync"] = sync_row[0] if sync_row else None
            manifest = {
                "created_at": now.isoformat(timespec="seconds"),
                "source_host": host,
                "source_database": remote_db,
                "file": name,
                "bytes": temporary.stat().st_size,
                "sha256": hashlib.sha256(temporary.read_bytes()).hexdigest(),
                "integrity_check": "ok",
                **details,
            }
            # Atomic replacement keeps the previous backup until validation succeeds.
            temporary.replace(snapshot)
            fd, raw_path = tempfile.mkstemp(prefix=".latest-", suffix=".part", dir=destination)
            manifest_tmp = Path(raw_path)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(manifest, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            manifest_tmp.replace(destination / "latest.json")
            return {"backup": str(snapshot), **manifest}
        finally:
            for path in (temporary, manifest_tmp):
                if path is not None:
                    path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="homeserver")
    parser.add_argument("--remote-db", default=REMOTE_DB)
    parser.add_argument("--ssh-config", type=Path, help="Independent SSH configuration for launchd")
    parser.add_argument(
        "--if-due", action="store_true", help="Skip an already covered daily backup",
    )
    parser.add_argument(
        "--destination", type=Path,
        default=Path.home() / "Backups" / "Trainings-Cockpit" / "main",
    )
    args = parser.parse_args()
    os.umask(0o077)
    try:
        result = backup(
            args.host, args.remote_db, args.destination,
            if_due=args.if_due, ssh_config=args.ssh_config,
        )
    except BlockingIOError:
        print("Backup already running; no second transfer started.")
        return 0
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.decode("utf-8", errors="replace").strip()
        print("Backup failed: " + message, file=sys.stderr)
        return 1
    except (OSError, RuntimeError, ValueError, sqlite3.Error, subprocess.TimeoutExpired) as exc:
        print("Backup failed: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
