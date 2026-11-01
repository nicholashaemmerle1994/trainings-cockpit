"""Test-Workout für den Phase-0-Push und dessen Verifikation."""

from __future__ import annotations

from datetime import date
from typing import Any

SPIKE_PREFIX = "tc:spike"

# Bewusst einfache intervals-Syntax: Warmup, 3 Wiederholungen, Cooldown.
TEST_DESCRIPTION = "- 15m 60%\n\n3x\n- 3m 110%\n- 3m 55%\n\n- 10m 55%"
TEST_DURATION_SECONDS = 15 * 60 + 3 * (3 * 60 + 3 * 60) + 10 * 60


def build_test_event(
    day: date,
    *,
    sport: str = "Ride",
    name: str = "TC Spike — Testeinheit",
    external_id: str | None = None,
) -> dict[str, Any]:
    return {
        "category": "WORKOUT",
        "start_date_local": f"{day.isoformat()}T00:00:00",
        "type": sport,
        "name": name,
        "description": TEST_DESCRIPTION,
        "moving_time": TEST_DURATION_SECONDS,
        "target": "POWER",
        "external_id": external_id or f"{SPIKE_PREFIX}:{day.isoformat()}",
    }


def verify_event(event: dict[str, Any], expected_external_id: str | None = None) -> dict[str, Any]:
    """Prüft, ob intervals.icu den Workout-Text geparst und Last berechnet hat."""
    doc = event.get("workout_doc") or {}
    steps = doc.get("steps") or []
    load = event.get("icu_training_load")
    intensity = event.get("icu_intensity")
    issues: list[str] = []

    if not steps:
        issues.append("workout_doc.steps ist leer — Text wurde nicht geparst")
    if load is None:
        issues.append("icu_training_load fehlt")
    elif load <= 0:
        issues.append(f"icu_training_load ist {load}")
    if expected_external_id and event.get("external_id") != expected_external_id:
        issues.append("external_id stimmt nicht überein")

    return {
        "ok": not issues,
        "event_id": event.get("id"),
        "name": event.get("name"),
        "external_id": event.get("external_id"),
        "type": event.get("type"),
        "steps": len(steps),
        "load": load,
        "intensity": intensity,
        "moving_time": event.get("moving_time"),
        "issues": issues,
    }
