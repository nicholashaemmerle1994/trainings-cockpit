"""Datenablage für Rohdumps und Befunde."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any


def dump_dir(data_dir: Path, source: str, day: date) -> Path:
    path = data_dir / "raw" / source / day.isoformat()
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def latest_day(data_dir: Path, source: str) -> date | None:
    root = data_dir / "raw" / source
    if not root.exists():
        return None
    days = sorted((p.name for p in root.iterdir() if p.is_dir()), reverse=True)
    for name in days:
        try:
            return date.fromisoformat(name)
        except ValueError:
            continue
    return None


def report_path(data_dir: Path, day: date) -> Path:
    path = data_dir / "reports" / f"phase0-{day.isoformat()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def now() -> datetime:
    return datetime.now().astimezone()
