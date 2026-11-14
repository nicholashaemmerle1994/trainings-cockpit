#!/usr/bin/python3
"""Install the independent macOS daily backup agent for the main database."""

from __future__ import annotations

import json
import os
import plistlib
import shlex
import shutil
import subprocess
from pathlib import Path

LABEL = "com.nicholas.trainings-cockpit.backup"


def prepare_ssh(runtime: Path) -> Path:
    """Keep launchd independent of credentials in macOS-protected Documents."""
    effective = subprocess.run(
        ["/usr/bin/ssh", "-G", "homeserver"], capture_output=True, text=True, check=True,
    )
    settings = {}
    for line in effective.stdout.splitlines():
        name, _, value = line.partition(" ")
        settings.setdefault(name, []).append(value)
    identities = [Path(value).expanduser() for value in settings.get("identityfile", [])]
    identity = next((path for path in identities if path.is_file()), None)
    if identity is None:
        raise RuntimeError("No existing SSH identity for homeserver found")
    key = runtime / "ssh-key"
    shutil.copyfile(identity, key)
    key.chmod(0o600)
    known_hosts = " ".join(
        json.dumps(str(Path(value).expanduser()))
        for value in shlex.split(settings["userknownhostsfile"][0])
    )
    config = runtime / "ssh-config"
    config.write_text(
        "Host homeserver\n"
        + "  HostName " + settings["hostname"][0] + "\n"
        + "  User " + settings["user"][0] + "\n"
        + "  Port " + settings["port"][0] + "\n"
        + "  IdentityFile " + json.dumps(str(key)) + "\n"
        + "  IdentitiesOnly yes\n  BatchMode yes\n  StrictHostKeyChecking yes\n"
        + "  UserKnownHostsFile " + known_hosts + "\n",
        encoding="utf-8",
    )
    config.chmod(0o600)
    return config


def install(home: Path, *, load: bool = True) -> dict:
    runtime = home / "Library/Application Support/Trainings-Cockpit/Backup"
    logs = home / "Library/Logs/Trainings-Cockpit"
    backups = home / "Backups/Trainings-Cockpit/main"
    agents = home / "Library/LaunchAgents"
    for directory in (runtime, logs, backups):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
    agents.mkdir(parents=True, exist_ok=True)
    program = runtime / "backup-main.py"
    shutil.copyfile(Path(__file__).with_name("backup-main.py"), program)
    program.chmod(0o700)
    ssh_config = prepare_ssh(runtime)
    stdout = logs / "backup.log"
    stderr = logs / "backup-error.log"
    for path in (stdout, stderr):
        path.touch(mode=0o600, exist_ok=True)
        path.chmod(0o600)
    plist = agents / (LABEL + ".plist")
    config = {
        "Label": LABEL,
        "ProgramArguments": [
            "/usr/bin/python3", str(program), "--if-due", "--destination", str(backups),
            "--ssh-config", str(ssh_config),
        ],
        "RunAtLoad": True,
        "StartCalendarInterval": {"Hour": 19, "Minute": 0},
        "StartInterval": 3600,
        "ProcessType": "Background",
        "EnvironmentVariables": {"HOME": str(home), "TZ": "Europe/Vienna"},
        "StandardOutPath": str(stdout),
        "StandardErrorPath": str(stderr),
        "Umask": 0o077,
    }
    with plist.open("wb") as stream:
        plistlib.dump(config, stream)
    plist.chmod(0o600)
    if load:
        domain = "gui/" + str(os.getuid())
        service = domain + "/" + LABEL
        loaded = subprocess.run(
            ["/bin/launchctl", "print", service], capture_output=True,
        )
        if loaded.returncode == 0:
            subprocess.run(["/bin/launchctl", "bootout", service], check=True)
        subprocess.run(["/bin/launchctl", "enable", service], check=True)
        subprocess.run(["/bin/launchctl", "bootstrap", domain, str(plist)], check=True)
    return {
        "label": LABEL, "program": str(program), "backups": str(backups),
        "plist": str(plist), "stdout": str(stdout), "stderr": str(stderr),
    }


if __name__ == "__main__":
    os.umask(0o077)
    print(json.dumps(install(Path.home()), ensure_ascii=False, indent=2))
