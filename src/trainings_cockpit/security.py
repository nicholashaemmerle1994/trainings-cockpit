"""Kleine Sicherheits- und Dateisystem-Helfer."""

from __future__ import annotations

import os
import stat
from pathlib import Path


def is_world_readable(path: Path) -> bool:
    """True, wenn Gruppe oder Andere die Datei lesen dürfen."""
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return False
    return bool(mode & (stat.S_IRGRP | stat.S_IROTH))


def tighten(path: Path) -> None:
    """Setzt restriktive Rechte auf eine Datei (POSIX)."""
    if os.name != "posix":
        return
    path.chmod(0o600)


def relative_to_project(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)
