"""Konfiguration und Pfade."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_BASE_URL = "https://intervals.icu/api/v1"
#: Der Planer rechnet mit lokalen Kalendertagen des Athleten. Die Zeitzone ist
#: eine explizite IANA-Zone, nicht die zufällige Zeitzone des Servers.
DEFAULT_TIME_ZONE = "Europe/Vienna"

DEFAULT_GOALS: tuple[dict[str, str], ...] = (
    {"name": "Halbmarathon", "date": "2026-11-21", "priority": "C"},
    {"name": "Vienna City Marathon", "date": "2027-04-18", "priority": "B"},
    {"name": "IRONMAN Kärnten-Klagenfurt", "date": "2027-06-13", "priority": "A"},
)


@dataclass(frozen=True)
class Settings:
    intervals_key: str | None
    intervals_athlete: str
    garmin_key: str | None
    data_dir: Path
    base_url: str
    goals: tuple[dict[str, str], ...] = DEFAULT_GOALS
    time_zone: str = DEFAULT_TIME_ZONE

    @classmethod
    def load(cls, env_file: Path | None = None) -> Settings:
        load_dotenv(env_file or DEFAULT_ENV_FILE, override=False)
        return cls(
            intervals_key=_clean(os.getenv("INTERVALS_API_KEY")),
            intervals_athlete=_clean(os.getenv("INTERVALS_ATHLETE_ID")) or "0",
            garmin_key=_clean(os.getenv("GARMIN_PERSONAL_API_KEY")),
            data_dir=Path(os.getenv("TC_DATA_DIR") or DEFAULT_DATA_DIR),
            base_url=(_clean(os.getenv("INTERVALS_BASE_URL")) or DEFAULT_BASE_URL).rstrip("/"),
            goals=_load_goals(),
            time_zone=_clean(os.getenv("TC_TIME_ZONE")) or DEFAULT_TIME_ZONE,
        )

    def ensure_data_dir(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir

    @property
    def db_path(self) -> Path:
        return self.data_dir / "cockpit.db"


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _load_goals() -> tuple[dict[str, str], ...]:
    raw = _clean(os.getenv("TC_GOALS"))
    if not raw:
        return DEFAULT_GOALS
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return DEFAULT_GOALS
    if not isinstance(parsed, list):
        return DEFAULT_GOALS
    goals = [
        {
            "name": str(item.get("name", "")).strip(),
            "date": str(item.get("date", "")).strip(),
            "priority": str(item.get("priority", "C")),
        }
        for item in parsed
        if isinstance(item, dict) and item.get("name") and item.get("date")
    ]
    return tuple(goals)


def mask(secret: str | None) -> str:
    if not secret:
        return "—"
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}…{secret[-4:]} ({len(secret)} Zeichen)"
