"""Loader für die fachlichen Planer-Fixtures (P01)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "planner"
CASES_DIR = FIXTURE_DIR / "cases"
REMOTE_DIR = FIXTURE_DIR / "remote"


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def case_paths() -> list[Path]:
    return sorted(CASES_DIR.glob("f*.json"))


def load_cases() -> list[dict[str, Any]]:
    return [load_json(path) for path in case_paths()]


def load_case(case_id: str) -> dict[str, Any]:
    for path in case_paths():
        data = load_json(path)
        if data.get("case") == case_id:
            return data
    raise FileNotFoundError(f"Fixture {case_id} fehlt in {CASES_DIR}")


def load_profiles() -> dict[str, Any]:
    return load_json(FIXTURE_DIR / "profiles.json")


def load_remote(relative_path: str) -> dict[str, Any]:
    return load_json(REMOTE_DIR / relative_path)


def load_matrix() -> dict[str, Any]:
    return load_json(FIXTURE_DIR / "capability-matrix.json")
