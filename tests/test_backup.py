from __future__ import annotations

import hashlib
import importlib.util
import json
import shlex
import shutil
import sqlite3
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from trainings_cockpit import db


def load_tool(name):
    path = Path(__file__).resolve().parents[1] / "tools" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = load_tool("backup-main")
installer = load_tool("install-backup-agent")
VIENNA = ZoneInfo("Europe/Vienna")


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.db"
    conn = db.connect(path)
    db.init_db(conn)
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute(
        "INSERT INTO activity(source,source_id,date,start_local,sport,updated_at) "
        "VALUES ('test','1','2026-11-14','2026-11-14T08:00:00','Run','2026-11-14')"
    )
    conn.commit()
    yield path, conn
    conn.close()


@pytest.fixture
def remote_locally(monkeypatch):
    original_run = subprocess.run

    def run(args, **kwargs):
        assert args[0] == "/usr/bin/ssh"
        remote = shlex.split(args[-1])
        assert remote[:2] == ["python3", "-c"]
        return original_run([sys.executable, *remote[1:]], **kwargs)

    monkeypatch.setattr(tool.subprocess, "run", run)


def test_live_wal_snapshot_is_standalone_and_restorable(source, tmp_path, remote_locally):
    path, conn = source
    assert Path(str(path) + "-wal").stat().st_size > 0
    destination = tmp_path / "backups"
    result = tool.backup("test", str(path), destination)
    snapshot = Path(result["backup"])
    assert snapshot.name == "cockpit-main.db"
    assert result["activities"] == 1
    assert result["sha256"] == hashlib.sha256(snapshot.read_bytes()).hexdigest()
    assert stat.S_IMODE(snapshot.stat().st_mode) == 0o600
    assert stat.S_IMODE(destination.stat().st_mode) == 0o700
    assert not list(destination.glob("*.part"))
    assert not Path(str(snapshot) + "-wal").exists()
    restored = tmp_path / "restored.db"
    shutil.copyfile(snapshot, restored)
    with sqlite3.connect(restored) as restored_conn:
        assert restored_conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert restored_conn.execute("SELECT sport FROM activity").fetchone()[0] == "Run"
    assert conn.execute("SELECT count(*) FROM activity").fetchone()[0] == 1


def test_success_replaces_one_backup_and_due_check_catches_up(
    source, tmp_path, remote_locally, monkeypatch,
):
    path, conn = source
    destination = tmp_path / "backups"
    morning = datetime(2026, 11, 14, 9, tzinfo=VIENNA)
    first = tool.backup("test", str(path), destination, now=morning)
    assert not tool.is_due(destination, datetime(2026, 11, 14, 18, tzinfo=VIENNA))
    assert tool.is_due(destination, datetime(2026, 11, 14, 19, tzinfo=VIENNA))
    # A failure/offline period leaves the daily boundary due after the next login.
    assert tool.is_due(destination, datetime(2026, 11, 15, 8, tzinfo=VIENNA))
    conn.execute(
        "INSERT INTO wellness(date,hrv,updated_at) VALUES ('2026-11-14',50,'2026-11-14')"
    )
    conn.commit()
    (destination / ".snapshot-interrupted.part").write_bytes(b"interrupted transfer")
    second = tool.backup(
        "test", str(path), destination, now=datetime(2026, 11, 15, 8, tzinfo=VIENNA),
    )
    assert first["backup"] == second["backup"]
    assert second["wellness_days"] == 1
    assert len(list(destination.glob("*.db"))) == 1
    assert not list(destination.glob("*.part"))

    def unexpected_transfer(*args, **kwargs):
        pytest.fail("An already covered day must not start SSH")

    monkeypatch.setattr(tool.subprocess, "run", unexpected_transfer)
    skipped = tool.backup(
        "test", str(path), destination, if_due=True,
        now=datetime(2026, 11, 15, 12, tzinfo=VIENNA),
    )
    assert skipped["status"] == "already_backed_up"


@pytest.mark.parametrize("failure", ["transfer", "corrupt", "wrong_database"])
def test_failed_backup_keeps_last_good_copy_and_manifest(
    source, tmp_path, remote_locally, monkeypatch, failure,
):
    path, _ = source
    destination = tmp_path / "backups"
    tool.backup("test", str(path), destination)
    previous = (destination / "cockpit-main.db").read_bytes()
    manifest = (destination / "latest.json").read_bytes()

    def fail(args, **kwargs):
        if failure == "wrong_database":
            other = tmp_path / "unrelated.db"
            with sqlite3.connect(other) as conn:
                conn.execute("CREATE TABLE unrelated (id INTEGER)")
            kwargs["stdout"].write(other.read_bytes())
        else:
            kwargs["stdout"].write(b"partial transfer")
            if failure == "transfer":
                raise subprocess.CalledProcessError(255, args, stderr=b"offline")

    monkeypatch.setattr(tool.subprocess, "run", fail)
    with pytest.raises((subprocess.CalledProcessError, sqlite3.Error, RuntimeError)):
        tool.backup("test", str(path), destination)
    assert (destination / "cockpit-main.db").read_bytes() == previous
    assert (destination / "latest.json").read_bytes() == manifest
    assert not list(destination.glob("*.part"))


def test_agent_uses_installed_copy_with_login_calendar_and_retry(tmp_path, monkeypatch):
    import plistlib

    identity = tmp_path / "existing-test-key"
    identity.write_text("test fixture, not a real private key")

    def ssh_config(args, **kwargs):
        assert args == ["/usr/bin/ssh", "-G", "homeserver"]
        return subprocess.CompletedProcess(
            args, 0, stdout=(
                "hostname 127.0.0.1\nuser test\nport 22\n"
                + "identityfile " + str(identity) + "\n"
                + "userknownhostsfile " + str(tmp_path / "known_hosts") + "\n"
            ),
        )

    monkeypatch.setattr(installer.subprocess, "run", ssh_config)
    result = installer.install(tmp_path, load=False)
    with Path(result["plist"]).open("rb") as stream:
        config = plistlib.load(stream)
    assert config["RunAtLoad"] is True
    assert config["StartCalendarInterval"] == {"Hour": 19, "Minute": 0}
    assert config["StartInterval"] == 3600
    assert config["ProgramArguments"][:2] == ["/usr/bin/python3", result["program"]]
    assert "--if-due" in config["ProgramArguments"]
    assert "--ssh-config" in config["ProgramArguments"]
    assert Path(result["program"]).is_file()
    runtime = Path(result["program"]).parent
    assert (runtime / "ssh-key").read_bytes() == identity.read_bytes()
    assert stat.S_IMODE((runtime / "ssh-key").stat().st_mode) == 0o600
    assert "StrictHostKeyChecking yes" in (runtime / "ssh-config").read_text()
    assert json.loads(json.dumps(config))["Umask"] == 0o077
